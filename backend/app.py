import asyncio, logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Literal
from fastapi import FastAPI
from pydantic import BaseModel
from backend.cola import Cola
from backend.filtro import evaluar
from backend.worker import Worker, GeneradorFalso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

cola = Cola()
worker = Worker(cola, GeneradorFalso())


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    cola.procesar(ev.model_dump())


def _con_filtro(item) -> dict:
    d = asdict(item)
    d["filtro"] = asdict(evaluar(item.pregunta)) if item.pregunta else None
    return d


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