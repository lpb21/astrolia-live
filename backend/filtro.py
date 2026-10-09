from __future__ import annotations
from dataclasses import dataclass
import re, unicodedata

# acción: "saltar" | "mensaje_fijo" | "permitir"
ACCIONES = {
    "crisis": "mensaje_fijo",
    "salud": "mensaje_fijo",
    "embarazo": "saltar",
    "menor": "saltar",
    "violencia": "mensaje_fijo",
    "brujeria": "saltar",
    "dinero_legal": "saltar",
}

MENSAJES = {
    "crisis": "Si estás pasando por un momento muy difícil, busca ahora a alguien de confianza "
              "o una línea de ayuda de tu país. No estás sola ni solo.",
    "salud": "Esta pregunta necesita a un profesional de salud, no a los astros. "
             "Si es urgente, acude a un servicio médico ya.",
    "violencia": "Tu seguridad es lo primero. Busca apoyo con alguien de confianza "
                 "o con las autoridades de tu país.",
}

# orden = prioridad: la primera categoría que coincide gana
PATRONES: list[tuple[str, re.Pattern]] = [
    ("crisis", re.compile(r"suicid|matarme|quitarme la vida|no quiero vivir|hacerme dano|cortarme|morirme")),
    ("salud", re.compile(r"desma[yl]|corazon (le |me )?late|enferm|cancer|hospital|sintoma|diagnost|"
                         r"operacion|cirugia|medico|doctor|convulsi|tumor|dolor de")),
    ("embarazo", re.compile(r"embaraz|aborto|aborta")),
    ("violencia", re.compile(r"me pega|me golpea|maltrat|abus|me amenaza|violencia")),
    ("menor", re.compile(r"\btengo 1[0-7] anos|\bmi (papa|mama|papi|mami) (me|no me)|colegio|"
                         r"profesora?\b|\bgrado\b|mis papas")),
    ("brujeria", re.compile(r"brujeria|hechizo|amarre|le hizo (un )?trabajo|me hicieron (un )?trabajo|"
                            r"le hicieron (un )?trabajo|endulzamiento")),
    ("dinero_legal", re.compile(r"herencia|demanda|juicio|abogad|loteria|chance|invertir|inversion|"
                                r"deuda|embargo|divorcio")),
]


@dataclass
class Resultado:
    sensible: bool
    categoria: str = ""
    accion: str = "permitir"
    termino: str = ""
    mensaje: str = ""


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def evaluar(texto: str) -> Resultado:
    t = _norm(texto)
    for categoria, patron in PATRONES:
        m = patron.search(t)
        if m:
            accion = ACCIONES.get(categoria, "saltar")
            if accion == "permitir":
                continue
            return Resultado(True, categoria, accion, m.group(0), MENSAJES.get(categoria, ""))
    return Resultado(False)