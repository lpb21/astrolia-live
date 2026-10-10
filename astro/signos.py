from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re, unicodedata
import swisseph as swe
from astro.cielo import SIGNOS, jd, longitud, signo_de

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
NOMBRES = {"aries": "Aries", "tauro": "Tauro", "geminis": "Géminis", "cancer": "Cáncer",
           "leo": "Leo", "virgo": "Virgo", "libra": "Libra", "escorpio": "Escorpio",
           "escorpion": "Escorpio", "sagitario": "Sagitario", "capricornio": "Capricornio",
           "acuario": "Acuario", "piscis": "Piscis"}
GLIFOS = {"♈": "Aries", "♉": "Tauro", "♊": "Géminis", "♋": "Cáncer", "♌": "Leo", "♍": "Virgo",
          "♎": "Libra", "♏": "Escorpio", "♐": "Sagitario", "♑": "Capricornio", "♒": "Acuario",
          "♓": "Piscis"}

FECHA_NUM = re.compile(r"\b(\d{1,2})\s*[/.\- ]\s*(\d{1,2})\s*[/.\- ]\s*(\d{4}|\d{2})\b")   # DD/MM/AA
FECHA_MES = re.compile(r"\b(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")(?:\s+(?:de|del)\s+(\d{4}))?")
EVENTO = re.compile(r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo|este|esta|"
                    r"proximo|para el|hasta el|el dia)\s*$")
# "Leo" también es nombre de persona: el signo en texto solo cuenta con "soy" o "signo"
# El signo en texto solo cuenta si es de quien pregunta: "soy aries", "soy de libra", "mi signo es leo"
SIGNO_TXT = re.compile(r"\b(?:soy|mi signo es|mi signo)\s+(?:de\s+)?(" + "|".join(NOMBRES) + r")\b")
# Un dato que aparece después de una referencia a un tercero es de ese tercero
TERCERO = re.compile(r"\b(mi|su|el|la) (ex|novio|novia|esposo|esposa|pareja|marido|mujer|hijo|hija|"
                     r"mama|papa|amante|crush|jefe|jefa|amigo|amiga|hermano|hermana)\b")
# Signo de la otra persona: "mi novio es aries", "mi ex es de signo leo", "él es cáncer"
SIGNO_PAREJA = re.compile(r"\b(?:es|signo)\s+(?:de\s+)?(?:signo\s+)?(" + "|".join(NOMBRES) + r")\b")
SIGNO_EL = re.compile(r"\b(?:el|ella)\s+es\s+(?:de\s+)?(?:signo\s+)?(" + "|".join(NOMBRES) + r")\b")

ELEMENTOS = ["fuego", "tierra", "aire", "agua"]
RELACIONES = {
    0: "mismo signo: se reconocen y se reflejan",
    1: "signos vecinos sin aspecto mayor: lenguajes distintos, requiere ajuste",
    2: "sextil: afines, fluye con poco esfuerzo",
    3: "cuadratura: tensión, atracción con roce",
    4: "trígono: mismo elemento, armonía natural",
    5: "quincuncio, sin aspecto mayor: lenguajes distintos, requiere ajuste",
    6: "oposición: complementarios, se atraen y chocan",
}


@dataclass
class DatoSigno:
    signo: str
    fecha: date | None
    en_cuspide: bool             # nació el día de cambio de signo; sin hora no se puede asegurar
    fuente: str                  # "fecha" | "nombre"


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _siglo(aa: int) -> int:
    return 1900 + aa if aa > date.today().year % 100 else 2000 + aa


def signo_por_fecha(f: date) -> tuple[str, bool]:
    """Signo al mediodía de Colombia; cúspide si el Sol cambia de signo en cualquier
    huso horario de ese día civil (UT-14 h a UT+36 h)."""
    base = datetime(f.year, f.month, f.day, tzinfo=timezone.utc)
    sol = lambda h: signo_de(longitud(jd(base + timedelta(hours=h)), swe.SUN)[0])
    return sol(17), sol(-14) != sol(36)


def es_menor(dato: DatoSigno | None, hoy: date) -> bool:
    """True si la fecha de nacimiento (con año) da menos de 18 años. Sin año no se puede saber."""
    if dato is None or dato.fecha is None:
        return False
    f = dato.fecha
    return hoy.year - f.year - ((hoy.month, hoy.day) < (f.month, f.day)) < 18


def _fechas(t: str) -> list[tuple[int, DatoSigno]]:
    """Fechas de nacimiento válidas del texto, con su posición, en orden de aparición."""
    hallados = []
    for m in FECHA_NUM.finditer(t):
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if len(m.group(3)) == 2:
            a = _siglo(a)
        try:
            f = date(a, mes, d)
        except ValueError:
            continue
        if f > date.today():
            continue
        s, c = signo_por_fecha(f)
        hallados.append((m.start(), DatoSigno(s, f, c, "fecha")))
    for m in FECHA_MES.finditer(t):
        if EVENTO.search(t[:m.start()]):
            continue                 # "este sábado 10 de octubre" es un evento, no un cumpleaños
        try:
            f = date(int(m.group(3) or 2000), MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            continue
        s, c = signo_por_fecha(f)
        hallados.append((m.start(), DatoSigno(s, f if m.group(3) else None, c, "fecha")))
    return sorted(hallados, key=lambda h: h[0])


def _corte(t: str) -> int:
    tercero = TERCERO.search(t)
    return tercero.start() if tercero else len(t)   # lo que va después de un tercero es de ese tercero


def extraer(texto: str) -> DatoSigno | None:
    """Dato de quien pregunta: la primera fecha, siempre que no venga después de un tercero."""
    t = _norm(texto)
    corte = _corte(t)

    for pos, dato in _fechas(t):
        if pos < corte:
            return dato
        break

    for glifo, signo in GLIFOS.items():
        pos = t.find(glifo)
        if 0 <= pos < corte:
            return DatoSigno(signo, None, False, "nombre")

    m = SIGNO_TXT.search(t)
    if m and m.start() < corte:
        return DatoSigno(NOMBRES[m.group(1)], None, False, "nombre")
    return None


def extraer_pareja(texto: str) -> DatoSigno | None:
    """Dato de la otra persona: la fecha que sigue a "mi ex / mi novio…" o, si no hay esa
    referencia, la segunda fecha del mensaje. Solo se conserva el signo, nunca su fecha."""
    t = _norm(texto)
    corte = _corte(t)
    fechas = _fechas(t)

    despues = [d for pos, d in fechas if pos >= corte]
    elegido = despues[0] if despues else (fechas[1][1] if len(fechas) >= 2 else None)
    if elegido:
        return DatoSigno(elegido.signo, None, elegido.en_cuspide, "fecha")

    m = SIGNO_PAREJA.search(t[corte:]) if corte < len(t) else SIGNO_EL.search(t)
    if m:
        return DatoSigno(NOMBRES[m.group(1)], None, False, "nombre")
    return None


def relacion(a: str, b: str) -> str:
    """Cómo se relacionan dos signos solares, según cuántos signos los separan."""
    ia, ib = SIGNOS.index(a), SIGNOS.index(b)
    sep = min((ia - ib) % 12, (ib - ia) % 12)
    elementos = f"{ELEMENTOS[ia % 4]} y {ELEMENTOS[ib % 4]}"
    return f"{RELACIONES[sep]} ({elementos})"
