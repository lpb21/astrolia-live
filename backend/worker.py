from __future__ import annotations
import asyncio, logging
from dataclasses import dataclass, field
import random
from datetime import datetime, timedelta, timezone
from typing import Protocol
from astro.cielo import Cielo, cielo
from astro.signos import es_menor
from backend.cola import Cola, Item
from backend.filtro import evaluar
from backend.prompt import armar_prompt
from tarot.tirada import CartaTirada, nivel_para, tirar

log = logging.getLogger("worker")
MAX_HISTORIAL = 50
MAX_PEDIDOS = 3        # a cuántas personas se les pide la fecha en un mismo aviso


class Generador(Protocol):
    async def generar(self, prompt: dict) -> dict: ...


class GeneradorFalso:
    async def generar(self, prompt: dict) -> dict:
        return {"sensible": False, "categoria": "", "respuesta": "Respuesta de prueba del generador falso."}


@dataclass
class Salida:
    user: str
    nickname: str
    pregunta: str
    tipo: str          # "lectura" | "mensaje_fijo" | "pide_fecha" | "pide_pregunta"
    texto: str
    ts: datetime
    cartas: list[CartaTirada] = field(default_factory=list)
    nivel: str = ""


class Worker:
    def __init__(self, cola: Cola, generador: Generador,
                 palabras_por_seg: float = 2.5, espera_vacia: float = 1.0,
                 rng: random.Random | None = None):
        self.cola = cola
        self.generador = generador
        self.palabras_por_seg = palabras_por_seg
        self.espera_vacia = espera_vacia
        self.rng = rng                 # solo para pruebas; None = azar del sistema
        self.pausado = False
        self.actual: Item | None = None
        self.salidas: list[Salida] = []
        self.saltados: list[dict] = []
        self._cielo: Cielo | None = None

    def _cielo_actual(self, ahora: datetime) -> Cielo:
        if self._cielo is None or ahora - self._cielo.momento > timedelta(hours=1):
            self._cielo = cielo(ahora)
        return self._cielo

    def _saltar(self, item: Item, categoria: str, motivo: str) -> None:
        self.cola.cerrar(item.user, "saltado")
        self.saltados = (self.saltados + [{"user": item.user, "pregunta": item.pregunta,
                                           "categoria": categoria, "motivo": motivo}])[-MAX_HISTORIAL:]
        log.info(f"[SALTADO] {item.user} ({categoria}: {motivo})")

    async def _entregar(self, item: Item, tipo: str, texto: str, ahora: datetime) -> None:
        self.salidas = (self.salidas + [Salida(item.user, item.nickname, item.pregunta,
                                               tipo, texto, ahora, list(item.cartas), item.nivel)])[-MAX_HISTORIAL:]
        log.info(f"[{tipo.upper()}] {item.user}: {texto[:80]}")
        if self.palabras_por_seg > 0:
            await asyncio.sleep(len(texto.split()) / self.palabras_por_seg)
        self.cola.cerrar(item.user, "hecho")

    async def _procesar(self, item: Item, ahora: datetime) -> None:
        if item.pregunta:
            f = evaluar(item.pregunta)
            if f.sensible:
                if f.accion == "mensaje_fijo":
                    await self._entregar(item, "mensaje_fijo", f.mensaje, ahora)
                else:
                    self._saltar(item, f.categoria, f.termino)
                return

        item.nivel = nivel_para(item.valor).nombre
        item.cartas = tirar(item.valor, self.rng)     # la tirada se hace cuando llega el turno
        prompt = armar_prompt(item, self._cielo_actual(ahora), item.dato)
        r = await self.generador.generar(prompt)
        if r.get("sensible"):
            self._saltar(item, r.get("categoria") or "modelo", "segundo filtro")
            return
        await self._entregar(item, "lectura", r["respuesta"], ahora)

    def _descartar_menores(self, ahora: datetime) -> None:
        """Saca de la cola a quien, por su fecha de nacimiento, tiene menos de 18 años."""
        for item in self.cola.pendientes(ahora):
            if es_menor(item.dato, ahora.date()):
                self._saltar(item, "menor", "fecha de nacimiento")

    async def _avisar(self, tipo: str, faltan: list[Item], uno: str, varios: str, ahora: datetime) -> bool:
        if not faltan:
            return False
        nombres = ", ".join(i.nickname for i in faltan)
        texto = f"{nombres}: {uno if len(faltan) == 1 else varios}"
        self.salidas = (self.salidas + [Salida("", nombres, "", tipo, texto, ahora)])[-MAX_HISTORIAL:]
        log.info(f"[{tipo.upper()}] {nombres}")
        if self.palabras_por_seg > 0:
            await asyncio.sleep(len(texto.split()) / self.palabras_por_seg)
        return True

    async def _pedir_preguntas(self, ahora: datetime) -> bool:
        faltan = self.cola.sin_pregunta(ahora)[:MAX_PEDIDOS]
        for item in faltan:
            item.pedido_pregunta = ahora
        return await self._avisar(
            "pide_pregunta", faltan,
            "gracias por tu regalo. Escribe tu pregunta con tu fecha de nacimiento; "
            "si prefieres, te leo el mensaje que las cartas tienen para ti.",
            "gracias por su regalo. Escriban su pregunta con su fecha de nacimiento; "
            "si prefieren, les leo el mensaje que las cartas tienen para ustedes.", ahora)

    async def _pedir_fechas(self, ahora: datetime) -> bool:
        faltan = self.cola.sin_fecha(ahora)[:MAX_PEDIDOS]
        for item in faltan:
            item.pedido_fecha = ahora
        return await self._avisar(
            "pide_fecha", faltan,
            "para leerte necesito tu fecha de nacimiento. Escríbela en el chat con día, mes y año.",
            "para leerles necesito su fecha de nacimiento. Escríbanla en el chat con día, mes y año.", ahora)

    async def paso(self, ahora: datetime | None = None) -> bool:
        """Pide fechas que falten y procesa un ítem. Devuelve True si hizo algo."""
        if self.pausado:
            return False
        ahora = ahora or datetime.now(timezone.utc)
        self._descartar_menores(ahora)
        pidio = await self._pedir_preguntas(ahora)
        pidio = await self._pedir_fechas(ahora) or pidio
        item = self.cola.tomar_siguiente(ahora)
        if item is None:
            return pidio
        self.actual = item
        try:
            await self._procesar(item, ahora)
        except Exception as exc:
            log.exception(f"[ERROR] procesando {item.user}")
            self._saltar(item, "error", repr(exc))
        finally:
            self.actual = None
        return True

    async def correr(self) -> None:
        log.info("worker iniciado")
        while True:
            if not await self.paso():
                await asyncio.sleep(self.espera_vacia)