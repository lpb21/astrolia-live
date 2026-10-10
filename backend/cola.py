from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from astro.signos import DatoSigno, extraer, extraer_pareja

VENTANA = timedelta(seconds=120)
ESPERA_FECHA = timedelta(seconds=90)   # tras pedir la fecha de nacimiento; luego se lee sin signo
NO_PREGUNTA = {"presente", "gracias", "hola", "buenas", "buenas noches",
               "ok", "si", "sí", "no", "yo", "amen", "amén"}


CORTESIA = re.compile(r"^(ok|okay|gracias|muchas gracias|mil gracias|muchas bendiciones|"
                      r"bendiciones|amen|amén|presente|hola)\b")

def es_pregunta(texto: str) -> bool:
    t = texto.strip().lower()
    if len(t) < 8 or t in NO_PREGUNTA:
        return False
    if CORTESIA.match(t) and "?" not in t and len(t.split()) <= 6:
        return False    # "ok gracias por su respuesta", "gracias por tus palabras"
    return len(re.findall(r"[a-záéíóúñü]", t)) >= 6


@dataclass
class Item:
    user: str
    nickname: str
    pregunta: str               # "" = lectura general
    valor: int
    regalos: list[str]
    ts: datetime                # cuándo quedó lista (pregunta + regalo)
    estado: str = "pendiente"   # pendiente | leyendo | hecho | saltado
    extras: list[str] = field(default_factory=list)   # preguntas posteriores, máx 3
    dato: DatoSigno | None = None           # signo / fecha de nacimiento de quien pregunta
    pedido_fecha: datetime | None = None    # cuándo se le pidió la fecha en voz
    pareja: DatoSigno | None = None         # signo de la otra persona, si lo dieron (nunca su fecha)


@dataclass
class _Pendiente:
    nickname: str
    ts: datetime
    texto: str = ""
    valor: int = 0
    regalos: list[str] = field(default_factory=list)


class Cola:
    def __init__(self, ventana: timedelta = VENTANA, espera_fecha: timedelta | None = ESPERA_FECHA):
        self.ventana = ventana
        self.espera_fecha = espera_fecha              # None = no exigir fecha de nacimiento
        self._datos: dict[str, DatoSigno] = {}        # último dato de nacimiento que dio cada usuario
        self._preguntas: dict[str, _Pendiente] = {}   # pregunta esperando regalo
        self._regalos: dict[str, _Pendiente] = {}     # regalo esperando pregunta
        self._items: dict[str, Item] = {}             # un ítem abierto por usuario
        self.historial: list[Item] = []
        self._msg_vistos: OrderedDict[int, None] = OrderedDict()

    # ---------- entrada ----------
    def procesar(self, ev: dict) -> None:
        msg_id = ev.get("msg_id") or 0
        if msg_id:
            if msg_id in self._msg_vistos:
                return
            self._msg_vistos[msg_id] = None
            if len(self._msg_vistos) > 20000:
                self._msg_vistos.popitem(last=False)
        ts = datetime.fromisoformat(ev["ts"])
        if ev["tipo"] == "comment" and self._on_dato(ev["user"], ev["texto"]):
            return
        if ev["tipo"] == "comment" and es_pregunta(ev["texto"]):
            self._on_pregunta(ev["user"], ev["nickname"], ev["texto"], ts)
        elif ev["tipo"] == "gift":
            self._on_regalo(ev["user"], ev["nickname"], ev["regalo"], ev["valor"], ts)

    def _on_dato(self, user, texto) -> bool:
        """Guarda la fecha o el signo si el comentario lo trae. True si solo era la respuesta
        a "¿cuál es tu fecha?" y no hay que tratarlo además como pregunta."""
        dato, pareja = extraer(texto), extraer_pareja(texto)
        item = self._items.get(user)
        if pareja and item and item.estado == "pendiente" and item.pareja is None:
            item.pareja = pareja
        if dato is None:
            return False
        self._datos[user] = dato
        if item and item.estado == "pendiente" and item.dato is None:
            item.dato = dato
            return bool(item.pregunta)
        return False

    def _on_pregunta(self, user, nickname, texto, ts):
        item = self._items.get(user)
        if item and item.estado == "pendiente":
            if not item.pregunta:
                item.pregunta = texto        # era lectura general y llegó la pregunta
            elif texto != item.pregunta and texto not in item.extras:
                item.extras = (item.extras + [texto])[-3:]
            return
        r = self._regalos.get(user)
        if r and ts - r.ts <= self.ventana:
            del self._regalos[user]
            self._crear(user, nickname, texto, r.valor, r.regalos, ts)
            return
        self._preguntas[user] = _Pendiente(nickname, ts, texto=texto)

    def _on_regalo(self, user, nickname, regalo, valor, ts):
        item = self._items.get(user)
        if item and item.estado == "pendiente":
            item.valor += valor
            item.regalos.append(regalo)
            return
        p = self._preguntas.get(user)
        if p and ts - p.ts <= self.ventana:
            del self._preguntas[user]
            self._crear(user, nickname, p.texto, valor, [regalo], ts)
            return
        r = self._regalos.setdefault(user, _Pendiente(nickname, ts))
        r.valor += valor
        r.regalos.append(regalo)

    def _crear(self, user, nickname, texto, valor, regalos, ts):
        self._items[user] = Item(user, nickname, texto, valor, list(regalos), ts,
                                 dato=self._datos.get(user), pareja=extraer_pareja(texto))

    # ---------- mantenimiento ----------
    def _vencer(self, ahora: datetime) -> None:
        for user, r in list(self._regalos.items()):
            if ahora - r.ts > self.ventana and user not in self._items:
                del self._regalos[user]
                self._crear(user, r.nickname, "", r.valor, r.regalos, r.ts)
        for user, p in list(self._preguntas.items()):
            if ahora - p.ts > self.ventana:
                del self._preguntas[user]

    # ---------- salida ----------
    def pendientes(self, ahora: datetime) -> list[Item]:
        self._vencer(ahora)
        abiertos = [i for i in self._items.values() if i.estado == "pendiente"]
        return sorted(abiertos, key=lambda i: (-i.valor, i.ts))

    def _lista(self, item: Item, ahora: datetime) -> bool:
        if item.dato or self.espera_fecha is None:
            return True
        return item.pedido_fecha is not None and ahora - item.pedido_fecha > self.espera_fecha

    def sin_fecha(self, ahora: datetime) -> list[Item]:
        """Ítems a los que todavía no se les ha pedido la fecha de nacimiento."""
        if self.espera_fecha is None:
            return []
        return [i for i in self.pendientes(ahora) if i.dato is None and i.pedido_fecha is None]

    def tomar_siguiente(self, ahora: datetime) -> Item | None:
        for item in self.pendientes(ahora):
            if self._lista(item, ahora):
                item.estado = "leyendo"
                return item
        return None

    def cerrar(self, user: str, estado: str = "hecho") -> None:
        item = self._items.pop(user, None)
        if item:
            item.estado = estado
            self.historial.append(item)