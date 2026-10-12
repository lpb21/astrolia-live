from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re, unicodedata
import swisseph as swe
from astro.cielo import SIGNOS, jd, longitud, signo_de

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
# Mes abreviado ("19 feb 94") y mes antes del día ("junio 11 90"); solo cuentan con día y año
_ABREV = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "sept": 9,
          "set": 9, "oct": 10, "nov": 11, "dic": 12}
NOMBRES = {"aries": "Aries", "tauro": "Tauro", "geminis": "Géminis", "cancer": "Cáncer",
           "leo": "Leo", "virgo": "Virgo", "libra": "Libra", "escorpio": "Escorpio",
           "escorpion": "Escorpio", "sagitario": "Sagitario", "capricornio": "Capricornio",
           "acuario": "Acuario", "piscis": "Piscis"}
GLIFOS = {"♈": "Aries", "♉": "Tauro", "♊": "Géminis", "♋": "Cáncer", "♌": "Leo", "♍": "Virgo",
          "♎": "Libra", "♏": "Escorpio", "♐": "Sagitario", "♑": "Capricornio", "♒": "Acuario",
          "♓": "Piscis"}

# DD/MM/AA con los separadores que usa la gente en el chat, incluido el apóstrofo: 30'06'08.
# El año puede venir pegado a la palabra siguiente ("30'06'08Puedes decirme").
_SEP = r"\s*[/.\-_ ;'’´`]\s*"
FECHA_NUM = re.compile(r"\b(\d{1,2})" + _SEP + r"(\d{1,2})" + _SEP + r"(\d{4}|\d{2})(?!\d)")
# Fechas escritas de corrido, como llegan del chat: "08112007", "050489", "05 0489"
FECHA_PEGADA = re.compile(r"\b(\d{2})(\d{2})((?:19|20)\d{2}|\d{2})\b|\b(\d{1,2})[/.\-_ ](\d{2})(\d{2})\b")
FECHA_MES = re.compile(r"\b(\d{1,2})\s+(?:de\s+)?(" + "|".join(MESES) + r")\b(?:\s+(?:de\s+|del\s+)?(\d{4}|\d{2})\b)?")
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


FECHA_ABREV = re.compile(r"\b(\d{1,2})\s+(?:de\s+)?(" + "|".join(_ABREV) + r")\.?\s+(?:de\s+|del\s+)?(\d{4}|\d{2})(?!\d)")
FECHA_MES_DIA = re.compile(r"\b(" + "|".join(MESES) + r")\s+(\d{1,2})\s*,?\s+(?:de\s+|del\s+)?(\d{4}|\d{2})(?!\d)")


def _tapar(m: re.Match) -> str:
    return " " * len(m.group(0))      # conserva las posiciones del texto


def sin_fechas(texto: str) -> str:
    """El texto sin fechas de nacimiento, para mostrarlo en pantalla o buscarle la pregunta."""
    for patron in (FECHA_NUM, FECHA_PEGADA, FECHA_ABREV, FECHA_MES_DIA):
        texto = patron.sub(" ", texto)
    return " ".join(texto.split())


