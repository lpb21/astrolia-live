from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json

# PROVISIONAL: las "claves" de mazo.json son significados genéricos. Caro las reemplaza por
# los suyos editando ese archivo; no hay cartas invertidas.
ARCHIVO = Path(__file__).parent / "mazo.json"


@dataclass(frozen=True)
class Carta:
    id: str                 # también es el nombre del archivo de imagen: "la-torre", "sota-espadas"
    nombre: str
    arcano: str             # "mayor" | "menor"
    palo: str | None        # bastos | copas | espadas | oros; None en los arcanos mayores
    numero: int             # 0-21 en mayores; 1-14 en menores (11 Sota, 12 Caballo, 13 Reina, 14 Rey)
    claves: str


def cargar(archivo: Path = ARCHIVO) -> tuple[Carta, ...]:
    cartas = tuple(Carta(**c) for c in json.loads(archivo.read_text(encoding="utf-8")))
    if len(cartas) != 78 or len({c.id for c in cartas}) != 78:
        raise ValueError(f"{archivo.name} debe tener 78 cartas distintas y tiene {len(cartas)}")
    return cartas


MAZO = cargar()
