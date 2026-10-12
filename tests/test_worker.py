import asyncio
from datetime import datetime, timedelta, timezone
from backend.cola import Cola
from backend.frases import NO_SE_LEE, PIDE_FECHA, SALUD, SOLO_ADULTOS
from backend.worker import Worker

CERO = timedelta(0)
T0 = datetime(2026, 10, 9, 1, 0, tzinfo=timezone.utc)


class GenFijo:
    def __init__(self, resp=None, error=None):
        self.resp = resp or {"sensible": False, "categoria": "", "respuesta": "lectura de prueba"}
        self.error = error
        self.prompts = []

    async def generar(self, prompt):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.resp


def preparar(pregunta, gen=None, espera_fecha=None):
    c = Cola(espera_fecha=espera_fecha)
    ts = T0.isoformat()
    if pregunta:
        c.procesar({"tipo": "comment", "user": "u", "nickname": "U", "texto": pregunta, "ts": ts})
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 1, "ts": ts})
    return c, Worker(c, gen or GenFijo(), palabras_por_seg=0)


def correr(w, seg=1):
    return asyncio.run(w.paso(T0 + timedelta(seconds=seg)))


def test_lectura_normal():
    c, w = preparar("mi novio me sigue queriendo?")
    assert correr(w)
    assert w.salidas[-1].tipo == "lectura" and c.historial[-1].estado == "hecho"

def test_embarazo_sin_rosquilla_se_le_pide_y_no_llama_al_modelo():
    gen = GenFijo()
    c, w = preparar("quedaré embarazada pronto", gen)             # regaló una rosa: 1 moneda
    correr(w)
    assert gen.prompts == [] and c.historial[-1].estado == "saltado"
    [s] = w.salidas
    assert s.tipo == "pide_regalo" and "rosquilla" in s.texto and s.cartas == []

def test_salud_mensaje_fijo_sin_modelo():
    gen = GenFijo()
    c, w = preparar("mi hija se desmaya", gen)
    correr(w)
    assert gen.prompts == [] and w.salidas[-1].tipo == "mensaje_fijo"

def test_segundo_filtro_del_modelo():
    gen = GenFijo({"sensible": True, "categoria": "salud", "respuesta": ""})
    c, w = preparar("me irá bien con mi tratamiento?", gen)
    correr(w)
    assert [s.texto for s in w.salidas] == [SALUD[0].format(n="U")] and w.saltados[-1]["categoria"] == "salud"

def test_error_del_generador_no_tumba_el_worker():
    c, w = preparar("me buscará este mes?", GenFijo(error=RuntimeError("timeout")))
    assert correr(w)
    assert w.saltados[-1]["categoria"] == "error" and w.actual is None
    assert [s.tipo for s in w.salidas] == ["mensaje_fijo"] and "problema" in w.salidas[0].texto

def test_pausa_no_toma_items():
    c, w = preparar("me buscará este mes?")
    w.pausado = True
    assert not correr(w)
    assert len(c.pendientes(T0 + timedelta(seconds=2))) == 1

def test_lectura_general_llega_al_prompt():
    gen = GenFijo()
    c, w = preparar("", gen)
    correr(w, 185)
    assert "LECTURA GENERAL" in gen.prompts[0]["messages"][0]["content"]

ESPERA = timedelta(seconds=90)

def comentar(c, texto, seg):
    c.procesar({"tipo": "comment", "user": "u", "nickname": "U", "texto": texto,
                "ts": (T0 + timedelta(seconds=seg)).isoformat()})

def test_sin_fecha_se_pide_y_no_se_lee():
    gen = GenFijo()
    c, w = preparar("mi novio me sigue queriendo?", gen, ESPERA)
    assert correr(w)
    assert w.salidas[-1].tipo == "pide_fecha" and "U" in w.salidas[-1].texto and gen.prompts == []
    assert not correr(w, 30) and len(w.salidas) == 1          # no vuelve a pedirla

def test_al_dar_la_fecha_se_lee_con_su_signo():
    gen = GenFijo()
    c, w = preparar("mi novio me sigue queriendo?", gen, ESPERA)
    correr(w)
    comentar(c, "05/05/1990", 20)
    assert correr(w, 21) and w.salidas[-1].tipo == "lectura"
    assert "Signo solar de la persona: Tauro" in gen.prompts[0]["messages"][0]["content"]
    assert c.historial[-1].pregunta == "mi novio me sigue queriendo?" and c.historial[-1].extras == []

