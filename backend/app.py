from dataclasses import asdict
from datetime import datetime, timezone
from typing import Literal
from fastapi import FastAPI
from pydantic import BaseModel
from backend.cola import Cola

app = FastAPI(title="Astrolia Live")
cola = Cola()


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


@app.get("/cola")
async def ver_cola():
    return [asdict(i) for i in cola.pendientes(ahora())]


@app.post("/cola/siguiente")
async def siguiente():
    item = cola.tomar_siguiente(ahora())
    return asdict(item) if item else None


@app.post("/cola/{user}/cerrar")
async def cerrar(user: str, estado: Literal["hecho", "saltado"] = "hecho"):
    cola.cerrar(user, estado)
    return {"ok": True}