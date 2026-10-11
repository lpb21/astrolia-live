from __future__ import annotations
from datetime import datetime
from pathlib import Path
from astro.signos import sin_fechas
from backend.cola import Cola
from backend.worker import Salida, Worker
from tarot.tirada import NIVELES, nivel_para

CARTAS = Path(__file__).parent.parent / "tarot" / "img"     # las baja tools/descargar_cartas.py
FORMATOS = (".webp", ".png", ".jpg", ".jpeg")
MAX_TURNOS = 5
MAX_PREGUNTA = 110


def _imagen(carta_id: str, carpeta: Path) -> str | None:
    """Ruta web de la imagen de la carta, si existe; el nombre del archivo es el id."""
    for ext in FORMATOS:
        if (carpeta / f"{carta_id}{ext}").is_file():
            return f"cartas/{carta_id}{ext}"
    return None


def _pregunta(texto: str) -> str:
    """La pregunta como se muestra en pantalla: sin fechas de nacimiento y recortada."""
    t = sin_fechas(texto)
    return t if len(t) <= MAX_PREGUNTA else t[:MAX_PREGUNTA - 1].rstrip() + "…"


def _hablando(s: Salida, carpeta: Path) -> dict:
    lectura = s.tipo == "lectura"      # solo la lectura muestra pregunta y cartas
    return {
        "clave": f"{s.user}|{s.tipo}|{s.ts.isoformat()}",
        "tipo": s.tipo,
        "nickname": s.nickname,
        "nivel": s.nivel if lectura else "",
        "signo": s.signo if lectura else "",
        "pregunta": _pregunta(s.pregunta) if lectura else "",
        "texto": s.texto,
        "cartas": [{"posicion": t.posicion, "id": t.carta.id, "nombre": t.carta.nombre,
                    "imagen": _imagen(t.carta.id, carpeta)} for t in s.cartas] if lectura else [],
    }


def vista(cola: Cola, worker: Worker, ahora: datetime, carpeta: Path = CARTAS) -> dict:
    """Todo lo que dibuja el overlay, en una sola respuesta. Sale al aire: no lleva usuarios,
    fechas de nacimiento ni preguntas que todavía no pasaron el filtro."""
    pendientes = cola.pendientes(ahora)
    actual = worker.actual
    return {
        "pausado": worker.pausado,
        "palabras_por_seg": worker.palabras_por_seg,
        "menu": [{"monedas": n.minimo, "nombre": n.nombre, "cartas": len(n.posiciones)}
                 for n in reversed(NIVELES) if n.en_menu],
        "turnos": [{"nickname": i.nickname, "nivel": nivel_para(i.valor).nombre, "falta": cola.falta(i),
                    "signo": i.dato.signo if i.dato else "", "pase": i.prioridad}
                   for i in pendientes[:MAX_TURNOS]],
        "en_cola": len(pendientes),
        "actual": {"nickname": actual.nickname, "nivel": actual.nivel} if actual else None,
        "hablando": _hablando(worker.hablando, carpeta) if worker.hablando else None,
        "boost": worker.boost.vista(ahora) if worker.boost else None,
    }