def test_fecha_en_la_pregunta_no_se_pide():
    gen = GenFijo()
    c, w = preparar("soy Ana 05/05/90 mi novio me sigue queriendo?", gen, ESPERA)
    correr(w)
    assert [s.tipo for s in w.salidas] == ["lectura"]

def test_si_no_responde_se_lee_sin_signo():
    gen = GenFijo()
    c, w = preparar("mi novio me sigue queriendo?", gen, ESPERA)
    correr(w)
    assert not correr(w, 60)
    assert correr(w, 95) and w.salidas[-1].tipo == "lectura"
    assert "desconocido" in gen.prompts[0]["messages"][0]["content"]

def test_fecha_dada_antes_se_recuerda():
    gen = GenFijo()
    c = Cola(espera_fecha=ESPERA)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "soy Ana 05/05/90 me va a buscar?", 0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    correr(w); c.cerrar("u")
    comentar(c, "y en el trabajo me irá bien?", 200)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 1,
                "ts": (T0 + timedelta(seconds=201)).isoformat()})
    correr(w, 202)
    assert [s.tipo for s in w.salidas] == ["lectura", "lectura"]


def test_menor_por_fecha_se_descarta_sin_llamar_al_modelo():
    gen = GenFijo()
    c, w = preparar("soy Sofi 15/03/2010 me va a hablar Juan?", gen, ESPERA)
    assert correr(w)
    assert gen.prompts == [] and [s.texto for s in w.salidas] == [SOLO_ADULTOS[0]]
    assert all("mayores de edad" in f and "menor" not in f for f in SOLO_ADULTOS) and w.salidas[0].tipo == "mensaje_fijo"
    assert c.historial[-1].estado == "saltado" and w.saltados[-1]["categoria"] == "menor"
    assert c.pendientes(T0 + timedelta(seconds=2)) == []

def test_menor_que_da_la_fecha_despues_tambien_se_descarta():
    gen = GenFijo()
    c, w = preparar("me va a hablar Juan esta semana?", gen, ESPERA)
    correr(w)                                   # se le pide la fecha
    comentar(c, "15/03/2010", 20)
    assert correr(w, 21) and w.salidas[-1].texto == SOLO_ADULTOS[0]
    assert gen.prompts == [] and w.saltados[-1]["categoria"] == "menor"

def test_fecha_de_la_pareja_menor_no_descarta_a_quien_pregunta():
    gen = GenFijo()
    c, w = preparar("soy Ana 05/05/90 mi hijo 15/03/2010 pasará el año?", gen, ESPERA)
    correr(w)
    assert all(s["categoria"] != "menor" or s["motivo"] != "fecha de nacimiento" for s in w.saltados)


def test_lectura_sale_con_su_tirada():
    gen = GenFijo()
    c, w = preparar("mi novio me sigue queriendo?", gen)
    correr(w)
    salida, item = w.salidas[-1], c.historial[-1]
    assert [t.posicion for t in salida.cartas] == ["mensaje"]          # una rosa = 1 moneda
    assert salida.nivel == "Mensaje del oráculo"
    assert salida.cartas == item.cartas
    assert f"Mensaje: {salida.cartas[0].carta.nombre}" in gen.prompts[0]["messages"][0]["content"]

def test_mensaje_fijo_y_saltados_no_sacan_cartas():
    c, w = preparar("mi hija se desmaya")
    correr(w)
    assert w.salidas[-1].tipo == "mensaje_fijo" and w.salidas[-1].cartas == []
    c, w = preparar("quedaré embarazada pronto")
    correr(w)
    assert c.historial[-1].cartas == []


def test_regalo_sin_pregunta_se_avisa_y_espera():
    gen = GenFijo()
    c, w = preparar("", gen, ESPERA)
    assert correr(w)
    assert [s.tipo for s in w.salidas] == ["pide_pregunta"] and "pregunta" in w.salidas[0].texto
    assert not correr(w, 30) and gen.prompts == []            # no se repite el aviso ni se lee aún

def test_sin_pregunta_recibe_el_mensaje_sin_pedirle_fecha():
    gen = GenFijo()
    c, w = preparar("", gen, ESPERA)
    correr(w)
    assert correr(w, 181)
    assert [s.tipo for s in w.salidas] == ["pide_pregunta", "lectura"]
    assert "LECTURA GENERAL" in gen.prompts[0]["messages"][0]["content"]

def test_pregunta_tardia_con_fecha_se_lee_como_pregunta():
    gen = GenFijo()
    c, w = preparar("", gen, ESPERA)
    correr(w)
    comentar(c, "soy Ana 05/05/90 me va a buscar Juan?", 90)
    correr(w, 91)
    assert [s.tipo for s in w.salidas] == ["pide_pregunta", "lectura"]
    assert "me va a buscar Juan?" in gen.prompts[0]["messages"][0]["content"]

