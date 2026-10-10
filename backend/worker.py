from __future__ import annotations
import asyncio, logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from astro.cielo import Cielo, cielo
from astro.signos import es_menor
from backend.cola import Cola, Item
from backend.filtro import evaluar
from backend.prompt import armar_prompt

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
    tipo: str          # "lectura" | "mensaje_fijo" | "pide_fecha"
    texto: str
    ts: datetime


class Worker:
    def __init__(self, cola: Cola, generador: Generador,
                 palabras_por_seg: float = 2.5, espera_vacia: float = 1.0):
        self.cola = cola
        self.generador = generador
        self.palabras_por_seg = palabras_por_seg
        self.espera_vacia = espera_vacia
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
                                               tipo, texto, ahora)])[-MAX_HISTORIAL:]
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

    async def _pedir_fechas(self, ahora: datetime) -> bool:
        faltan = self.cola.sin_fecha(ahora)[:MAX_PEDIDOS]
        if not faltan:
            return False
        for item in faltan:
            item.pedido_fecha = ahora
        nombres = ", ".join(i.nickname for i in faltan)
        texto = (f"{nombres}: para leerte necesito tu fecha de nacimiento. Escríbela en el chat con día, mes y año."
                 if len(faltan) == 1 else
                 f"{nombres}: para leerles necesito su fecha de nacimiento. Escríbanla en el chat con día, mes y año.")
        self.salidas = (self.salidas + [Salida("", nombres, "", "pide_fecha", texto, ahora)])[-MAX_HISTORIAL:]
        log.info(f"[PIDE_FECHA] {nombres}")
        if self.palabras_por_seg > 0:
            await asyncio.sleep(len(texto.split()) / self.palabras_por_seg)
        return True

    async def paso(self, ahora: datetime | None = None) -> bool:
        """Pide fechas que falten y procesa un ítem. Devuelve True si hizo algo."""
        if self.pausado:
            return False
        ahora = ahora or datetime.now(timezone.utc)
        self._descartar_menores(ahora)
        pidio = await self._pedir_fechas(ahora)
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