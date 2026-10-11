from __future__ import annotations
from dataclasses import dataclass
import random
from tarot.mazo import MAZO, Carta

TIEMPOS = ("pasado", "presente", "futuro")


@dataclass(frozen=True)
class Nivel:
    minimo: int                     # monedas totales del turno desde las que aplica
    nombre: str
    posiciones: tuple[str, ...]
    en_menu: bool = False           # se muestra en el menú del overlay
    segunda_pregunta: bool = False  # responde también la primera pregunta adicional
    ritual: bool = False            # PENDIENTE: falta el catálogo de rituales de Caro
    triada: bool = False            # PENDIENTE: solar, lunar y ascendente (pide hora y ciudad)


# De mayor a menor: gana el primer nivel cuyo mínimo alcanza el valor del turno.
# PROVISIONAL: los cortes los confirma Caro con los precios reales de los regalos.
NIVELES: tuple[Nivel, ...] = (
    Nivel(200, "Lectura maestra", TIEMPOS + ("obstáculo", "lo oculto", "consejo"),
          en_menu=True, segunda_pregunta=True, ritual=True, triada=True),
    Nivel(100, "Lectura completa", TIEMPOS + ("obstáculo", "lo oculto", "consejo"),
          en_menu=True, segunda_pregunta=True, ritual=True),
    Nivel(50, "Lectura profunda", TIEMPOS + ("obstáculo", "consejo"), segunda_pregunta=True, ritual=True),
    Nivel(30, "Lectura doble", TIEMPOS + ("consejo",), en_menu=True, segunda_pregunta=True, ritual=True),
    Nivel(20, "Lectura con ritual", TIEMPOS + ("consejo",), ritual=True),
    Nivel(10, "Tres tiempos con consejo", TIEMPOS + ("consejo",), en_menu=True),
    Nivel(5, "Tres tiempos", TIEMPOS, en_menu=True),
    Nivel(1, "Mensaje del oráculo", ("mensaje",), en_menu=True),
    Nivel(0, "Sí o no", ("respuesta",), en_menu=True),      # turno gratis
)

_azar = random.SystemRandom()


@dataclass(frozen=True)
class CartaTirada:
    posicion: str
    carta: Carta


def nivel_para(valor: int) -> Nivel:
    for nivel in NIVELES:
        if valor >= nivel.minimo:
            return nivel
    return NIVELES[-1]


def posiciones_para(valor: int) -> tuple[str, ...]:
    return nivel_para(valor).posiciones


def tirar(valor: int, rng: random.Random | None = None) -> list[CartaTirada]:
    """Saca del mazo, sin repetir, una carta por cada posición que corresponde al valor del turno."""
    posiciones = posiciones_para(valor)
    cartas = (rng or _azar).sample(MAZO, len(posiciones))
    return [CartaTirada(p, c) for p, c in zip(posiciones, cartas)]
