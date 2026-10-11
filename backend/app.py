import asyncio, logging, os
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel
from astro.signos import extraer, fecha_incompleta
from backend import bitacora, revision
from backend.boost import Boost
from backend.cola import Cola, es_pregunta, parece_pregunta, trae_pregunta
from backend.filtro import evaluar
from backend.overlay import CARTAS, vista
from backend.worker import Worker, GeneradorFalso
from tarot.tirada import NIVELES, nivel_para

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

load_dotenv()


def _generador():
    """La IA real si hay clave en .env; sin clave, el generador de prueba (para ensayar sin gastar)."""
    if os.getenv("ANTHROPIC_API_KEY"):
        from backend.generador import GeneradorClaude
        generador = GeneradorClaude()
        logging.info(f"lecturas con Claude ({generador.modelo})")
        return generador
    logging.warning("sin ANTHROPIC_API_KEY en .env: lecturas con el generador de prueba")
    return GeneradorFalso()


# Boost de likes: cada BOOST_CADA_MIN minutos (0 = solo a pedido, con POST /control/boost)
_cada = int(os.getenv("BOOST_CADA_MIN", "10"))
boost = Boost(cada=timedelta(minutes=_cada) if _cada > 0 else None)

# Cada cuántos minutos la voz recuerda cómo pedir la pregunta gratis (0 = nunca)
_aviso = int(os.getenv("AVISO_GRATIS_MIN", "5"))

# Segundos mínimos entre un saludo a quienes van entrando y el siguiente (0 = no saludar).
# Solo se saluda cuando no hay ninguna pregunta lista para leer.
_bienvenida = int(os.getenv("BIENVENIDA_CADA_SEG", "180"))