def test_segunda_pregunta_solo_desde_30_monedas():
    def contenido(valor):
        gen = GenFijo()
        c = Cola(espera_fecha=None)
        w = Worker(c, gen, palabras_por_seg=0)
        comentar(c, "me va a buscar este mes?", 0)
        c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "X", "valor": valor, "ts": T0.isoformat()})
        comentar(c, "y en el trabajo me irá bien?", 1)
        correr(w, 2)
        return gen.prompts[0]["messages"][0]["content"]
    assert "Responde también" in contenido(30) and "Tipo de lectura: Lectura doble" in contenido(30)
    assert "Responde también" not in contenido(10)


def test_pregunta_gratis_pide_fecha_y_se_lee_como_si_o_no():
    gen = GenFijo()
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "me va a buscar Juan este mes?", 0)
    assert correr(w) and [s.tipo for s in w.salidas] == ["pide_fecha"] and gen.prompts == []
    comentar(c, "05/05/90", 20)
    assert correr(w, 21)
    s = w.salidas[-1]
    assert s.tipo == "lectura" and s.nivel == "Sí o no" and [t.posicion for t in s.cartas] == ["respuesta"]
    contenido = gen.prompts[0]["messages"][0]["content"]
    assert "turno gratis de sí o no" in contenido and "Tauro" in contenido

def test_menor_con_pregunta_gratis_recibe_el_aviso():
    gen = GenFijo()
    c = Cola(espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "soy Sofi 15/03/2010 me va a hablar Juan?", 0)
    correr(w)
    assert gen.prompts == [] and [s.texto for s in w.salidas] == [SOLO_ADULTOS[0]]

def test_segunda_pregunta_que_llega_con_la_fecha_se_responde():
    gen = GenFijo()
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "¿me irá bien con Juan?", 0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "X", "valor": 30, "ts": T0.isoformat()})
    comentar(c, "soy Ana 05/05/90 y en el trabajo, ¿me ascenderán?", 5)
    correr(w, 6)
    contenido = gen.prompts[0]["messages"][0]["content"]
    assert "me ascenderán?" in contenido and "Responde también" in contenido and "Tauro" in contenido


def test_la_lectura_queda_en_pantalla_lo_suficiente():
    from backend.worker import Salida
    from tarot.tirada import tirar
    w = Worker(Cola(), GenFijo(), palabras_por_seg=2.5)
    corta = Salida("u", "U", "", "lectura", "Respuesta de prueba del generador falso.", T0, tirar(1))
    assert w._duracion(corta) == 6 + 3 + 3                           # 2,4 s de voz no alcanzan para ver la carta
    seis = Salida("u", "U", "", "lectura", "palabra " * 20, T0, tirar(100))
    assert w._duracion(seis) == 6 + 3 * 6 + 3
    larga = Salida("u", "U", "", "lectura", "palabra " * 200, T0, tirar(100))
    assert w._duracion(larga) == 200 / 2.5 + 3                       # la voz manda, más la pausa final
    aviso = Salida("", "", "", "pide_fecha", "palabra " * 10, T0)
    assert w._duracion(aviso) == 4

def test_la_voz_recuerda_la_pregunta_gratis_cada_cierto_tiempo():
    c = Cola()
    w = Worker(c, GenFijo(), palabras_por_seg=0, aviso_gratis=timedelta(minutes=5))
    assert not correr(w, 0) and not correr(w, 59)
    assert correr(w, 60) and w.salidas[-1].tipo == "aviso" and "signo de interrogación" in w.salidas[-1].texto
    assert not correr(w, 200)
    assert correr(w, 361) and len(w.salidas) == 2
    sin = Worker(Cola(max_gratis=0), GenFijo(), palabras_por_seg=0, aviso_gratis=timedelta(minutes=5))
    assert not correr(sin, 0) and not correr(sin, 600)

def test_si_o_no_pide_contexto_y_mas_palabras():
    gen = GenFijo()
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "me va a buscar Juan este mes?", 0)
    correr(w)
    contenido = gen.prompts[0]["messages"][0]["content"]
    assert "No respondas con un sí o un no seco" in contenido and "entre 60 y 90 palabras" in contenido

def test_el_prompt_deja_pasar_las_preguntas_de_dinero():
    gen = GenFijo()
    c, w = preparar("voy a poder salir de mis deudas?", gen)
    correr(w)
    assert w.salidas[-1].tipo == "lectura"
    sistema = gen.prompts[0]["system"]
    assert "DINERO Y TRABAJO" in sistema and "dinero o temas legales" not in sistema


