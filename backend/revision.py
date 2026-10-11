"""Lee una bitácora y la resume por persona para la página de revisión."""
from __future__ import annotations
import json, re
from pathlib import Path

LOGS = Path(__file__).parent.parent / "logs"
NOMBRE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_bitacora\.jsonl$")
RESPUESTAS = ("lectura", "mensaje_fijo")


def sesiones(carpeta: Path = LOGS) -> list[str]:
    """Bitácoras guardadas, de la más reciente a la más antigua."""
    if not carpeta.is_dir():
        return []
    return sorted((p.name for p in carpeta.iterdir() if NOMBRE.match(p.name)), reverse=True)


def leer(nombre: str, carpeta: Path = LOGS) -> list[dict]:
    if not NOMBRE.match(nombre):                 # el nombre llega del navegador: solo archivos de bitácora
        raise ValueError("sesión inválida")
    entradas = []
    for linea in (carpeta / nombre).read_text(encoding="utf-8").splitlines():
        try:
            entradas.append(json.loads(linea))
        except json.JSONDecodeError:
            continue                             # una línea a medio escribir no tumba la revisión
    return entradas


def _estado(p: dict) -> tuple[str, str]:
    """Cómo terminó la persona y, si algo quedó mal, la alerta."""
    ev = p["eventos"]
    tipos = [e["tipo"] for e in ev]
    lecturas = [e for e in ev if e["tipo"] == "lectura"]
    pagas = [e for e in lecturas if e.get("nivel") != "Sí o no"]
    ultima_situacion = next((e["situacion"] for e in reversed(ev) if e.get("situacion")), "")
    if lecturas:
        estado = "Leída" if len(lecturas) == 1 else f"Leída {len(lecturas)} veces"
    elif "mensaje_fijo" in tipos:
        estado = "Se le dijo que no se lee"
    elif "sin_fecha" in tipos:
        estado = "Salió de la fila sin dar la fecha"
    elif ultima_situacion:
        estado = ultima_situacion
    elif p["monedas"]:
        estado = "Regaló y no escribió pregunta"
    else:
        estado = "Solo charla"
    alerta = ""
    en_espera = ultima_situacion.startswith(("En la fila", "Se le está leyendo"))   # el live sigue: aún puede leerse
    if en_espera and not lecturas:
        estado = ultima_situacion
    if p["monedas"] and not pagas and "mensaje_fijo" not in tipos and not en_espera:
        alerta = "Regaló y no se le leyó con su regalo"
    elif any(not e.get("pregunta") for e in pagas) and any(e.get("es") == "pregunta clara" for e in ev):
        alerta = "Se le leyó un mensaje general aunque escribió una pregunta"
    return estado, alerta


def resumen(entradas: list[dict]) -> dict:
    personas: dict[str, dict] = {}
    for e in entradas:
        p = personas.setdefault(e["user"], {"user": e["user"], "nickname": "", "monedas": 0, "lecturas": 0,
                                            "comentarios": 0, "signo": "", "eventos": []})
        p["nickname"] = e.get("nickname") or p["nickname"]
        p["monedas"] += e.get("valor", 0) if e["tipo"] == "regalo" else 0
        p["lecturas"] += e["tipo"] == "lectura"
        p["comentarios"] += e["tipo"] == "comentario"
        p["signo"] = e.get("signo") or p["signo"]
        ultimo = p["eventos"][-1] if p["eventos"] else None
        if (ultimo and e["tipo"] == "comentario" == ultimo["tipo"] and e.get("texto") == ultimo.get("texto")):
            ultimo["veces"] = ultimo.get("veces", 1) + 1       # el mismo mensaje repetido se cuenta, no se lista
            ultimo["situacion"] = e.get("situacion", ultimo.get("situacion", ""))
            continue
        p["eventos"].append({k: v for k, v in e.items() if k not in ("user", "nickname")})
    for p in personas.values():
        p["estado"], p["alerta"] = _estado(p)
    lista = sorted(personas.values(), key=lambda p: (not p["alerta"], -p["monedas"], -p["lecturas"], -p["comentarios"]))
    return {
        "personas": lista,
        "totales": {"personas": len(lista), "con_regalo": sum(1 for p in lista if p["monedas"]),
                    "monedas": sum(p["monedas"] for p in lista), "lecturas": sum(p["lecturas"] for p in lista),
                    "alertas": sum(1 for p in lista if p["alerta"])},
    }
