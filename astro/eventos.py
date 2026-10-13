"""Eventos astrológicos relevantes (eclipses, ingresos, retrogradaciones, lunas) tomados de una API externa,
para comentarlos en el live.

TODAVÍA NO ESTÁ EN USO. Queda listo para cuando se conecte la base de datos: ese día se elige la API,
se ajusta `_leer` al formato que devuelva y se ponen ASTRO_API_URL y ASTRO_API_KEY en .env. Mientras
esas variables no existan, `desde_entorno()` devuelve None y el live sigue igual que hoy.

Cómo se usa (ya conectado en backend/app.py y backend/worker.py):
    fuente = desde_entorno()                      # None si no hay API configurada
    Worker(..., eventos=fuente)                   # en los ratos sin preguntas, la voz cuenta un evento
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging, os
import httpx

log = logging.getLogger("eventos")

ESPERA = 8.0                        # segundos; si la API tarda más, ese día no hay eventos
VIGENCIA = timedelta(hours=6)       # cada cuánto se vuelve a consultar
DIAS_ADELANTE = 7                   # se piden los eventos de hoy y de la semana que viene


@dataclass(frozen=True)
class EventoAstro:
    fecha: date
    titulo: str                     # "Luna llena en Aries", "Mercurio entra en Escorpio"
    detalle: str = ""               # una frase de qué invita a mirar; puede venir vacía

    def frase(self, hoy: date) -> str:
        """Cómo lo dice la voz."""
        dias = (self.fecha - hoy).days
        cuando = "Hoy" if dias == 0 else "Mañana" if dias == 1 else f"En {dias} días"
        return f"{cuando} tenemos {self.titulo}." + (f" {self.detalle}" if self.detalle else "")


def _leer(datos) -> list[EventoAstro]:
    """Convierte la respuesta de la API en eventos. PROVISIONAL: supone una lista de objetos con "date"
    (AAAA-MM-DD), "title" y, opcional, "description"; se ajusta cuando se elija la API."""
    lista = datos.get("events", []) if isinstance(datos, dict) else datos
    eventos = []
    for e in lista or []:
        try:
            eventos.append(EventoAstro(date.fromisoformat(str(e["date"])[:10]), str(e["title"]).strip(),
                                       str(e.get("description") or "").strip()))
        except (KeyError, ValueError, TypeError, AttributeError):
            continue                # un evento mal formado no tumba a los demás
    return sorted(eventos, key=lambda e: e.fecha)


class FuenteEventos:
    """Consulta la API y recuerda la respuesta unas horas. Nunca lanza: si falla, no hay eventos."""

    def __init__(self, url: str, clave: str = "", cliente: httpx.AsyncClient | None = None):
        self.url = url
        self.clave = clave
        self.cliente = cliente or httpx.AsyncClient(timeout=ESPERA)
        self._eventos: list[EventoAstro] = []
        self._consultado: datetime | None = None
        self._dichos: set[tuple[date, str]] = set()

    async def proximos(self, ahora: datetime) -> list[EventoAstro]:
        if self._consultado is None or ahora - self._consultado > VIGENCIA:
            self._consultado = ahora
            try:
                hoy = ahora.date()
                r = await self.cliente.get(self.url, params={"from": hoy.isoformat(),
                                                             "to": (hoy + timedelta(days=DIAS_ADELANTE)).isoformat()},
                                           headers={"Authorization": f"Bearer {self.clave}"} if self.clave else {})
                r.raise_for_status()
                self._eventos = _leer(r.json())
                log.info(f"[EVENTOS] {len(self._eventos)} eventos")
            except Exception as exc:
                log.warning(f"[EVENTOS] no se pudo consultar la API: {exc!r}")
        hoy = ahora.date()
        return [e for e in self._eventos if 0 <= (e.fecha - hoy).days <= DIAS_ADELANTE]

    async def siguiente(self, ahora: datetime) -> str | None:
        """La frase del próximo evento que aún no se ha dicho en este live, o None si no queda ninguno."""
        for e in await self.proximos(ahora):
            if (e.fecha, e.titulo) not in self._dichos:
                self._dichos.add((e.fecha, e.titulo))
                return e.frase(ahora.date())
        return None


def desde_entorno() -> FuenteEventos | None:
    """La fuente configurada en .env, o None si no hay (el caso de hoy)."""
    url = os.getenv("ASTRO_API_URL")
    return FuenteEventos(url, os.getenv("ASTRO_API_KEY", "")) if url else None