def test_los_avisos_rotan_sus_frases():
    c = Cola(espera_fecha=ESPERA)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    for n, user in enumerate(["a", "b", "c", "d"]):
        c.procesar({"tipo": "comment", "user": user, "nickname": user.upper(), "texto": "me va a buscar este mes?",
                    "ts": (T0 + timedelta(seconds=n * 10)).isoformat()})
        c.procesar({"tipo": "gift", "user": user, "nickname": user.upper(), "regalo": "Rose", "valor": 1,
                    "ts": (T0 + timedelta(seconds=n * 10)).isoformat()})
        correr(w, n * 10 + 1)
    dichos = [s.texto for s in w.salidas if s.tipo == "pide_fecha"]
    assert dichos == [PIDE_FECHA[i % len(PIDE_FECHA)][0].format(n=u) for i, u in enumerate("ABCD")]
    assert dichos[0] != dichos[1] != dichos[2] and dichos[3].startswith("D, para leerte")

def test_aviso_para_varias_personas_va_en_plural():
    c = Cola(espera_fecha=ESPERA)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    for user in ("a", "b"):
        c.procesar({"tipo": "comment", "user": user, "nickname": user.upper(), "texto": "me va a buscar este mes?", "ts": T0.isoformat()})
        c.procesar({"tipo": "gift", "user": user, "nickname": user.upper(), "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    correr(w)
    assert w.salidas[-1].texto == PIDE_FECHA[0][1].format(n="A, B")

def test_todas_las_frases_tienen_sus_campos():
    from backend import frases as f
    for uno, varios in f.PIDE_PREGUNTA + f.PIDE_FECHA:
        assert "{n}" in uno and "{n}" in varios
    assert all("{seg}" in x for x in f.BOOST_INICIO)
    assert all("{n}" in x and "{likes}" in x for x in f.BOOST_GANO + f.BOOST_GANO_SIN_PREGUNTA)
    assert all("interrogación" in x and "fecha" in x and "ígueme" in x for x in f.AVISO_GRATIS)
    assert all("{" not in x for x in f.NO_SE_LEE + f.SOLO_ADULTOS + f.FALLO)


def test_si_solo_da_el_anio_la_voz_dice_que_falta_y_le_da_mas_tiempo(caplog):
    gen = GenFijo()
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "soy Shirley me irá bien en esta relación con bryan?", 0)
    correr(w, 1)                                             # pide la fecha
    comentar(c, "Shirley del 2002 me irá bien en esta relación con bryan del 99", 17)
    comentar(c, "Shirley del 2002 me irá bien en esta relación con bryan del 99", 20)   # insiste
    assert correr(w, 21)
    assert [s.tipo for s in w.salidas] == ["pide_fecha", "pide_fecha"]
    assert "ya tengo el año" in w.salidas[-1].texto and "día y el mes" in w.salidas[-1].texto
    assert not correr(w, 30) and len(w.salidas) == 2         # no se repite por cada mensaje
    assert c.pendientes(T0 + timedelta(seconds=100))          # sigue en la fila: el plazo empezó de nuevo
    comentar(c, "30 de junio", 101)
    correr(w, 102)
    assert w.salidas[-1].tipo == "lectura" and w.salidas[-1].signo == "Cáncer"

def test_si_solo_da_el_mes_se_le_pide_el_dia_y_si_no_responde_queda_en_el_log(caplog):
    import logging
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    comentar(c, "me va a buscar Juan este mes?", 0)
    correr(w, 1)
    comentar(c, "soy de junio", 10)
    correr(w, 11)
    assert "ya tengo el mes" in w.salidas[-1].texto and "día" in w.salidas[-1].texto
    with caplog.at_level(logging.INFO, logger="cola"):
        assert c.pendientes(T0 + timedelta(seconds=110)) == []
    assert "[SIN_FECHA] u sale de la fila" in caplog.text and w.salidas[-1].tipo == "pide_fecha"


def test_cada_lectura_ofrece_frases_de_fe_distintas():
    from backend.frases import BENDICIONES
    gen = GenFijo()
    c = Cola(espera_fecha=None)
    w = Worker(c, gen, palabras_por_seg=0)
    vistas = []
    for n in range(10):
        user = f"u{n}"
        c.procesar({"tipo": "comment", "user": user, "nickname": user, "texto": "me va a buscar este mes?", "ts": T0.isoformat()})
        c.procesar({"tipo": "gift", "user": user, "nickname": user, "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
        correr(w, n + 1)
        contenido = gen.prompts[-1]["messages"][0]["content"]
        bloque = contenido.split("<cierre_de_fe>\n")[1].split("\n</cierre_de_fe>")[0].split("\n")
        assert len(bloque) == 4 and all(b in BENDICIONES for b in bloque)
        assert "no uses ninguna" in contenido and "no cuenta en el límite" in contenido
        vistas += bloque
    assert len(set(vistas)) == 40 == len(BENDICIONES)          # dio la vuelta completa sin repetir

def test_pregunta_gratis_tambien_recibe_frases_de_fe():
    gen = GenFijo()
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "voy a superar esta tristeza?", 0)
    correr(w)
    assert "<cierre_de_fe>" in gen.prompts[0]["messages"][0]["content"]


def _fernando(nickname, valor=0):
    gen = GenFijo()
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    ev = {"user": "fer", "nickname": nickname, "ts": T0.isoformat()}
    c.procesar({**ev, "tipo": "comment", "texto": "cómo se ven las cosas entre Carmen Rodríguez 12-10-93 y Fernando Salazar"})
    if valor:
        c.procesar({**ev, "tipo": "gift", "regalo": "Rose", "valor": valor})
    return gen, c, w

def _dice(c, texto, seg, user="fer", nickname="x"):
    c.procesar({"tipo": "comment", "user": user, "nickname": nickname, "texto": texto,
                "ts": (T0 + timedelta(seconds=seg)).isoformat()})

def test_fecha_de_la_pareja_por_el_nombre_de_la_cuenta_se_le_pide_la_suya():
    gen, c, w = _fernando("FERNANDO SALAZAR", valor=5)
    correr(w, 1)
    [item] = c.pendientes(T0 + timedelta(seconds=2))
    assert item.dato is None and item.pareja.signo == "Libra" and c.falta(item) == ["fecha"]
    assert "ya tengo la fecha de la otra persona" in w.salidas[-1].texto
    _dice(c, "03/03/1990", 20, nickname="FERNANDO SALAZAR")
    correr(w, 21)
    contenido = gen.prompts[0]["messages"][0]["content"]
    assert w.salidas[-1].signo == "Piscis" and "Signo solar de la persona: Piscis" in contenido and "Libra" in contenido

def test_fecha_dudosa_se_pregunta_y_no_frena_a_los_demas():
    gen, c, w = _fernando("abc", valor=100)
    c.procesar({"tipo": "comment", "user": "otra", "nickname": "Otra", "texto": "soy Ana 05/05/90 me va a buscar Juan?", "ts": T0.isoformat()})
    c.procesar({"tipo": "gift", "user": "otra", "nickname": "Otra", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    correr(w, 1)
    assert [s.tipo for s in w.salidas] == ["pide_fecha", "lectura"]
    assert "¿es tuya o de la otra persona?" in w.salidas[0].texto
    assert w.salidas[1].nickname == "Otra"                      # tenía menos monedas, pero no esperó la respuesta
    assert not correr(w, 10)                                    # no se repite la pregunta ni se lee todavía
    _dice(c, "de ella", 15)
    correr(w, 16)
    [item] = c.pendientes(T0 + timedelta(seconds=17))
    assert item.dudosa is None and item.pareja.signo == "Libra" and c.falta(item) == ["fecha"]
    assert "me falta la tuya" in w.salidas[-1].texto or "escríbeme la tuya" in w.salidas[-1].texto

def test_si_responde_mia_se_lee_con_su_signo():
    gen, c, w = _fernando("abc", valor=5)
    correr(w, 1)
    _dice(c, "es mía", 10)
    correr(w, 11)
    assert w.salidas[-1].tipo == "lectura" and w.salidas[-1].signo == "Libra"
    assert "Signo solar de la persona: Libra" in gen.prompts[0]["messages"][0]["content"]

def test_si_no_responde_la_duda_se_lee_igual_y_la_ia_lo_resuelve():
    gen, c, w = _fernando("abc")                                # pregunta gratis
    correr(w, 1)
    assert not correr(w, 45)
    assert correr(w, 47)
    s = w.salidas[-1]
    assert s.tipo == "lectura" and s.signo == ""                # en pantalla no se le atribuye el signo
    contenido = gen.prompts[0]["messages"][0]["content"]
    assert "Signo de la persona: desconocido" in contenido and "no se sabe si es de quien pregunta" in contenido

def test_fecha_dudosa_de_menor_no_descarta_a_quien_pregunta():
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    _dice(c, "cómo se ven las cosas entre Sofi 15/03/2010 y Pedro", 0, nickname="abc")
    correr(w, 1)
    assert [s.tipo for s in w.salidas] == ["pide_fecha"] and w.saltados == []


# ---------- Oliver, log del 11 de octubre: una pregunta ya respondida no se vuelve a leer ----------
def test_pregunta_ya_respondida_no_se_relee_gratis_ni_con_otro_regalo():
    gen = GenFijo()
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    P = "Elkin Oliver Camacho Camino 20 de septiembre del 2005 lograré ser militar y cuando?"
    regalo = lambda seg, nombre, valor: c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": nombre,
                                                    "valor": valor, "ts": (T0 + timedelta(seconds=seg)).isoformat()})
    regalo(0, "Hand Heart", 100)
    comentar(c, P, 18)
    correr(w, 38)
    assert [s.nivel for s in w.salidas if s.tipo == "lectura"] == ["Lectura completa"]
    for seg in (203, 208, 212):                       # la repite mientras espera a la anfitriona
        comentar(c, P, seg)
    assert not correr(w, 230) and len(gen.prompts) == 1
    assert c.situacion("u") == "Esa pregunta ya se le respondió: se lee de nuevo solo si regala"
    comentar(c, "Muchas gracias", 499)
    regalo(504, "Rose", 3)                            # otro regalo, sin pregunta nueva
    correr(w, 505)
    [item] = c.pendientes(T0 + timedelta(seconds=506))
    assert item.pregunta == "" and w.salidas[-1].tipo == "pide_pregunta" and len(gen.prompts) == 1
    comentar(c, P, 520)                               # ahora sí la quiere otra vez, con su regalo
    correr(w, 521)
    assert [s.nivel for s in w.salidas if s.tipo == "lectura"] == ["Lectura completa", "Mensaje del oráculo"]

def test_pregunta_nueva_despues_de_una_respondida_si_entra():
    gen = GenFijo()
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "me va a buscar Juan este mes?", 0)
    correr(w, 1)
    comentar(c, "Me va a buscar Juan este mes ??", 20)          # la misma, escrita distinto
    assert correr(w, 21) and w.salidas[-1].tipo == "agotada"    # no se relee: se le avisa que ya usó su gratis
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 1, "ts": (T0 + timedelta(seconds=30)).isoformat()})
    comentar(c, "y en el trabajo me irá bien?", 35)             # otra pregunta, con regalo
    correr(w, 36)
    assert "en el trabajo" in gen.prompts[-1]["messages"][0]["content"] and len(gen.prompts) == 2


