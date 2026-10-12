from __future__ import annotations
from dataclasses import dataclass
import re, unicodedata

# acción: "saltar" | "mensaje_fijo" | "con_regalo" | "permitir"
ACCIONES = {
    "crisis": "mensaje_fijo",
    "salud": "mensaje_fijo",
    "embarazo": "con_regalo",      # se lee solo con un regalo de MINIMO monedas o más
    "menor": "saltar",
    "violencia": "mensaje_fijo",
    "brujeria": "saltar",
    "dinero_legal": "saltar",
    "acusacion": "saltar",
}

# Temas que se leen solo desde cierto regalo (30 monedas = una rosquilla/Doughnut)
MINIMO = {"embarazo": 30}

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
    ("salud", re.compile(r"desma[yl]|corazon (le |me )?late|enferm|hospital|sintoma|diagnost|"
                         r"cirugia|convulsi|tumor|dolor(es)? (de|en)\b|me duele|quimio|radioterapia|metastasis|"
                         r"\bmi salud\b|\bde salud\b|\basma\b|disnea|diabet|infarto")),
    ("embarazo", re.compile(r"embaraz|aborto|aborta|sera (mama|papa)\b|nena o varon|varon o (nena|nina)|nino o nina")),
    ("violencia", re.compile(r"me pega|me golpea|maltrat|abus|me amenaza|violencia|corre peligro|en peligro\b")),
    ("menor", re.compile(r"\btengo 1[0-7] anos|\bmi (papa|mama|papi|mami) (me|no me)|colegio|"
                         r"\bgrado\b|mis papas")),
    ("brujeria", re.compile(r"brujeria|hechizo|amarre|le hizo (un )?trabajo|me hicieron (un )?trabajo|"
                            r"le hicieron (un )?trabajo|endulzamiento")),
    # Señalar a una persona como culpable de un robo o un chisme no lo deciden las cartas
    ("acusacion", re.compile(r"quien (fue|me robo|me lo robo|lo hizo|me hizo)|quienes? (son|fueron)\b|"
                             r"me robaron|me robo\b|me quitaron (un |el |mi |la |una )?(dinero|plata|celular|cartera)")),
    ("dinero_legal", re.compile(r"\blegal(es)?\b|notari|herencia|\bdemanda\b|\bdemandar|"
                                r"(?<!perdio el )(?<!perdi el )(?<!pierde el )\bjuicio\b|"
                                r"abogad|loteria|invertir|inversion|(?<!sin )\bembarg|divorcio")),
]

# "cáncer" es signo o enfermedad según lo que lo rodea; se decide por cada aparición
_CANCER = re.compile(r"\bcancer\b")
_CANCER_SIGNO = re.compile(r"(?:\b(?:soy|signo|en|ascendente|los|las|hombres?|mujer(?:es)?|novi[oa]|chic[oa]|"
                           r"espos[oa]|ex|pareja)(?: de| del signo| es| en)?\s+|\(\s*)$")
_CANCER_ES = re.compile(r"\bes(?: de)?\s+$")                  # "él es cáncer" / "lo que tiene es cáncer"
_CANCER_TIENE = re.compile(r"\b(?:tien\w+|tengo|tenga|tuv[eo]|padec\w+|sufr\w+ de|detectaron|"
                           r"contra el|paciente de)\s+$")
_CANCER_DUDOSO = re.compile(r"\b(?:el|un|del|de|con|por|mi|su)\s+$")
_CANCER_ORGANO = re.compile(r"^\s+(?:de (?:mama|seno|piel|prostata|utero|pulmon|colon|estomago|higado|"
                            r"garganta|tiroides|sangre|hueso)|en (?:el|la|mi|su)\b|terminal|maligno)")
_MEDICO = re.compile(r"\bcur[ae]|\bsana|terminal|maligno|tratamiento|paciente|\bmuri|falleci|etapa|\boper")
_MEDICO_VAGO = re.compile(r"mejor|super|\bvenc|\bluch|quitar")


def _cancer_enfermedad(t: str) -> str:
    """Devuelve el fragmento que delata la enfermedad, o "" si cada "cáncer" es el signo."""
    for m in _CANCER.finditer(t):
        antes, despues = t[:m.start()], t[m.end():]
        if _CANCER_SIGNO.search(antes):
            continue
        if _CANCER_ES.search(antes) and not _MEDICO.search(t):
            continue
        pista = (_CANCER_TIENE.search(antes) or _CANCER_ORGANO.search(despues)
                 or (_CANCER_ES.search(antes) and _MEDICO.search(t)))
        if not pista and _CANCER_DUDOSO.search(antes):
            pista = _MEDICO.search(t) or _MEDICO_VAGO.search(t)
        if pista:
            return t[max(0, m.start() - 12):m.end() + 12].strip()
    return ""


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
        termino = m.group(0) if m else (_cancer_enfermedad(t) if categoria == "salud" else "")
        if termino:
            accion = ACCIONES.get(categoria, "saltar")
            if accion == "permitir":
                continue
            return Resultado(True, categoria, accion, termino, MENSAJES.get(categoria, ""))
    return Resultado(False)