cola = Cola()
worker = Worker(cola, _generador(), boost=boost,
                aviso_gratis=timedelta(minutes=_aviso) if _aviso > 0 else None,
                bienvenida=timedelta(seconds=_bienvenida) if _bienvenida > 0 else None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Un archivo por arranque: lecturas, avisos, turnos saltados y errores de cada live
    Path("logs").mkdir(exist_ok=True)
    archivo = logging.FileHandler(f"logs/{datetime.now():%Y-%m-%d_%H-%M-%S}_backend.log", encoding="utf-8")
    archivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(archivo)
    bitacora.abrir(Path(f"logs/{datetime.now():%Y-%m-%d_%H-%M-%S}_bitacora.jsonl"))
    tarea = asyncio.create_task(worker.correr())
    yield
    tarea.cancel()


app = FastAPI(title="Astrolia Live", lifespan=lifespan)


class EventoIn(BaseModel):
    tipo: str
    user: str
    nickname: str
    texto: str = ""
    regalo: str = ""
    valor: int = 0
    ts: str
    msg_id: int = 0


def ahora() -> datetime:
    return datetime.now(timezone.utc)


@app.post("/eventos", status_code=204)
async def recibir(ev: EventoIn):
    ts = datetime.fromisoformat(ev.ts)
    if ev.tipo == "like":            # valor = cuántos toques trae el evento
        boost.like(ev.user, ev.nickname, ev.valor, ts)
        return
    if ev.tipo == "join":
        worker.llegada(ev.user, ev.nickname)
        return
    cola.procesar(ev.model_dump())
    cola.pendientes(ahora())         # deja la fila al día para anotar en qué quedó la persona
    if ev.tipo == "comment":
        dato, tema = extraer(ev.texto), evaluar(ev.texto)
        bitacora.anotar("comentario", ev.user, ev.nickname, ts, texto=ev.texto, es=_clase(ev.texto, dato),
                        signo=dato.signo if dato else "", tema=tema.categoria if tema.sensible else "",
                        situacion=cola.situacion(ev.user))
    elif ev.tipo == "gift":
        bitacora.anotar("regalo", ev.user, ev.nickname, ts, texto=ev.regalo, valor=ev.valor,
                        situacion=cola.situacion(ev.user))
    elif ev.tipo == "follow":
        bitacora.anotar("follow", ev.user, ev.nickname, ts, texto="Empezó a seguir la cuenta")


def _clase(texto: str, dato) -> str:
    """Cómo entendió el sistema un comentario; es lo que explica en la revisión por qué entró o no."""
    if dato and not trae_pregunta(texto):
        return "solo fecha o signo"
    if fecha_incompleta(texto) and not es_pregunta(texto):
        return "fecha incompleta"
    if parece_pregunta(texto):
        return "pregunta clara"
    if es_pregunta(texto):
        return "pregunta sin señal clara"
    return "charla"


def _con_filtro(item) -> dict:
    d = asdict(item)
    d["filtro"] = asdict(evaluar(item.pregunta)) if item.pregunta else None
    d["nivel"] = nivel_para(item.valor).nombre
    d["falta"] = cola.falta(item)          # para marcar en la lista de turnos: "pregunta" o "fecha"
    return d


@app.get("/menu")
async def menu():
    """Niveles que se muestran en el overlay, del más barato al más caro."""
    return [{"monedas": n.minimo, "nombre": n.nombre, "cartas": len(n.posiciones)}
            for n in reversed(NIVELES) if n.en_menu]


@app.get("/cola")
async def ver_cola():
    return [_con_filtro(i) for i in cola.pendientes(ahora())]


# @app.post("/cola/siguiente")
# async def siguiente():
#     item = cola.tomar_siguiente(ahora())
#     return _con_filtro(item) if item else None


@app.post("/cola/{user}/cerrar")
async def cerrar(user: str, estado: Literal["hecho", "saltado"] = "hecho"):
    cola.cerrar(user, estado)
    return {"ok": True}


@app.post("/control/pausa")
async def pausar():
    worker.pausado = True
    return {"pausado": True}


@app.post("/control/boost")
async def lanzar_boost():
    """Abre una ronda de likes en cuanto termine lo que se esté diciendo."""
    boost.pedido = True
    return {"ok": True}


@app.post("/control/reanudar")
async def reanudar():
    worker.pausado = False
    return {"pausado": False}


@app.get("/estado")
async def estado():
    return {
        "pausado": worker.pausado,
        "actual": asdict(worker.actual) if worker.actual else None,
        "en_cola": len(cola.pendientes(ahora())),
        "ultimas_salidas": [asdict(s) for s in worker.salidas[-5:]],
        "ultimos_saltados": worker.saltados[-10:],
    }


@app.get("/revision/sesiones")
async def revision_sesiones():
    return revision.sesiones()


@app.get("/revision/datos")
async def revision_datos(sesion: str = ""):
    """Resumen por persona de un live. Sin `sesion`, el más reciente (el que está corriendo)."""
    disponibles = revision.sesiones()
    sesion = sesion or (disponibles[0] if disponibles else "")
    if sesion not in disponibles:
        return {"sesion": "", "personas": [], "totales": {}}
    return {"sesion": sesion, **revision.resumen(revision.leer(sesion))}


@app.get("/overlay/estado")
async def estado_overlay():
    return vista(cola, worker, ahora())


class SinCache(StaticFiles):
    """El navegador de LIVE Studio revalida cada archivo: un cambio en el overlay se ve al recargar."""
    async def get_response(self, path, scope):
        r = await super().get_response(path, scope)
        r.headers["Cache-Control"] = "no-cache"
        return r


if CARTAS.is_dir():      # sin imágenes el overlay dibuja las cartas; ver tools/descargar_cartas.py
    app.mount("/overlay/cartas", SinCache(directory=CARTAS), name="cartas")
# Página para revisar el live persona por persona: http://127.0.0.1:8000/revision/ (no sale al aire)
app.mount("/revision", SinCache(directory=Path(__file__).parent.parent / "revision", html=True), name="revision")
# Fuente de navegador para LIVE Studio: http://127.0.0.1:8000/overlay/
app.mount("/overlay", SinCache(directory=Path(__file__).parent.parent / "overlay", html=True), name="overlay")