# ---------- bienvenida a quienes entran ----------
def test_bienvenida_entre_lecturas():
    from backend.frases import BIENVENIDA, Y_LOS_DEMAS
    c = Cola(espera_fecha=None)
    w = Worker(c, GenFijo(), palabras_por_seg=0, bienvenida=timedelta(seconds=60))
    assert not correr(w, 0)
    w.llegada("a", "Ana")
    w.llegada("a", "Ana")                                       # entrar dos veces no la saluda dos veces
    assert correr(w, 1) and w.salidas[-1].tipo == "bienvenida"
    assert w.salidas[-1].texto == BIENVENIDA[0][0].format(n="Ana")
    for u, n in [("b", "Luis"), ("c", "Marta"), ("a", "Ana")]:
        w.llegada(u, n)
    assert not correr(w, 30)                                    # todavía no pasa el minuto
    assert correr(w, 62) and w.salidas[-1].texto == BIENVENIDA[1][1].format(n="Luis y Marta")
    for n in range(6):
        w.llegada(f"x{n}", f"P{n}")
    correr(w, 130)
    assert w.salidas[-1].texto == BIENVENIDA[2][1].format(n="P3, P4, P5" + Y_LOS_DEMAS)
    assert not correr(w, 300)                                   # sin gente nueva no hay saludo

