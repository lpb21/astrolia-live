from __future__ import annotations
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from astro.signos import sin_fechas
from backend.cola import Cola
from backend.worker import Salida, Worker
from tarot.tirada import NIVELES, nivel_para

TAROT = Path(__file__).parent.parent / "tarot"
# Dónde busca el overlay la imagen de cada carta, en orden, con la ruta web de cada carpeta:
# primero las preparadas para el live (tools/preparar_cartas.py) y, si esa carta no está, la original.
CARPETAS = (("cartas", TAROT / "img_live"), ("cartas-originales", TAROT / "img"))
FORMATOS = (".webp", ".png", ".jpg", ".jpeg")
MAX_TURNOS = 5
# Regalos que tienen animación propia del avatar (overlay: videos/<clip>.mp4), por su nombre en TikTok
CLIP_REGALO = {"rose": "rosa", "doughnut": "rosquilla"}
VIGENCIA_EFECTO = timedelta(seconds=12)      # pasado ese rato ya no se anima: llegaría fuera de lugar
MAX_PREGUNTA = 110


class Efectos:
    """Animaciones de regalo pendientes de mostrarse. El overlay las ve en cada consulta y no repite un id."""

    def __init__(self):
        self._lista: deque[dict] = deque(maxlen=30)
        self._n = 0

    def regalo(self, nombre: str, ts: datetime) -> None:
        clip = CLIP_REGALO.get(nombre.strip().lower())
        if clip:
            self._n += 1
            self._lista.append({"id": self._n, "clip": clip, "ts": ts})

    def recientes(self, ahora: datetime) -> list[dict]:
        return [{"id": e["id"], "clip": e["clip"]} for e in self._lista if ahora - e["ts"] <= VIGENCIA_EFECTO]


def _imagen(carta_id: str, carpetas=CARPETAS) -> str | None:
    """Ruta web de la imagen de la carta, si existe; el nombre del archivo es el id."""
    for ruta_web, carpeta in carpetas:
        for ext in FORMATOS:
            if (carpeta / f"{carta_id}{ext}").is_file():
                return f"{ruta_web}/{carta_id}{ext}"
    return None


def _pregunta(texto: str) -> str:
    """La pregunta como se muestra en pantalla: sin fechas de nacimiento y recortada."""
    t = sin_fechas(texto)
    return t if len(t) <= MAX_PREGUNTA else t[:MAX_PREGUNTA - 1].rstrip() + "…"


def _hablando(s: Salida, carpetas) -> dict:
    lectura = s.tipo in ("lectura", "carta_momento")      # solo estas muestran cartas (y la lectura, pregunta)
    return {
        "clave": f"{s.user}|{s.tipo}|{s.ts.isoformat()}",
        "tipo": s.tipo,
        "nickname": s.nickname,
        "nivel": s.nivel if lectura else "",
        "signo": s.signo if lectura else "",
        "pregunta": _pregunta(s.pregunta) if lectura else "",
        "texto": s.texto,
        # Con voz: los trozos ya sintetizados (texto, audio y duración real) y si ya están todos
        "trozos": [{"texto": t["texto"], "audio": f"audio/{t['audio']}.wav", "dur": t["dur"]} for t in s.trozos],
        "completo": s.completo,
        "cartas": [{"posicion": t.posicion, "id": t.carta.id, "nombre": t.carta.nombre,
                    "imagen": _imagen(t.carta.id, carpetas)} for t in s.cartas] if lectura else [],
    }


def vista(cola: Cola, worker: Worker, ahora: datetime, carpeta: Path | None = None) -> dict:
    """Todo lo que dibuja el overlay, en una sola respuesta. Sale al aire: no lleva usuarios,
    fechas de nacimiento ni preguntas que todavía no pasaron el filtro."""
    carpetas = (("cartas", carpeta),) if carpeta else CARPETAS      # `carpeta`: solo para pruebas
    pendientes = cola.pendientes(ahora)
    actual = worker.actual
    return {
        "pausado": worker.pausado,
        "palabras_por_seg": worker.palabras_por_seg,
        "menu": [{"monedas": n.minimo, "regalo": n.regalo, "nombre": n.nombre, "cartas": len(n.posiciones)}
                 for n in reversed(NIVELES) if n.en_menu],
        "turnos": [{"nickname": i.nickname, "nivel": nivel_para(i.valor).nombre, "falta": cola.falta(i),
                    # segundos que le quedan para escribir su pregunta a quien regaló sin preguntar
                    "restante": (max(round((cola.espera_pregunta - (ahora - i.ts)).total_seconds()), 0)
                                 if not i.pregunta else None),
                    "signo": i.dato.signo if i.dato else "", "pase": i.prioridad}
                   for i in pendientes[:MAX_TURNOS]],
        "en_cola": len(pendientes),
        "actual": {"nickname": actual.nickname, "nivel": actual.nivel} if actual else None,
        "hablando": _hablando(worker.hablando, carpetas) if worker.hablando else None,
        "boost": worker.boost.vista(ahora) if worker.boost else None,
        "cartel": cola.cartel(ahora),
    }
