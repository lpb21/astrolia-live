from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re, unicodedata
import swisseph as swe
from astro.cielo import jd, longitud, signo_de

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
SIGNO_TXT = re.compile(r"\b(?:soy|signo)\s+(?:de\s+)?(" + "|".join(NOMBRES) + r")\b")


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


def extraer(texto: str) -> DatoSigno | None:
    t = _norm(texto)

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
        return DatoSigno(s, f, c, "fecha")

    for m in FECHA_MES.finditer(t):
        if EVENTO.search(t[:m.start()]):
            continue                 # "este sábado 10 de octubre" es un evento, no un cumpleaños
        try:
            f = date(int(m.group(3) or 2000), MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            continue
        s, c = signo_por_fecha(f)
        return DatoSigno(s, f if m.group(3) else None, c, "fecha")

    for glifo, signo in GLIFOS.items():
        if glifo in texto:
            return DatoSigno(signo, None, False, "nombre")

    m = SIGNO_TXT.search(t)
    if m:
        return DatoSigno(NOMBRES[m.group(1)], None, False, "nombre")
    return None