def test_la_bienvenida_espera_a_que_no_haya_preguntas():
    c = Cola(espera_fecha=None)
    w = Worker(c, GenFijo(), palabras_por_seg=0, bienvenida=timedelta(seconds=180))
    for n, user in enumerate(["p1", "p2"]):
        c.procesar({"tipo": "comment", "user": user, "nickname": user, "texto": "me va a buscar este mes?", "ts": T0.isoformat()})
        c.procesar({"tipo": "gift", "user": user, "nickname": user, "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    w.llegada("z", "Zoe")
    correr(w, 1)
    correr(w, 2)
    assert [s.tipo for s in w.salidas] == ["lectura", "lectura"]          # primero las preguntas
    assert correr(w, 3) and w.salidas[-1].tipo == "bienvenida" and "Zoe" in w.salidas[-1].texto
    w.llegada("y", "Yuli")
    assert not correr(w, 120)                                             # y no más de una cada 3 minutos
    assert correr(w, 184) and "Yuli" in w.salidas[-1].texto

def test_sin_bienvenida_configurada_no_se_guarda_a_nadie():
    w = Worker(Cola(), GenFijo(), palabras_por_seg=0)
    w.llegada("a", "Ana")
    assert not correr(w, 0) and w.salidas == []


def test_si_dice_que_la_mando_al_interno_se_le_pide_en_el_chat():       # mylove, live del 11 de octubre
    gen = GenFijo()
    c = Cola(espera_fecha=None)
    w = Worker(c, gen, palabras_por_seg=0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "mylove", "regalo": "Singing Mushroom", "valor": 99, "ts": T0.isoformat()})
    correr(w, 1)                                               # le pide la pregunta
    comentar(c, "te envie la pregunta al interno", 60)
    comentar(c, "ya te la mandé por privado", 65)
    assert correr(w, 66)
    assert [s.tipo for s in w.salidas] == ["pide_pregunta", "pide_pregunta"]
    assert "aquí en el chat" in w.salidas[-1].texto and "mylove" in w.salidas[-1].texto
    assert not correr(w, 70)                                   # se le dice una sola vez
    comentar(c, "le llegará el karma a Héctor por el daño que me hizo?", 90)
    correr(w, 91)
    assert w.salidas[-1].tipo == "lectura" and "karma" in gen.prompts[0]["messages"][0]["content"]

def test_hablar_del_interno_sin_regalo_no_dispara_el_aviso():
    c = Cola(espera_fecha=None)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    comentar(c, "te escribí al interno", 0)
    assert not correr(w, 1) and w.salidas == []


# ---------- embarazo: se lee con rosquilla (Susel Ríos, live del 12 de octubre) ----------
def test_embarazo_con_rosquilla_se_lee():
    gen = GenFijo()
    c = Cola(espera_fecha=None)
    w = Worker(c, gen, palabras_por_seg=0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "Susel", "regalo": "Doughnut", "valor": 30, "ts": T0.isoformat()})
    comentar(c, "saber si estoy embarazada?", 20)
    correr(w, 21)
    assert w.salidas[-1].tipo == "lectura" and "embarazada" in gen.prompts[0]["messages"][0]["content"]
    assert "EMBARAZO" in gen.prompts[0]["system"] and "confirme con una prueba" in gen.prompts[0]["system"]

