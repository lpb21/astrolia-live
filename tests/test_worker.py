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

def test_embarazo_se_invita_al_dm_y_no_llama_al_modelo():
    gen = GenFijo()
    c, w = preparar("quedaré embarazada pronto", gen)             # regaló una rosa: 1 moneda
    correr(w)
    assert gen.prompts == [] and c.historial[-1].estado == "hecho"
    [s] = w.salidas                                                # va por DM, y la voz no dice la palabra
    assert s.tipo == "mensaje_fijo" and "mensaje directo" in s.texto and "embaraz" not in s.texto.lower() and s.cartas == []

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
    assert "MENSAJE DE LAS CARTAS" in gen.prompts[0]["messages"][0]["content"]

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
    assert "MENSAJE DE LAS CARTAS" in gen.prompts[0]["messages"][0]["content"]

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
    assert "Dinero y trabajo:" in sistema and "Ante la duda, responde" in sistema


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
        c.procesar({"tipo": "comment", "user": user, "nickname": user, "texto": "estoy muy triste, me va a buscar este mes?", "ts": T0.isoformat()})
        c.procesar({"tipo": "gift", "user": user, "nickname": user, "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
        correr(w, n + 1)
        contenido = gen.prompts[-1]["messages"][0]["content"]
        bloque = contenido.split("<cierre_de_fe>\n")[1].split("\n</cierre_de_fe>")[0].split("\n")
        assert len(bloque) == 1 and bloque[0] in BENDICIONES        # una sola: con cuatro, la IA llegó a decir dos
        assert "no la uses" in contenido and "no cuenta en el límite" in contenido
        assert "como máximo UNA frase que mencione a Dios" in contenido
        vistas += bloque
    assert len(set(vistas)) == 10                              # no repite hasta dar la vuelta a las 40

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
    assert w.salidas[1].user == "otra"                          # tenía menos monedas, pero no esperó la respuesta
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


# ---------- live del 12 de octubre con IA y voz (barakaconexionyesencia) ----------
def test_el_prompt_avisa_que_el_nombre_de_la_tarotista_no_es_el_de_quien_pregunta():
    gen = GenFijo()
    c, w = preparar("Baraka quisiera saber si voy a comprar pronto mi moto", gen)
    correr(w)
    assert "Ese nombre es el de la tarotista" in gen.prompts[0]["system"]

def test_tema_delicado_gratis_se_responde_sin_pedir_la_fecha():
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    comentar(c, "como me puedo quitar un vudú que me puso una bruja para que no me toque la enfermedad?", 0)
    correr(w, 1)
    assert [s.tipo for s in w.salidas] == ["mensaje_fijo"] and "médico" in w.salidas[0].texto
    c2 = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w2 = Worker(c2, GenFijo(), palabras_por_seg=0)
    comentar(c2, "cómo me quito un amarre que me hizo una bruja?", 0)
    correr(w2, 1)
    assert [s.tipo for s in w2.salidas] == ["mensaje_fijo"] and w2.saltados[-1]["categoria"] == "brujeria"


# ---------- relleno: que la voz no se quede callada ----------
def test_tras_unos_segundos_en_silencio_la_voz_llena_el_rato():
    from backend import frases
    gen = GenFijo()
    c = Cola(espera_fecha=None)
    w = Worker(c, gen, palabras_por_seg=0, relleno=timedelta(seconds=3))
    assert not correr(w, 0) and not correr(w, 2)
    assert correr(w, 3) and w.salidas[-1].tipo == "relleno" and w.salidas[-1].texto in frases.TIPS
    assert not correr(w, 5)                                           # vuelve a contar desde lo último que dijo
    assert correr(w, 6)
    s = w.salidas[-1]
    assert s.tipo == "carta_momento" and len(s.cartas) == 1 and s.nivel == "Carta del momento"
    assert "carta del momento" in gen.prompts[-1]["messages"][0]["content"] and gen.prompts[-1]["valor"] == 0
    correr(w, 9)
    assert w.salidas[-1].tipo == "relleno" and ("Luna está en" in w.salidas[-1].texto or "Luna en" in w.salidas[-1].texto)

def test_la_carta_del_momento_y_el_cielo_no_salen_en_cada_silencio(monkeypatch):
    monkeypatch.setattr("backend.worker.MAX_HISTORIAL", 1000)          # para contar todo lo dicho
    gen = GenFijo()
    w = Worker(Cola(), gen, palabras_por_seg=0, relleno=timedelta(seconds=3))
    for seg in range(0, 601, 3):                                      # diez minutos sin nadie
        correr(w, seg)
    tipos = [s.tipo for s in w.salidas]
    assert tipos.count("carta_momento") == 4 and len(gen.prompts) == 4          # una cada 3 minutos
    textos = [s.texto for s in w.salidas if s.tipo == "relleno"]
    assert sum("Luna" in t and "cielo" in t.lower() for t in textos) == 1        # el cielo, cada 10 minutos
    assert len(set(textos[:30])) == 30                                          # sin repetir tips en un buen rato

def test_el_relleno_no_se_adelanta_a_un_turno():
    c, w = preparar("mi novio me sigue queriendo?")
    w.relleno = timedelta(seconds=3)
    correr(w, 100)
    assert [s.tipo for s in w.salidas] == ["lectura"]
    assert not correr(w, 102) and correr(w, 103) and w.salidas[-1].tipo == "relleno"

def test_carta_del_momento_sin_ia_usa_la_frase_fija():
    from backend.worker import GeneradorFalso
    w = Worker(Cola(), GeneradorFalso(), palabras_por_seg=0, relleno=timedelta(seconds=10))
    correr(w, 0); correr(w, 10); correr(w, 20)
    s = w.salidas[-1]
    assert s.tipo == "carta_momento" and s.cartas[0].carta.nombre in s.texto

def test_la_carta_del_momento_se_ve_en_el_overlay():
    from backend.overlay import vista
    w = Worker(Cola(), GenFijo(), palabras_por_seg=0, relleno=timedelta(seconds=10))
    correr(w, 0); correr(w, 10); correr(w, 20)
    w.hablando = w.salidas[-1]
    h = vista(w.cola, w, T0 + timedelta(seconds=21))["hablando"]
    assert h["tipo"] == "carta_momento" and len(h["cartas"]) == 1 and h["nivel"] == "Carta del momento" and h["pregunta"] == ""


# ---------- live del 12 de octubre (astrologos5) ----------
def test_anio_solo_dentro_de_la_pregunta_recibe_el_aviso_de_lo_que_falta():
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    comentar(c, "Aleyda del 86 quiero saber si mi esposo yobani me ama", 0)
    correr(w, 1)
    assert [s.tipo for s in w.salidas] == ["pide_fecha"] and "ya tengo el año" in w.salidas[0].texto

def test_sin_voz_no_se_anuncia_el_turno():
    c, w = preparar("mi novio me sigue queriendo?")
    correr(w)
    assert [s.tipo for s in w.salidas] == ["lectura"]


# ---------- live del 12 de octubre (cisne_blanco_) ----------
def test_a_quien_tiene_un_emoji_por_nombre_se_le_dice_corazon():
    gen = GenFijo()
    c = Cola(espera_fecha=None)
    w = Worker(c, gen, palabras_por_seg=0)
    c.procesar({"tipo": "gift", "user": "_jenn", "nickname": "🖤", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    correr(w, 1)
    assert w.salidas[-1].tipo == "pide_pregunta" and w.salidas[-1].texto.startswith("corazón, gracias por tu regalo")
    correr(w, 181)
    assert "llámala \"corazón\"" in gen.prompts[0]["messages"][0]["content"]
    w.bienvenida = timedelta(seconds=60)
    w.llegada("x", "🦋✨")
    assert w._llegadas == {}                                    # sin nombre que decir, no se le saluda


# ---------- temas legales: sí o no muy corto ----------
def test_tema_legal_se_lee_corto_aunque_el_regalo_sea_grande():
    gen = GenFijo()
    c = Cola(espera_fecha=None)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "pedro de 10/06/86 solucionare mi asunto legal?", 0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Leon", "valor": 200, "ts": T0.isoformat()})
    correr(w)
    s = w.salidas[-1]
    assert s.tipo == "lectura" and s.nivel == "Sí o no" and [t.posicion for t in s.cartas] == ["respuesta"]
    contenido = gen.prompts[0]["messages"][0]["content"]
    assert "Es un tema legal: responde muy corto" in contenido and "entre 30 y 45 palabras" in contenido
    assert "<cierre_de_fe>" not in contenido and "abogado" in contenido

def test_al_que_regala_sin_preguntar_se_le_dice_cuanto_tiempo_tiene():
    c = Cola()
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "Lupita", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    correr(w, 1)
    assert w.salidas[-1].texto == "Lupita, gracias por tu regalo. Tienes 3 minutos para enviarme tu pregunta con tu fecha de nacimiento; si no, te leo el mensaje que las cartas tienen para ti."
    c2 = Cola(espera_pregunta=timedelta(seconds=90))
    w2 = Worker(c2, GenFijo(), palabras_por_seg=0)
    c2.procesar({"tipo": "gift", "user": "u", "nickname": "Lupita", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    correr(w2, 42)                                            # la voz venía ocupada: ya pasaron 42 s
    assert "Tienes 50 segundos para" in w2.salidas[-1].texto

def test_la_lista_de_turnos_lleva_la_cuenta_regresiva():
    from backend.overlay import vista
    c = Cola()
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "Lupita", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    assert vista(c, w, T0 + timedelta(seconds=19))["turnos"][0]["restante"] == 161
    comentar(c, "soy Lupita 12/12/99 me va a buscar Samuel?", 20)
    assert vista(c, w, T0 + timedelta(seconds=21))["turnos"][0]["restante"] is None


# ---------- novedades del live del 12-oct-2026 (hadaencantadatarot) ----------
def test_al_menor_se_le_avisa_una_sola_vez_por_live():
    # andres02higuita (11/11/2008) siguió escribiendo y la voz le repitió el aviso cuatro veces
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    comentar(c, "Andrés Higuita 11/11/2008 me va a buscar ella?", 0)
    correr(w, 1)
    comentar(c, "Andrés Higuita 11/11/2008 ella me quiere?", 60)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Doughnut", "valor": 30, "ts": (T0 + timedelta(seconds=61)).isoformat()})
    correr(w, 62)
    assert [s.tipo for s in w.salidas] == ["mensaje_fijo"]
    assert [s["categoria"] for s in w.saltados] == ["menor", "menor"]

def test_la_voz_dice_barajando_para_y_tap_tap():
    from backend import frases as f
    assert all("arajando para {n}" in x for x in f.BARAJANDO)
    todas = f.BOOST_INICIO + f.BOOST_GANO + f.BOOST_GANO_SIN_PREGUNTA
    assert all("like" not in x.replace("{likes}", "").lower() for x in todas)
    assert all("{likes} tap tap" in x for x in f.BOOST_GANO + f.BOOST_GANO_SIN_PREGUNTA)


# ---------- sin live: la voz no le habla a nadie (13-oct-2026: el backend corrió sin ingesta) ----------
def test_sin_eventos_del_live_la_voz_deja_de_rellenar_y_vuelve_al_llegar_gente():
    from backend.boost import Boost
    c = Cola()
    w = Worker(c, GenFijo(), palabras_por_seg=0, relleno=timedelta(seconds=3), sin_live=timedelta(minutes=3),
               boost=Boost(cada=timedelta(minutes=1)), aviso_gratis=timedelta(minutes=5))
    assert asyncio.run(w.paso(T0)) is False                                     # arranca el plazo
    assert asyncio.run(w.paso(T0 + timedelta(seconds=10))) is True              # dentro del plazo sí rellena
    antes = len(w.salidas)
    for seg in (200, 400, 900):                                                 # pasó el plazo sin un solo evento
        assert asyncio.run(w.paso(T0 + timedelta(seconds=seg))) is False
    assert len(w.salidas) == antes and w.boost.inicio is None
    w.senal(T0 + timedelta(seconds=901))                                        # llegó alguien: vuelve
    assert asyncio.run(w.paso(T0 + timedelta(seconds=905))) is True

def test_si_la_ingesta_avisa_que_el_live_termino_se_calla_pero_lee_lo_pendiente():
    c = Cola(espera_fecha=None)
    w = Worker(c, GenFijo(), palabras_por_seg=0, relleno=timedelta(seconds=3))
    w.senal(T0)
    comentar(c, "soy Ana 05/05/90 me va a buscar Juan?", 0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    w.conexion(False, T0 + timedelta(seconds=1))
    assert not w.en_vivo(T0 + timedelta(seconds=2))
    assert asyncio.run(w.paso(T0 + timedelta(seconds=2))) is True and w.salidas[-1].tipo == "lectura"
    n = len(w.salidas)
    assert asyncio.run(w.paso(T0 + timedelta(seconds=60))) is False and len(w.salidas) == n
    w.conexion(True, T0 + timedelta(seconds=70))
    assert asyncio.run(w.paso(T0 + timedelta(seconds=80))) is True


# ---------- novedades del live del 13-oct-2026 (soyluzespiritual) ----------
def test_fecha_con_el_anio_primero():
    from astro.signos import extraer
    from datetime import date
    # anamariaalvistobar ganó el boost y salió de la fila "por no dar su fecha", que sí había dado
    assert extraer("Hola soy Ana de Colombia 1998-04-09 Colombia quiero saber si tendré trabajo pronto").fecha == date(1998, 4, 9)
    assert extraer("1998/4/9").fecha == date(1998, 4, 9) and extraer("soy Ana 05/05/90 y Juan?").fecha == date(1990, 5, 5)

def test_si_se_le_pidio_la_fecha_la_que_escribe_despues_es_suya_aunque_nombre_a_otro():
    # fernandahormazabal0: "Mi ex Carlos volverá" → se le pide la fecha → "Mi ex Carlos volverá a buscarme 12 06 90"
    from datetime import date
    c = Cola(espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    comentar(c, "Mi ex Carlos volverá a buscarme?", 0)
    correr(w, 1)
    assert w.salidas[-1].tipo == "pide_fecha"
    comentar(c, "Mi ex Carlos volverá a buscarme 12 06 90", 20)
    correr(w, 21)
    assert w.salidas[-1].tipo == "lectura" and w.salidas[-1].signo == "Géminis"
    # sin que se la hayan pedido, una fecha después de "mi ex" sigue siendo de la otra persona
    c2 = Cola(espera_gratis=CERO)
    comentar(c2, "Mi ex Carlos volverá a buscarme 12 06 90", 0)
    assert c2.pendientes(T0)[0].dato is None

def test_paternidad_no_se_lee():
    from backend.filtro import evaluar
    for t in ["hola rosa 18-05-96 la niña q tengo es de luis", "quiero saber si el bebe es de el", "de quien es el bebe que espero",
              "el es el papa de mi hijo?", "me sale la prueba de adn"]:
        assert (evaluar(t).categoria, evaluar(t).accion) == ("paternidad", "saltar"), t
    for t in ["mi hijo es feliz?", "mi hija es de signo leo", "mi hijo volvera a casa?", "mi hija sera feliz con el", "dame un chance de leerme"]:
        assert not evaluar(t).sensible, t

def test_se_le_habla_por_el_nombre_con_que_se_presento():
    from astro.signos import nombre_dicho
    assert nombre_dicho("Soy Lizet Mi pareja Brayan Rosas tiene sentimientos por mi") == "Lizet"
    assert nombre_dicho("buenas tardes soy Iván de el 22 de Mayo del 1984") == "Iván"
    assert [nombre_dicho(t) for t in ("soy de bolivia", "soy libra", "soy muy feliz", "soy madre soltera", "Carlos volverá?")] == [None] * 5
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    c.procesar({"tipo": "comment", "user": "laura_2000", "nickname": "Laura", "texto": "Soy Lizet 05/05/90 Brayan volverá a buscarme?", "ts": T0.isoformat()})
    correr(w, 1)
    assert w.salidas[-1].tipo == "lectura" and w.salidas[-1].nickname == "Lizet" and w.salidas[-1].user == "laura_2000"

def test_el_plazo_se_dice_en_minutos_enteros():
    c = Cola()
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "Fer", "regalo": "Rose", "valor": 2, "ts": T0.isoformat()})
    correr(w, 40)                                             # quedan 140 s: antes decía "140 segundos"
    assert "Tienes 2 minutos para" in w.salidas[-1].texto


# ---------- ajustes de Caro tras el live del 13-oct-2026 ----------
def test_embarazo_va_por_dm_con_cualquier_regalo_y_sin_pedir_fecha():
    from backend.frases import LECTURA_PRIVADA
    assert all("embaraz" not in f.lower() and "mensaje directo" in f for f in LECTURA_PRIVADA)
    gen = GenFijo()
    c = Cola(espera_fecha=ESPERA)
    w = Worker(c, gen, palabras_por_seg=0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "Susel", "regalo": "Doughnut", "valor": 30, "ts": T0.isoformat()})
    comentar(c, "saber si estoy embarazada?", 20)
    correr(w, 21)
    assert w.salidas[-1].tipo == "mensaje_fijo" and w.salidas[-1].texto.startswith("Susel, ") and gen.prompts == []
    assert 'Nunca escribas las palabras "embarazo"' in armar_prompt_sistema()

def armar_prompt_sistema():
    from backend.prompt import SISTEMA
    return SISTEMA

def test_compatibilidad_sin_regalo_invita_a_la_sinastria_y_con_regalo_se_lee():
    gen = GenFijo()
    c = Cola(espera_fecha=ESPERA, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "Entre libra y escorpión reinita somos compatibles en el amor?", 0)     # lizethpena00: sin fecha
    correr(w, 1)
    assert w.salidas[-1].tipo == "mensaje_fijo" and "sinastría" in w.salidas[-1].texto and "mensaje directo" in w.salidas[-1].texto
    assert gen.prompts == []
    c2 = Cola(espera_fecha=None)
    w2 = Worker(c2, gen, palabras_por_seg=0)
    comentar(c2, "soy Ana 05/05/90 somos compatibles Juan y yo?", 0)
    c2.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 5, "ts": T0.isoformat()})
    correr(w2, 1)
    assert w2.salidas[-1].tipo == "lectura"

def test_loteria_y_chance_se_leen_con_prudencia_y_lo_legal_sigue_corto():
    from backend.filtro import evaluar
    for t in ["me voy a ganar la lotería?", "hola Fernanda 07-06 94 me ganara el chance", "me conviene invertir en ese negocio?"]:
        assert not evaluar(t).sensible, t
    for t in ["ganaré la demanda?", "me quedo con la herencia?"]:
        assert evaluar(t).accion == "breve", t
    gen = GenFijo()
    c, w = preparar("soy Fernanda 07-06-94 me ganaré el chance?", gen)
    correr(w)
    assert w.salidas[-1].tipo == "lectura"
    assert "Nunca afirmes que va a ganar" in gen.prompts[0]["system"] and '"inversion"' not in gen.prompts[0]["system"]

def test_la_frase_de_fe_solo_se_ofrece_a_quien_carga_algo_que_pesa():
    from backend.prompt import pesa
    assert all(pesa(t) for t in ["voy a superar esta tristeza?", "mi mamá va a estar bien?", "me siento muy sola", "él me fue infiel, lo perdono?"])
    assert not any(pesa(t) for t in ["me va a escribir Andrés?", "volveré con mi ex?", "Natalia volverá conmigo", ""])
    gen = GenFijo()
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    comentar(c, "me va a escribir Andrés este mes?", 0)
    correr(w)
    assert "<cierre_de_fe>" not in gen.prompts[0]["messages"][0]["content"]

def test_heart_me_se_dice_quiereme():
    from backend.prompt import REGALOS_ES
    assert REGALOS_ES["heart me"] == "quiéreme"


# ---------- novedades del live del 13-oct-2026 por la tarde (florencia.tarot) ----------
def test_enfermera_no_es_un_tema_de_salud_ni_un_nombre():
    from backend.filtro import evaluar
    from astro.signos import nombre_dicho
    for t in ["quiero saber si voy a encontrar trabajo soy Enfermera", "me sale trabajo como enfermera con mi nueva matricula",
              "voy a terminar enfermería?"]:
        assert not evaluar(t).sensible, t
    assert evaluar("mi mamá está enferma, se va a mejorar?").categoria == "salud"
    assert evaluar("tengo una enfermedad").categoria == "salud"
    assert nombre_dicho("quiero saber si voy a encontrar trabajo soy Enfermera") is None

def test_quien_gana_el_boost_sin_pregunta_tiene_tiempo_para_escribirla():
    # DominicRH: regaló, se le venció el plazo, ganó el boost ("déjame tu pregunta") y 18 s después se le leyó el mensaje general
    c = Cola()
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    c.procesar({"tipo": "gift", "user": "dom", "nickname": "Dominic", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    ahora = T0 + timedelta(seconds=250)                              # ya pasaron los 3 minutos
    assert c.dar_pase("dom", "Dominic", ahora) is False
    assert c.tomar_siguiente(ahora + timedelta(seconds=20)) is None       # espera su pregunta
    comentar_de = lambda texto, seg: c.procesar({"tipo": "comment", "user": "dom", "nickname": "Dominic", "texto": texto,
                                                 "ts": (T0 + timedelta(seconds=seg)).isoformat()})
    comentar_de("soy Dominic 05/05/90 me va a buscar Juan?", 280)
    item = c.tomar_siguiente(T0 + timedelta(seconds=281))
    assert item is not None and item.pregunta and item.prioridad

def test_repetir_la_pregunta_mientras_se_la_leen_no_abre_otro_turno():
    c = Cola(espera_fecha=None)
    comentar(c, "El se comunicará conmigo hoy?", 0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Money Gun", "valor": 500, "ts": T0.isoformat()})
    assert c.tomar_siguiente(T0 + timedelta(seconds=1)) is not None
    comentar(c, "El se comunicará conmigo hoy?", 5)
    c.cerrar("u", "hecho")
    assert c.pendientes(T0 + timedelta(seconds=10)) == []

def test_a_quien_no_pregunto_no_se_le_reprocha():
    gen = GenFijo()
    c = Cola(espera_pregunta=CERO)
    w = Worker(c, gen, palabras_por_seg=0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "Tai", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})
    correr(w, 5)
    contenido = gen.prompts[-1]["messages"][0]["content"]
    assert "No se lo digas ni se lo reproches" in contenido


# ---------- regalos pequeños sin pregunta: una carta corta para el grupo (decisión de Caro, 13-oct-2026) ----------
def _regalar(c, user, nick, regalo="Heart Me", valor=1, seg=0):
    c.procesar({"tipo": "gift", "user": user, "nickname": nick, "regalo": regalo, "valor": valor,
                "ts": (T0 + timedelta(seconds=seg)).isoformat()})

def test_regalos_pequenos_sin_pregunta_se_leen_juntos_y_corto():
    gen = GenFijo()
    c = Cola()
    w = Worker(c, gen, palabras_por_seg=0)
    for n, nick in enumerate(["Tai", "Bety", "Aline"]):
        _regalar(c, f"u{n}", nick, seg=n)
    _regalar(c, "grande", "Karol", "Rhythm Bot", 199, seg=3)          # un regalo grande no entra al grupo
    correr(w, 5)
    assert w.salidas[-1].tipo == "pide_pregunta" and "Tienen 3 minutos" in w.salidas[-1].texto     # primero se les da su tiempo
    antes = len(gen.prompts)
    asyncio.run(w.paso(T0 + timedelta(seconds=200)))                   # venció el plazo: va primero el regalo grande
    assert w.salidas[-1].nickname == "Karol" and len(w.salidas[-1].cartas) == 6
    asyncio.run(w.paso(T0 + timedelta(seconds=201)))
    s = w.salidas[-1]
    assert s.tipo == "lectura" and s.nickname == "Tai, Bety y Aline" and len(s.cartas) == 1
    contenido = gen.prompts[-1]["messages"][0]["content"]
    assert "<personas>Tai, Bety, Aline</personas>" in contenido and "entre 45 y 65 palabras" in contenido
    assert "les lees a varias personas a la vez" in contenido and len(gen.prompts) == antes + 2    # una sola llamada para las tres
    assert c.pendientes(T0 + timedelta(seconds=202)) == [] and [i.estado for i in c.historial[-3:]] == ["hecho"] * 3

def test_regalo_pequeno_sin_pregunta_solo_tambien_es_corto_y_con_pregunta_no_se_agrupa():
    gen = GenFijo()
    c = Cola(espera_fecha=None)
    w = Worker(c, gen, palabras_por_seg=0)
    _regalar(c, "a", "Tai")
    _regalar(c, "b", "Bety", seg=1)
    c.procesar({"tipo": "comment", "user": "b", "nickname": "Bety", "texto": "soy Bety 05/05/90 me va a buscar Juan?",
                "ts": (T0 + timedelta(seconds=30)).isoformat()})
    asyncio.run(w.paso(T0 + timedelta(seconds=200)))
    asyncio.run(w.paso(T0 + timedelta(seconds=201)))
    asyncio.run(w.paso(T0 + timedelta(seconds=202)))
    lecturas = [s for s in w.salidas if s.tipo == "lectura"]
    assert sorted(s.nickname for s in lecturas) == ["Bety", "Tai"]
    sola = next(p for p in gen.prompts if "<persona>Tai</persona>" in p["messages"][0]["content"])
    assert "entre 30 y 45 palabras" in sola["messages"][0]["content"]
    con_pregunta = next(p for p in gen.prompts if "me va a buscar Juan" in p["messages"][0]["content"])
    assert "entre 30 y 45" not in con_pregunta["messages"][0]["content"]

def test_el_cielo_del_dia_se_nombra_en_una_de_cada_tres_lecturas():
    gen = GenFijo()
    c = Cola(espera_fecha=None, espera_gratis=CERO, max_gratis=10)
    w = Worker(c, gen, palabras_por_seg=0)
    for n in range(6):
        c.procesar({"tipo": "comment", "user": f"u{n}", "nickname": f"Ana{n}", "texto": "soy Ana 05/05/90 me va a buscar Juan?", "ts": T0.isoformat()})
        asyncio.run(w.paso(T0 + timedelta(seconds=n + 1)))
    con = ["Fase lunar" in p["messages"][0]["content"] for p in gen.prompts]
    assert con == [True, False, False, True, False, False]
    assert "no menciones planetas" in gen.prompts[1]["messages"][0]["content"] and "no menciones planetas" not in gen.prompts[0]["messages"][0]["content"]

def test_eventos_astrologicos_solo_con_api_configurada(monkeypatch):
    from datetime import date
    from astro import eventos as ev
    monkeypatch.delenv("ASTRO_API_URL", raising=False)
    assert ev.desde_entorno() is None                                  # lo de hoy: sin API, nada cambia
    leidos = ev._leer({"events": [{"date": "2026-10-14", "title": "Luna nueva en Libra", "description": "Buen día para empezar."},
                                  {"title": "sin fecha"}, {"date": "mal", "title": "x"}]})
    assert [e.titulo for e in leidos] == ["Luna nueva en Libra"]
    assert leidos[0].frase(date(2026, 10, 13)) == "Mañana tenemos Luna nueva en Libra. Buen día para empezar."

    class Falsa:
        def __init__(self): self.n = 0
        async def siguiente(self, ahora):
            self.n += 1
            return "Hoy tenemos Luna nueva en Libra." if self.n == 1 else None
    w = Worker(Cola(), GenFijo(), palabras_por_seg=0, relleno=timedelta(seconds=3), eventos=Falsa())
    asyncio.run(w.paso(T0))
    asyncio.run(w.paso(T0 + timedelta(seconds=10)))
    assert w.salidas[-1].texto == "Hoy tenemos Luna nueva en Libra."
    asyncio.run(w.paso(T0 + timedelta(seconds=20)))                    # ya no hay evento nuevo: sigue el relleno de siempre
    assert w.salidas[-1].texto != "Hoy tenemos Luna nueva en Libra."
