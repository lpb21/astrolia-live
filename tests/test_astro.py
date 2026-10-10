from datetime import date, datetime, timezone
from astro.cielo import cielo
from astro.signos import es_menor, extraer, extraer_pareja, relacion

def test_sol_j2000():                      # Sol a ~280.4° el 1-ene-2000 12:00 UT
    c = cielo(datetime(2000, 1, 1, 12, tzinfo=timezone.utc))
    assert c.posiciones["Sol"].signo == "Capricornio"
    assert 280 < c.posiciones["Sol"].lon < 281

def test_luna_llena_abril_2024():          # Luna llena 23-abr-2024 23:49 UT
    c = cielo(datetime(2024, 4, 23, 23, 49, tzinfo=timezone.utc))
    assert abs(c.fase_lunar - 180) < 2 and c.nombre_fase == "Luna llena"

def test_casas_solares():
    c = cielo(datetime(2000, 1, 1, 12, tzinfo=timezone.utc))
    assert c.casas_solares("Capricornio")["Sol"] == 1
    assert c.casas_solares("Aries")["Sol"] == 10

def test_fechas_reales_del_chat():
    casos = {
        "HL vivíana Ortiz 29 01 86 Javier Macías": "Acuario",
        "hola soy Daniela 13/11/1987 debemos vender la casa": "Escorpio",
        "soy Ruth vilca 21.07.2006, Edman Rony quiere": "Cáncer",
        "alejandra merlo 3/9/87 jose bonilla porque no me busca": "Virgo",
        "Carolina Agudelo 3 de mayo voy a tener suerte en mi proyecto?": "Tauro",
        "Daniela 19/03/97 Juan Camilo y yo vamos a volver": "Piscis",
    }
    for texto, esperado in casos.items():
        assert extraer(texto).signo == esperado, texto

def test_evento_no_es_cumpleanos():
    d = extraer("soy Raquel polo 30.9.92 ¿ me pondré de novia con Dani este sábado 10 de octubre?")
    assert d.signo == "Libra" and d.fecha.year == 1992
    assert extraer("me pondré de novia con Dani este sábado 10 de octubre?") is None

def test_cuspide():                        # el Sol entró a Piscis el 19-feb-1974
    d = extraer("luz marina Gómez 19-02-74 Freddy armas mota 26-03-85")
    assert d.en_cuspide and d.signo in ("Acuario", "Piscis")

def test_signo_por_nombre_y_glifo():
    assert extraer("soy aries ♈ leeme las cartas").signo == "Aries"
    assert extraer("soy de libra, me irá bien?").signo == "Libra"
    assert extraer("Leo me ama?") is None            # Leo como nombre, no signo

def test_sin_dato():
    for t in ["Que le espera a alejandro en el 2027", "31 71 serguio seguirá con migo",
              "mi novio Jaciel me sigue queriendo?"]:
        assert extraer(t) is None, t
        
def test_dato_de_tercero_no_cuenta():
    assert extraer("Mi ex Fernando 02/07/2002 volverá?") is None
    assert extraer("mi novio es signo aries, me ama?") is None
    assert extraer("soy Ana 05/05/90 y mi ex 02/07/2002 volverá?").signo == "Tauro"

def test_dos_fechas_primera_propia_segunda_pareja():
    t = "Ana 05/05/90, Carlos 02/07/88, volveremos?"
    assert extraer(t).signo == "Tauro"
    p = extraer_pareja(t)
    assert p.signo == "Cáncer" and p.fecha is None          # de la pareja no se guarda la fecha
    assert extraer_pareja("luz marina Gómez 19-02-74 Freddy armas mota 26-03-85").signo == "Aries"

def test_fecha_tras_tercero_es_de_la_pareja():
    t = "Mi ex Fernando 02/07/2002 volverá?"
    assert extraer(t) is None and extraer_pareja(t).signo == "Cáncer"
    t = "soy Ana 05/05/90 y mi ex 02/07/2002 volverá?"
    assert extraer(t).signo == "Tauro" and extraer_pareja(t).signo == "Cáncer"

def test_signo_de_la_pareja_por_nombre():
    assert extraer_pareja("mi novio es signo aries, me ama?").signo == "Aries"
    assert extraer_pareja("soy leo y él es cáncer, somos compatibles?").signo == "Cáncer"

def test_una_sola_fecha_no_tiene_pareja():
    for t in ["soy Ana 05/05/90 me va a buscar?", "soy aries leeme las cartas", "mi novio me quiere?"]:
        assert extraer_pareja(t) is None, t

def test_relacion_entre_signos():
    assert relacion("Tauro", "Cáncer").startswith("sextil") and "tierra y agua" in relacion("Tauro", "Cáncer")
    assert relacion("Aries", "Leo").startswith("trígono")
    assert relacion("Aries", "Libra").startswith("oposición")
    assert relacion("Piscis", "Aries") == relacion("Aries", "Piscis").replace("fuego y agua", "agua y fuego")


def test_es_menor_por_fecha():
    hoy = date(2026, 10, 9)
    assert es_menor(extraer("soy Sofi 15/03/2010 me va a hablar?"), hoy)
    assert es_menor(extraer("soy Sofi 10/10/2008 me va a hablar?"), hoy)        # cumple 18 mañana
    assert not es_menor(extraer("soy Sofi 09/10/2008 me va a hablar?"), hoy)    # cumple 18 hoy
    assert not es_menor(extraer("soy Ana 05/05/90 me va a buscar?"), hoy)
    assert not es_menor(extraer("Carolina 3 de mayo tendré suerte?"), hoy)      # sin año no se sabe
    assert not es_menor(None, hoy)