def test_embarazo_gratis_se_le_pide_la_rosquilla_de_una_y_al_enviarla_se_lee():
    gen = GenFijo()
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "soy Ana 05/05/90 estoy embarazada?", 0)
    assert correr(w, 1)
    assert [s.tipo for s in w.salidas] == ["pide_regalo"] and "Envíala" in w.salidas[0].texto or "envía una rosquilla" in w.salidas[0].texto
    assert c.pendientes(T0 + timedelta(seconds=2)) == [] and gen.prompts == []
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Doughnut", "valor": 30,
                "ts": (T0 + timedelta(seconds=40)).isoformat()})
    correr(w, 41)
    assert w.salidas[-1].tipo == "lectura" and w.salidas[-1].nivel == "Lectura doble"
    comentar(c, "y me va a buscar Juan este mes?", 60)          # su pregunta gratis seguía intacta
    correr(w, 61)
    assert w.salidas[-1].nivel == "Sí o no"

def test_embarazo_con_regalo_pequeno_no_alcanza():
    gen = GenFijo()
    c = Cola(espera_fecha=None)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "quedaré embarazada este año?", 0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 5, "ts": T0.isoformat()})
    correr(w, 1)
    assert w.salidas[-1].tipo == "pide_regalo" and gen.prompts == []


# ---------- cartel de pregunta gratis agotada ----------
def test_gratis_agotada_se_avisa_una_vez_con_cartel():
    from backend.overlay import vista
    gen = GenFijo()
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "me va a buscar Juan este mes?", 0)
    correr(w, 1)                                                # su pregunta gratis
    assert vista(c, w, T0 + timedelta(seconds=2))["cartel"] is None
    comentar(c, "y en el trabajo me irá bien?", 30)
    assert correr(w, 31)
    s = w.salidas[-1]
    assert s.tipo == "agotada" and "ya usaste tu pregunta gratis" in s.texto and "regalo" in s.texto
    assert vista(c, w, T0 + timedelta(seconds=40))["cartel"] == "U"
    assert vista(c, w, T0 + timedelta(seconds=60))["cartel"] is None       # el cartel dura unos segundos
    comentar(c, "y con mi familia cómo me irá?", 70)
    assert not correr(w, 71) and len(gen.prompts) == 1                     # no se repite el aviso ni se lee