def _fechas(t: str) -> list[tuple[int, DatoSigno]]:
    """Fechas de nacimiento válidas del texto, con su posición, en orden de aparición."""
    hallados = []
    numericas = [m.groups() + (m.start(),) for m in FECHA_NUM.finditer(t)]
    numericas += [tuple(g for g in m.groups() if g) + (m.start(),) for m in FECHA_PEGADA.finditer(FECHA_NUM.sub(_tapar, t))]
    for g1, g2, g3, pos in numericas:
        d, mes, a = int(g1), int(g2), int(g3)
        if len(g3) == 2:
            a = _siglo(a)
        if mes > 12 >= d:
            d, mes = mes, d              # 12/30/82: escrito al estilo mes/día
        try:
            f = date(a, mes, d)
        except ValueError:
            continue
        if f > date.today():
            continue
        s, c = signo_por_fecha(f)
        hallados.append((pos, DatoSigno(s, f, c, "fecha")))
    tomadas = [m.span() for m in FECHA_MES.finditer(t)]
    for patron, orden in ((FECHA_ABREV, (1, 2, 3)), (FECHA_MES_DIA, (2, 1, 3))):
        for m in patron.finditer(t):
            if any(a < m.end() and m.start() < b for a, b in tomadas) or EVENTO.search(t[:m.start()]):
                continue
            d, mes, a = (m.group(i) for i in orden)
            try:
                f = date(_siglo(int(a)) if len(a) == 2 else int(a), {**MESES, **_ABREV}[mes], int(d))
            except ValueError:
                continue
            if f <= date.today():
                s, c = signo_por_fecha(f)
                hallados.append((m.start(), DatoSigno(s, f, c, "fecha")))
    for m in FECHA_MES.finditer(t):
        if EVENTO.search(t[:m.start()]):
            continue                 # "este sábado 10 de octubre" es un evento, no un cumpleaños
        try:
            anio = int(m.group(3) or 2000)
            f = date(_siglo(anio) if m.group(3) and len(m.group(3)) == 2 else anio, MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            continue
        s, c = signo_por_fecha(f)
        hallados.append((m.start(), DatoSigno(s, f if m.group(3) else None, c, "fecha")))
    return sorted(hallados, key=lambda h: h[0])


def _corte(t: str) -> int:
    tercero = TERCERO.search(t)
    return tercero.start() if tercero else len(t)   # lo que va después de un tercero es de ese tercero


# Respuestas a medias a "¿cuál es tu fecha de nacimiento?": solo el año o solo el mes
ANIO_SOLO = re.compile(r"\b(?:del?|ano|en|en el)\s+(?:ano\s+)?((?:19[3-9]\d|20[01]\d)|[3-9]\d)\b(?!\s*(?:anos|likes|monedas))")
MES_SOLO = re.compile(r"\b(?:soy|naci|nacida|nacido|cumplo|cumpleanos)\b.{0,25}\b(" + "|".join(MESES) + r")\b"
                      r"|\b(" + "|".join(MESES) + r")\s+(?:de|del)\s+(?:19|20)\d{2}\b"
                      r"|^\W*(?:\w+\W+){0,2}(?:de |en )?(" + "|".join(MESES) + r")\W*$")


def fecha_incompleta(texto: str) -> str | None:
    """Qué dio la persona cuando no alcanza para saber su signo: "mes" (falta el día) o
    "anio" (faltan día y mes). None si el texto trae la fecha o no habla de eso."""
    t = _norm(texto)
    if _fechas(t) or SIGNO_TXT.search(t) or any(g in t for g in GLIFOS):
        return None
    corte = _corte(t)
    m = MES_SOLO.search(t)
    if m and m.start() < corte:
        return "mes"
    m = ANIO_SOLO.search(t)
    return "anio" if m and m.start() < corte else None


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


# ---------- ¿de quién es la fecha? ----------
@dataclass
class Reparto:
    propio: DatoSigno | None             # dato de quien pregunta
    pareja: DatoSigno | None             # dato de la otra persona (solo el signo)
    dudosa: DatoSigno | None = None      # hay una fecha y no se sabe de cuál de los dos es
    de_pareja: bool = False              # la única fecha del mensaje resultó ser de la otra persona


_PRESENTACION = re.compile(r"\b(soy|me llamo|mi nombre es|mi fecha|naci|yo)\b")
_DOS_PERSONAS_ANTES = re.compile(r"\bentre\b|\by\s+[a-zñ]+(\s+[a-zñ]+){0,2}\s*$")
_DOS_PERSONAS_DESPUES = re.compile(r"^[\d\s/.\-_'’´`]*(\s*[a-zñ]+){0,2}\s*,?\s+y\s+[a-zñ]")
_RESPUESTA_SUYA = re.compile(r"\bno es (la )?mia\b|\bde (el|ella|la otra persona)\b|\bsuy[ao]\b|"
                             r"\bde mi (pareja|novi[oa]|espos[oa]|ex|marido|mujer)\b|^(es )?(la )?de (?!mi\b)[a-zñ]+$")
_RESPUESTA_MIA = re.compile(r"\b(mia|mio)\b|\bmi fecha\b|^(es )?(la )?de mi$|^(si )?yo$")


def _junto_a(t: str, pos: int) -> set[str]:
    """Palabras pegadas a la fecha (el nombre de quien es), sin cruzar una "y" ni una coma."""
    antes = re.split(r"\s+y\s+|,", t[:pos])[-1]
    despues = re.split(r"(?:^|\s+)y\s+|,", re.sub(r"^[\d\s/.\-_'’´`]+", " ", t[pos:pos + 45]))[0]
    return set(re.findall(r"[a-zñ]{4,}", antes)[-3:]) | set(re.findall(r"[a-zñ]{4,}", despues)[:2])


def repartir(texto: str, nickname: str = "", user: str = "") -> Reparto:
    """Como extraer + extraer_pareja, pero mirando junto a qué nombre está cada fecha y cómo se
    llama la cuenta que escribe. "cómo se ven las cosas entre Carmen 12-10-93 y Fernando", escrito
    por Fernando: la fecha es de Carmen. Si no hay cómo saberlo, la fecha queda como dudosa."""
    r = Reparto(extraer(texto), extraer_pareja(texto))
    t = _norm(texto)
    fechas = [(pos, d) for pos, d in _fechas(t) if pos < _corte(t)]
    if r.propio is None or r.propio.fuente != "fecha" or not fechas:
        return r
    cuenta = re.sub(r"[^a-zñ]", "", _norm(f"{nickname}{user}"))
    es_suya = [any(p in cuenta for p in _junto_a(t, pos)) for pos, _ in fechas]
    solo_signo = lambda d: DatoSigno(d.signo, None, d.en_cuspide, "fecha")

    if len(fechas) >= 2:
        tramo = lambda i: re.split(r"\s+y\s+|,", t[fechas[i - 1][0] if i else 0:fechas[i][0]])[-1]
        se_presenta = [bool(_PRESENTACION.search(tramo(i))) for i in (0, 1)]
        if (es_suya[1] and not es_suya[0]) or (se_presenta[1] and not se_presenta[0]):
            # "Cristian 11/10/99 y Luisa 23/12/00", escribe Luisa; o "…11 junio 1985, me llamo Ricardo 17;04 89"
            r.propio, r.pareja = fechas[1][1], solo_signo(fechas[0][1])
        return r
    pos, dato = fechas[0]
    tramos = re.split(r"\s+y\s+|,", t[:pos])
    if es_suya[0] or _PRESENTACION.search(tramos[-1]):
        return r                                      # "soy Ana 05/05/90…" o la fecha va junto a su nombre
    if _PRESENTACION.search(" ".join(tramos[:-1])) and re.search(r"[a-zñ]{4,}", tramos[-1]):
        # "soy Lesly, Simón Velásquez 28-2-96 regresará…": se presentó aparte; la fecha va con el otro nombre
        return Reparto(None, solo_signo(dato), de_pareja=True)
    nombres_cuenta = [p for p in re.findall(r"[a-zñ]{4,}", _norm(nickname)) if re.search(rf"\b{p}\b", t)]
    if nombres_cuenta and _junto_a(t, pos):
        # Su nombre está en el mensaje, pero lejos de la fecha: la fecha es de la otra persona
        return Reparto(None, solo_signo(dato), de_pareja=True)
    antes = [p for p in re.findall(r"[a-zñ]+", t[:pos]) if p not in ("hola", "buenas", "buenos", "dias", "tardes", "noches")]
    if len(antes) <= 3 and not _DOS_PERSONAS_ANTES.search(t[:pos]):
        return r                                      # "Ana 05/05/90 y Juan…": nombre y fecha al empezar, es la suya
    if _DOS_PERSONAS_ANTES.search(t[:pos]) or _DOS_PERSONAS_DESPUES.search(t[pos:]):
        return Reparto(None, r.pareja, dudosa=dato)   # dos personas, una fecha y nada que diga de quién es
    return r


def respuesta_duda(texto: str) -> str | None:
    """Lo que contesta la persona a "¿esa fecha es tuya o de la otra persona?": "propia" o "pareja"."""
    t = re.sub(r"[^a-zñ ]", " ", _norm(texto)).strip()
    t = " ".join(t.split())
    if not t or len(t.split()) > 7:
        return None
    if _RESPUESTA_SUYA.search(t):
        return "pareja"
    return "propia" if _RESPUESTA_MIA.search(t) else None


def relacion(a: str, b: str) -> str:
    """Cómo se relacionan dos signos solares, según cuántos signos los separan."""
    ia, ib = SIGNOS.index(a), SIGNOS.index(b)
    sep = min((ia - ib) % 12, (ib - ia) % 12)
    elementos = f"{ELEMENTOS[ia % 4]} y {ELEMENTOS[ib % 4]}"
    return f"{RELACIONES[sep]} ({elementos})"
