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
    regalo: str = ""                # el regalo de TikTok que alcanza este nivel, como se anuncia en el menú
    segunda_pregunta: bool = False  # responde también la primera pregunta adicional
    ritual: bool = False            # PENDIENTE: falta el catálogo de rituales de Caro
    triada: bool = False            # PENDIENTE: solar, lunar y ascendente (pide hora y ciudad)


# De mayor a menor: gana el primer nivel cuyo mínimo alcanza el valor del turno.
# Los cortes del menú coinciden con el precio de un regalo real (vistos en los logs de octubre de 2026:
# Rose 1, Finger Heart 5, Doughnut 30, Singing Mushroom 99, Confetti y Hand Heart 100, Dancing Hands 199).
# Por eso los dos más altos son 99 y 199, y no 100 y 200: con 100 y 200 esos regalos se quedaban un nivel abajo.
# Precios cotejados el 12-oct-2026 con el catálogo de Colombia: https://beetgames.com/es/tiktok-gifts/co/
# (ahí también: Rosa 10, Perfume 20; no hay regalos de 50 monedas).
# PROVISIONAL: los nombres en español de `regalo` los confirma Caro contra el panel de regalos de su app.
NIVELES: tuple[Nivel, ...] = (
    Nivel(199, "Lectura maestra", TIEMPOS + ("obstáculo", "lo oculto", "consejo"),
          en_menu=True, regalo="🙌 Manos bailando", segunda_pregunta=True, ritual=True, triada=True),
    Nivel(99, "Lectura completa", TIEMPOS + ("obstáculo", "lo oculto", "consejo"),
          en_menu=True, regalo="🎉 Confeti", segunda_pregunta=True, ritual=True),
    Nivel(50, "Lectura profunda", TIEMPOS + ("obstáculo", "consejo"), segunda_pregunta=True, ritual=True),
    Nivel(30, "Lectura doble", TIEMPOS + ("consejo",), en_menu=True, regalo="🍩 Rosquilla", segunda_pregunta=True, ritual=True),
    Nivel(20, "Lectura con ritual", TIEMPOS + ("consejo",), ritual=True),
    Nivel(10, "Tres tiempos con consejo", TIEMPOS + ("consejo",), en_menu=True, regalo="🌹 10 Rosas"),
    Nivel(5, "Tres tiempos", TIEMPOS, en_menu=True, regalo="🫰 Corazón de dedos"),
    Nivel(1, "Mensaje del oráculo", ("mensaje",), en_menu=True, regalo="🌹 Rosa"),
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