def test_charla_de_quien_ya_uso_la_gratis_no_dispara_el_cartel():
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    comentar(c, "me va a buscar Juan este mes?", 0)
    correr(w, 1)
    for n, t in enumerate(["gracias bella", "Bonito domingo bella ✨ gracias", "él es así muy orgulloso"]):
        comentar(c, t, 10 + n)
    assert not correr(w, 20)

def test_con_regalo_no_sale_el_cartel():
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    comentar(c, "me va a buscar Juan este mes?", 0)
    correr(w, 1)
    comentar(c, "y en el trabajo me irá bien?", 30)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 1, "ts": (T0 + timedelta(seconds=31)).isoformat()})
    correr(w, 32)
    assert [s.tipo for s in w.salidas] == ["lectura", "lectura"]


# ---------- salud: orientación con cariño ----------
def test_salud_recibe_una_orientacion_y_no_se_leen_cartas():
    gen = GenFijo()
    c, w = preparar("quiero saber si tengo asma o disnea", gen)
    correr(w)
    [s] = w.salidas
    assert s.tipo == "mensaje_fijo" and s.cartas == [] and gen.prompts == []
    assert s.texto.startswith("U, ") and "médico" in s.texto
    assert all("{n}" in f and ("médico" in f or "doctor" in f) for f in SALUD)


# ---------- live del 12 de octubre (indiodeluz): Johanna, José, Judith y "¿hay preguntitas gratuitas?" ----------
def test_el_cartel_vuelve_a_salir_cada_vez_que_insiste_pero_la_voz_avisa_una_vez():
    from backend.overlay import vista
    gen = GenFijo()
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    P = "Hola soy johanna urbina 150986 quiero Saber si Jonathan ya tiene una relación con otra persona"
    comentar(c, P, 0)
    correr(w, 1)                                                  # su pregunta gratis
    comentar(c, P, 33)                                            # la repite
    assert vista(c, w, T0 + timedelta(seconds=34))["cartel"] == "U"
    assert correr(w, 34) and w.salidas[-1].tipo == "agotada"
    assert vista(c, w, T0 + timedelta(seconds=70))["cartel"] is None
    comentar(c, P, 100)                                           # insiste más tarde
    comentar(c, "soy johanna 150986 Jonathan dejó de amarme?", 105)
    assert vista(c, w, T0 + timedelta(seconds=106))["cartel"] == "U"      # el cartel vuelve a salir
    assert not correr(w, 106) and len(gen.prompts) == 1                   # la voz no se repite

def test_cartel_con_varias_personas_muestra_las_tres_ultimas():
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    for n, user in enumerate(["a", "b", "c", "d"]):
        c.procesar({"tipo": "comment", "user": user, "nickname": user.upper(), "texto": "me va a buscar este mes?",
                    "ts": T0.isoformat()})
        correr(w, n + 1)
    for n, user in enumerate(["a", "b", "c", "d"]):
        c.procesar({"tipo": "comment", "user": user, "nickname": user.upper(), "texto": "y en el trabajo me irá bien?",
                    "ts": (T0 + timedelta(seconds=40 + n)).isoformat()})
    assert c.cartel(T0 + timedelta(seconds=45)) == "B, C, D"

def test_pregunta_por_las_gratis_no_entra_a_la_fila_y_la_voz_explica():
    from backend.frases import AVISO_GRATIS
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0, aviso_gratis=timedelta(minutes=5))
    correr(w, 0)
    correr(w, 60)                                                 # el recordatorio de siempre
    assert len(w.salidas) == 1
    for seg, t in [(150, "hay preguntitas gratuitas??"), (151, "son gratis las preguntas?")]:
        comentar(c, t, seg)
    assert c.pendientes(T0 + timedelta(seconds=152)) == []
    assert correr(w, 152) and w.salidas[-1].tipo == "aviso" and w.salidas[-1].texto in AVISO_GRATIS
    comentar(c, "hay gratis?", 170)
    assert not correr(w, 171)                                     # se acaba de explicar: no se repite enseguida
    assert len(w.salidas) == 2
    
def test_limite_de_gasto_pausa_y_devuelve_el_turno():
    from backend.generador import LimiteGasto
    c, w = preparar("me buscará este mes?", GenFijo(error=LimiteGasto("usage limits")))
    correr(w)
    assert w.pausado and w.alerta and w.saltados == []
    assert [i.user for i in c.pendientes(T0 + timedelta(seconds=2))] == ["u"]
