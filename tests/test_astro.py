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


def test_fechas_escritas_de_corrido():            # logs del 11 de octubre
    from astro.signos import sin_fechas
    casos = {
        "wendy cEniceros 05 0489 quiero saber si veré mañana a Jaime": ("Aries", 1989),
        "Lesly tapia 08112007 quiero saber q quiere Stiven conmigo": ("Escorpio", 2007),
        "Isabel maria 3_8_1988 quiero saber algo": ("Leo", 1988),
        "soy Ana 050590 me va a buscar?": ("Tauro", 1990),
    }
    for texto, (signo, anio) in casos.items():
        d = extraer(texto)
        assert d and d.signo == signo and d.fecha.year == anio, texto
    assert extraer("mi número es 3001234567 me va a llamar?") is None
    assert extraer("ya van 20000 likes, me va a leer?") is None
    assert sin_fechas("Lesly 08112007 quiero saber") == "Lesly quiero saber"
    assert sin_fechas("wendy 05 0489 y Ana 3/8/83 hola") == "wendy y Ana hola"

def test_fecha_con_mes_sin_de():
    d = extraer("Yudith 15 octubre 92. quiero saber si esa persona seguirá buscándome")
    assert d.signo == "Libra" and d.fecha.year == 1992
    assert extraer("nos vemos este sábado 10 octubre, irá?") is None

def test_fecha_con_apostrofos():                   # log del 11 de octubre
    from astro.signos import sin_fechas
    for t in ["30'06'2008 Puedes decirme como pasarán las cosas con Julian",
              "30'06'08 Puedes decirme como pasarán las cosas con Julian",
              "30'06'08Puedes decirme como pasarán las cosas con Julian", "30’06’08 qué pasará con Julian?"]:
        d = extraer(t)
        assert d and d.signo == "Cáncer" and d.fecha.year == 2008, t
        assert "30" not in sin_fechas(t) and "Julian" in sin_fechas(t), t
    assert extraer("tengo 3 hijos, 2 perros y 15 años de casada, me dejará?") is None

def test_fecha_incompleta():                       # Shirley, log del 11 de octubre
    from astro.signos import fecha_incompleta
    anio = ["Hola buen día Shirley del 2002 me irá bien en esta relación con bryan del 99 🇪🇸",
            "soy del 85", "Soy yulis del 85 Camilo volverá conmigo", "nací en 1990", "del año 2001"]
    mes = ["soy de junio", "nací en marzo", "junio del 2002", "de mayo", "cumplo en octubre, me buscará?"]
    nada = ["me va a buscar este mes?", "nos vemos en mayo, irá?", "tengo 35 años, volverá?", "soy Ana 05/05/90",
            "3 de mayo", "soy tauro", "mi ex es del 99", "ya van 80 likes", "volverá en el 2027?"]
    for t in anio: assert fecha_incompleta(t) == "anio", t
    for t in mes: assert fecha_incompleta(t) == "mes", t
    for t in nada: assert fecha_incompleta(t) is None, t


# ---------- ¿de quién es la fecha? (Fernando Salazar, log del 11 de octubre) ----------
def test_fecha_junto_al_nombre_de_la_otra_persona():
    from astro.signos import repartir
    for t in ["cómo se ven las cosas entre Carmen Rodríguez 12-10-93 y Fernando Salazar",
              "cómo se ven las cosas entre Carmen 12-10-93 Rodríguez y Fernando slaazar"]:
        r = repartir(t, "FERNANDO SALAZAR", "fernando.salazar7080")
        assert r.propio is None and r.pareja.signo == "Libra" and r.pareja.fecha is None and r.de_pareja, t

def test_dos_fechas_se_reparten_por_el_nombre_de_la_cuenta():
    from astro.signos import repartir
    r = repartir("hola Cristian García 11/10/1999 y Luisa Hernández 23/12/2000 vamos arreglar las cosas",
                 "Fernanda 🌹😍❤️", "luisafernanda7467")
    assert r.propio.signo == "Capricornio" and r.pareja.signo == "Libra"
    r = repartir("Sebastiano 05 12 93 està triste por mi Fabiola 29 12 74?", "Fabiola la guerrera", "fabiolasallemi35")
    assert r.propio.fecha.year == 1974 and r.pareja.signo == "Sagitario"
    r = repartir("Ismael bravo Río 31 8 80 y ana nieves monago Benítez 30 7 91 volvera a ser pareja", "Ismael", "isma")
    assert r.propio.signo == "Virgo" and r.pareja.signo == "Leo"

