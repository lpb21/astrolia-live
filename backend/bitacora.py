"""Bitácora del live: una línea JSON por cada cosa que llega del chat y por cada decisión que
toma el sistema, para revisar después persona por persona (página /revision/). Solo se escribe
cuando la app la abre; en los tests y scripts no deja archivos."""
from __future__ import annotations
import json, logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("bitacora")
log.setLevel(logging.INFO)
log.propagate = False            # no va a la consola ni a backend.log


_abiertas: list[logging.Handler] = []


def abrir(archivo: Path) -> logging.Handler:
    manejador = logging.FileHandler(archivo, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(manejador)
    _abiertas.append(manejador)
    return manejador


def cerrar(manejador: logging.Handler) -> None:
    log.removeHandler(manejador)
    _abiertas.remove(manejador)
    manejador.close()


def anotar(tipo: str, user: str, nickname: str = "", ts: datetime | None = None, **datos) -> None:
    if not _abiertas or not user:
        return
    entrada = {"ts": (ts or datetime.now(timezone.utc)).isoformat(), "tipo": tipo, "user": user, "nickname": nickname}
    entrada.update({k: v for k, v in datos.items() if v not in ("", None, [], False)})
    log.info(json.dumps(entrada, ensure_ascii=False))
