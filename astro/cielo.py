from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import swisseph as swe

swe.set_ephe_path(str(Path(__file__).parent / "ephe"))

SIGNOS = ["Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo", "Libra",
          "Escorpio", "Sagitario", "Capricornio", "Acuario", "Piscis"]
PLANETAS = {"Sol": swe.SUN, "Luna": swe.MOON, "Mercurio": swe.MERCURY, "Venus": swe.VENUS,
            "Marte": swe.MARS, "Júpiter": swe.JUPITER, "Saturno": swe.SATURN,
            "Urano": swe.URANUS, "Neptuno": swe.NEPTUNE, "Plutón": swe.PLUTO}
ASPECTOS = {"conjunción": (0, 8), "sextil": (60, 5), "cuadratura": (90, 7),
            "trígono": (120, 7), "oposición": (180, 8)}   # (ángulo, orbe)
FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED
FASES = ["Luna nueva", "Creciente", "Cuarto creciente", "Gibosa creciente",
         "Luna llena", "Gibosa menguante", "Cuarto menguante", "Menguante"]


def jd(momento: datetime) -> float:
    m = momento.astimezone(timezone.utc)
    return swe.julday(m.year, m.month, m.day, m.hour + m.minute / 60 + m.second / 3600)


def longitud(jd_ut: float, planeta: int) -> tuple[float, float]:
    xx, _ = swe.calc_ut(jd_ut, planeta, FLAGS)
    return xx[0], xx[3]          # longitud eclíptica, velocidad diaria


def signo_de(lon: float) -> str:
    return SIGNOS[int(lon // 30) % 12]


@dataclass
class Posicion:
    planeta: str
    lon: float
    signo: str
    grado: float
    retrogrado: bool


@dataclass
class Aspecto:
    a: str
    b: str
    tipo: str
    orbe: float


@dataclass
class Cielo:
    momento: datetime
    posiciones: dict[str, Posicion]
    aspectos: list[Aspecto]
    fase_lunar: float            # elongación Luna-Sol en grados
    nombre_fase: str

    def casas_solares(self, signo: str) -> dict[str, int]:
        """Casa (signo entero) que ocupa cada planeta contando desde el signo solar."""
        base = SIGNOS.index(signo)
        return {p.planeta: (SIGNOS.index(p.signo) - base) % 12 + 1
                for p in self.posiciones.values()}


def cielo(momento: datetime) -> Cielo:
    j = jd(momento)
    pos: dict[str, Posicion] = {}
    for nombre, p in PLANETAS.items():
        lon, vel = longitud(j, p)
        pos[nombre] = Posicion(nombre, round(lon, 4), signo_de(lon), round(lon % 30, 2), vel < 0)

    aspectos = []
    nombres = list(pos)
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            d = abs(pos[a].lon - pos[b].lon) % 360
            d = min(d, 360 - d)
            for tipo, (angulo, orbe) in ASPECTOS.items():
                if abs(d - angulo) <= orbe:
                    aspectos.append(Aspecto(a, b, tipo, round(abs(d - angulo), 2)))

    fase = (pos["Luna"].lon - pos["Sol"].lon) % 360
    nombre_fase = FASES[int(((fase + 22.5) % 360) // 45)]
    return Cielo(momento, pos, sorted(aspectos, key=lambda x: x.orbe), round(fase, 2), nombre_fase)