def test_fecha_dudosa_cuando_la_cuenta_no_ayuda():
    from astro.signos import repartir
    for t in ["cómo se ven las cosas entre Carmen Rodríguez 12-10-93 y Fernando Salazar",
              "quiero saber si Juan y Ana 05/05/90 van a volver"]:
        r = repartir(t, "abc", "abc88.8")
        assert r.propio is None and r.dudosa is not None and not r.de_pareja, t

def test_fecha_propia_en_los_casos_de_siempre():
    from astro.signos import repartir
    casos = [("Soy Ana 05/05/90 y Juan me quiere?", "abc"), ("Ana 05/05/90 y Juan vamos a volver?", "mgc"),
             ("Hola! Brenda Sotelo 09/06/95, Noelia tiene problemas con verme bien en mi matrimonio?", "Bren♡"),
             ("JeannetteHijerra 12 4 69 tengo futuro con Manuel Sandoval?", "Janet Hijerra"),
             ("Carlos 21/07/92 edilmary está esperando que le demuestre todo para volver conmigo?", "Carlos Arango"),
             ("wendy cEniceros 05 0489 quiero saber si veré mañana a Jaime Alday", "mgc")]
    for t, cuenta in casos:
        r = repartir(t, cuenta, "x")
        assert r.propio is not None and r.dudosa is None and not r.de_pareja, t

def test_respuesta_a_la_duda():
    from astro.signos import respuesta_duda
    for t in ["mía", "es mía", "la mía", "Mia 🙏", "mi fecha", "sí, la mía", "es la mia"]:
        assert respuesta_duda(t) == "propia", t
    for t in ["de él", "de ella", "suya", "es de Carmen", "no es mía", "de mi pareja", "de mi ex"]:
        assert respuesta_duda(t) == "pareja", t
    for t in ["me va a buscar este mes?", "hola", "gracias", "quiero saber si Carmen vuelve conmigo y cuándo será"]:
        assert respuesta_duda(t) is None, t


def test_fechas_en_otros_formatos_del_chat():       # live del 11 de octubre
    from astro.signos import repartir, sin_fechas
    casos = {"Azucena Flores 12/30/82 Carlos Romero me quiere para algo serio": ("Capricornio", 1982),
             "Erika junio 11 90 Franklin marzo 12 89. Que sucederá entre nosotros": ("Géminis", 1990),
             "hector sonora 19 feb 94. me uso y todavía cruel conmigo": ("Piscis", 1994),
             "soy Eli 1995 30 de junio que me conviene": ("Cáncer", None)}
    for texto, (signo, anio) in casos.items():
        d = extraer(texto)
        assert d and d.signo == signo and (anio is None or d.fecha.year == anio), texto
    assert extraer_pareja("Erika junio 11 90 Franklin marzo 12 89. Que sucederá entre nosotros").signo == "Piscis"
    assert sin_fechas("hector 19 feb 94. volverá?") == "hector . volverá?"
    assert extraer("nos vemos en marzo 12 personas, irá?") is None and extraer("el mar 12 veces me llamó") is None

def test_se_presento_aparte_y_la_fecha_va_con_el_otro_nombre():
    from astro.signos import repartir
    r = repartir("soy Lesly, Simón Velásquez 28-2-96 regresará para algo serio en un futuro", "Les 🤍", "les.garcia43")
    assert r.propio is None and r.de_pareja and r.pareja.signo == "Piscis"
    for t in ["soy Rosa 29 10 1982 miguel me quiere", "Soy Ana, 05/05/90, me quiere Juan?",
              "hola buenos días..Olga Hernández 16_12_63 Luis regresará conmigo"]:
        assert repartir(t, "x", "y").propio is not None, t


def test_me_llamo_con_la_segunda_fecha():           # Richy García, live del 12 de octubre
    from astro.signos import repartir
    r = repartir("jael me ha hecho infiel 11 junio 1985 , me llamo Ricardo 17;04 89", "Richy garcia", "richy")
    assert r.propio.signo == "Aries" and r.propio.fecha.year == 1989 and r.pareja.signo == "Géminis"

def test_anio_pegado_a_la_palabra_siguiente():      # Judith, live del 12 de octubre
    d = extraer("soy Judith, octubre 10 de 90egresaré con la persona que ya no vivo?")
    assert d and d.signo == "Libra" and d.fecha.year == 1990
