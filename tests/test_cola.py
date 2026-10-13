from datetime import datetime, timedelta, timezone
from backend.cola import Cola, es_pregunta

CERO = timedelta(0)
T0 = datetime(2026, 10, 9, 0, 40, tzinfo=timezone.utc)

def ev(tipo, user, seg, texto="", regalo="", valor=0):
    return {"tipo": tipo, "user": user, "nickname": user, "texto": texto,
            "regalo": regalo, "valor": valor,
            "ts": (T0 + timedelta(seconds=seg)).isoformat()}

def test_regalo_y_luego_pregunta():          # ojozdekira
    c = Cola()
    c.procesar(ev("gift", "ojo", 0, regalo="Rose", valor=1))
    c.procesar(ev("comment", "ojo", 1, texto="cual es mi panorama en economía"))
    [item] = c.pendientes(T0 + timedelta(seconds=2))
    assert item.valor == 1 and "economía" in item.pregunta

def test_pregunta_y_luego_regalo():
    c = Cola()
    c.procesar(ev("comment", "ayu", 0, texto="soy aries leeme las cartas"))
    c.procesar(ev("gift", "ayu", 30, regalo="Rose", valor=1))
    assert len(c.pendientes(T0 + timedelta(seconds=31))) == 1

def test_spam_un_solo_item():               # viviana x9
    c = Cola()
    c.procesar(ev("gift", "viv", 0, regalo="Rose", valor=1))
    for s in range(1, 10):
        c.procesar(ev("comment", "viv", s, texto="que sintió hoy que me vio es mi ex"))
    assert len(c.pendientes(T0 + timedelta(seconds=11))) == 1

def test_regalos_se_suman():                # araceli, dos rachas
    c = Cola()
    c.procesar(ev("comment", "ara", 0, texto="me va a buscar este mes"))
    c.procesar(ev("gift", "ara", 1, regalo="Rose", valor=1))
    c.procesar(ev("gift", "ara", 4, regalo="Rose", valor=1))
    [item] = c.pendientes(T0 + timedelta(seconds=5))
    assert item.valor == 2

def test_regalo_sin_pregunta_es_lectura_general():
    c = Cola()
    c.procesar(ev("gift", "alma", 0, regalo="Rose", valor=3))
    [item] = c.pendientes(T0 + timedelta(seconds=1))          # entra a la fila de inmediato
    assert item.pregunta == "" and item.valor == 3 and c.falta(item) == ["pregunta"]
    assert c.tomar_siguiente(T0 + timedelta(seconds=179)) is None     # se le dan 180 s para preguntar
    assert c.tomar_siguiente(T0 + timedelta(seconds=180)) is item

def test_orden_por_valor_y_ts():
    c = Cola()
    for u, s, v in [("a", 0, 1), ("b", 1, 5), ("c", 2, 1)]:
        c.procesar(ev("comment", u, s, texto="pregunta de prueba larga"))
        c.procesar(ev("gift", u, s, regalo="Rose", valor=v))
    assert [i.user for i in c.pendientes(T0 + timedelta(seconds=3))] == ["b", "a", "c"]

def test_no_preguntas():
    for t in ["presente", "gracias", "🙏🏻🙏🏻", "yo", "Presente"]:
        assert not es_pregunta(t)
        
def test_gracias_no_borra_la_pregunta():          # julio.saavedra95
    c = Cola()
    c.procesar(ev("comment", "jul", 0, texto="me irá bien en el trabajo nuevo?"))
    c.procesar(ev("gift", "jul", 1, regalo="Rose", valor=1))
    c.procesar(ev("comment", "jul", 5, texto="ok gracias por su respuesta"))
    [item] = c.pendientes(T0 + timedelta(seconds=6))
    assert item.pregunta == "me irá bien en el trabajo nuevo?" and item.extras == []

def test_reformulacion_va_a_extras():             # camilagaray231
    c = Cola()
    c.procesar(ev("comment", "cam", 0, texto="Mi papá me obligará a terminar con mi novio?"))
    c.procesar(ev("gift", "cam", 1, regalo="Rose", valor=1))
    c.procesar(ev("comment", "cam", 9, texto="Mi papá me dira que termine con mi novio"))
    [item] = c.pendientes(T0 + timedelta(seconds=10))
    assert "obligará" in item.pregunta and len(item.extras) == 1

def test_lectura_general_recibe_pregunta_tardia():
    c = Cola()
    c.procesar(ev("gift", "ani", 0, regalo="White Rose", valor=1))
    c.pendientes(T0 + timedelta(seconds=121))
    c.procesar(ev("comment", "ani", 130, texto="péndulo me responde si o no"))
    [item] = c.pendientes(T0 + timedelta(seconds=131))
    assert item.pregunta == "péndulo me responde si o no"

def test_cortesias_reales():
    for t in ["ok gracias por su respuesta", "gracias por tus palabras ❤️", "muchas bendiciones"]:
        assert not es_pregunta(t)
    assert es_pregunta("hola soy rosita Jonathan me quiere como pareja y me ama enserio o no")
    
def test_msg_id_repetido_no_suma_dos_veces():
    c = Cola()
    c.procesar(ev("comment", "r", 0, texto="me va a buscar este mes"))
    g = ev("gift", "r", 1, regalo="Rose", valor=5)
    g["msg_id"] = 123
    c.procesar(g)
    c.procesar(g)
    [item] = c.pendientes(T0 + timedelta(seconds=2))
    assert item.valor == 5

def test_item_guarda_signo_de_la_pareja():
    c = Cola()
    c.procesar(ev("comment", "ana", 0, texto="Ana 05/05/90, Carlos 02/07/88, volveremos?"))
    c.procesar(ev("gift", "ana", 1, regalo="Rose", valor=1))
    [item] = c.pendientes(T0 + timedelta(seconds=2))
    assert item.dato.signo == "Tauro" and item.pareja.signo == "Cáncer" and item.pareja.fecha is None

def test_pareja_llega_despues():
    c = Cola()
    c.procesar(ev("comment", "ana", 0, texto="soy Ana 05/05/90 volveremos?"))
    c.procesar(ev("gift", "ana", 1, regalo="Rose", valor=1))
    c.procesar(ev("comment", "ana", 5, texto="mi ex es del 02/07/88"))
    [item] = c.pendientes(T0 + timedelta(seconds=6))
    assert item.dato.signo == "Tauro" and item.pareja.signo == "Cáncer"


def test_pregunta_tras_60s_se_toma_si_aun_no_le_leen():
    c = Cola()
    c.procesar(ev("gift", "lu", 0, regalo="Rose", valor=4))
    c.procesar(ev("comment", "lu", 90, texto="soy Lu 05/05/90 me va a buscar Juan?"))
    item = c.tomar_siguiente(T0 + timedelta(seconds=91))
    assert "Juan" in item.pregunta and item.dato.signo == "Tauro" and c.falta(item) == []

def test_sin_pregunta_no_frena_a_los_que_ya_estan_listos():
    c = Cola(espera_fecha=None)
    c.procesar(ev("gift", "rico", 0, regalo="Hand Heart", valor=100))          # más valor, sin pregunta
    c.procesar(ev("comment", "ana", 1, texto="me va a buscar este mes"))
    c.procesar(ev("gift", "ana", 2, regalo="Rose", valor=1))
    assert [i.user for i in c.pendientes(T0 + timedelta(seconds=3))] == ["rico", "ana"]
    assert c.tomar_siguiente(T0 + timedelta(seconds=3)).user == "ana"         # rico sigue con tiempo
    c.cerrar("ana")
    assert c.tomar_siguiente(T0 + timedelta(seconds=181)).user == "rico"

def test_falta_fecha_solo_si_hay_pregunta():
    c = Cola()
    c.procesar(ev("gift", "a", 0, regalo="Rose", valor=1))
    c.procesar(ev("comment", "b", 0, texto="me va a buscar este mes"))
    c.procesar(ev("gift", "b", 1, regalo="Rose", valor=1))
    faltas = {i.user: c.falta(i) for i in c.pendientes(T0 + timedelta(seconds=2))}
    assert faltas == {"a": ["pregunta"], "b": ["fecha"]}
    assert [i.user for i in c.sin_fecha(T0 + timedelta(seconds=2))] == ["b"]
    assert [i.user for i in c.sin_pregunta(T0 + timedelta(seconds=2))] == ["a"]

def test_regalo_mientras_le_leen_abre_turno_nuevo_al_cerrar():
    c = Cola(espera_fecha=None)
    c.procesar(ev("comment", "u", 0, texto="me va a buscar este mes"))
    c.procesar(ev("gift", "u", 1, regalo="Rose", valor=1))
    primero = c.tomar_siguiente(T0 + timedelta(seconds=2))
    c.procesar(ev("gift", "u", 5, regalo="Doughnut", valor=30))
    assert primero.valor == 1 and c.pendientes(T0 + timedelta(seconds=6)) == []
    c.cerrar("u")
    [nuevo] = c.pendientes(T0 + timedelta(seconds=7))
    assert nuevo.valor == 30 and nuevo.pregunta == ""


def test_segunda_pregunta_junto_a_la_fecha_va_a_extras():
    c = Cola()
    c.procesar(ev("comment", "ana", 0, texto="¿me irá bien con Juan?"))
    c.procesar(ev("gift", "ana", 1, regalo="Doughnut", valor=30))
    c.procesar(ev("comment", "ana", 5, texto="soy Ana 05/05/90 y en el trabajo, ¿me ascenderán?"))
    [item] = c.pendientes(T0 + timedelta(seconds=6))
    assert item.dato.signo == "Tauro" and item.pregunta == "¿me irá bien con Juan?"
    assert item.extras == ["soy Ana 05/05/90 y en el trabajo, ¿me ascenderán?"]

def test_la_fecha_sola_no_cuenta_como_segunda_pregunta():
    for respuesta in ("05/05/90", "soy Ana María López 05/05/1990", "nací el 5 de mayo de 1990", "soy tauro",
                      "mi fecha de nacimiento es 05/05/90"):
        c = Cola()
        c.procesar(ev("comment", "ana", 0, texto="¿me irá bien con Juan?"))
        c.procesar(ev("gift", "ana", 1, regalo="Doughnut", valor=30))
        c.procesar(ev("comment", "ana", 5, texto=respuesta))
        [item] = c.pendientes(T0 + timedelta(seconds=6))
        assert item.dato.signo == "Tauro" and item.extras == [], respuesta

def test_segunda_pregunta_con_fecha_sin_signo_de_interrogacion():
    c = Cola()
    c.procesar(ev("comment", "ana", 0, texto="¿me irá bien con Juan?"))
    c.procesar(ev("gift", "ana", 1, regalo="Doughnut", valor=30))
    c.procesar(ev("comment", "ana", 5, texto="05/05/90 quiero saber si me van a ascender en el trabajo"))
    [item] = c.pendientes(T0 + timedelta(seconds=6))
    assert len(item.extras) == 1


def test_gratis_no_espera_a_quien_regalo_y_aun_no_pregunta():
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    c.procesar(ev("comment", "libre", 0, texto="me va a buscar este mes?"))
    c.procesar(ev("gift", "paga", 1, regalo="Rose", valor=1))            # en la fila, sin pregunta todavía
    assert [(i.user, i.valor) for i in c.pendientes(T0 + timedelta(seconds=2))] == [("paga", 1), ("libre", 0)]
    item = c.tomar_siguiente(T0 + timedelta(seconds=2))
    assert item.user == "libre" and item.regalos == [] and item.estado == "leyendo"

def test_regalo_listo_va_antes_que_la_gratis():
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    c.procesar(ev("comment", "libre", 0, texto="me va a buscar este mes?"))
    c.procesar(ev("comment", "paga", 5, texto="le gusto a Pedro o no?"))
    c.procesar(ev("gift", "paga", 6, regalo="Rose", valor=1))
    assert c.tomar_siguiente(T0 + timedelta(seconds=7)).user == "paga"
    c.cerrar("paga")
    assert c.tomar_siguiente(T0 + timedelta(seconds=8)).user == "libre"

def test_gratis_tambien_necesita_fecha():
    c = Cola(espera_gratis=CERO)
    c.procesar(ev("comment", "ana", 0, texto="me va a buscar este mes?"))
    [item] = c.sin_fecha(T0 + timedelta(seconds=1))
    assert item.valor == 0 and c.falta(item) == ["fecha"]
    assert c.tomar_siguiente(T0 + timedelta(seconds=1)) is None
    c.procesar(ev("comment", "ana", 20, texto="05/05/90"))
    tomado = c.tomar_siguiente(T0 + timedelta(seconds=21))
    assert tomado is item and tomado.dato.signo == "Tauro"

def test_una_sola_pregunta_gratis_por_persona():
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    c.procesar(ev("comment", "ana", 0, texto="me va a buscar este mes?"))
    assert c.tomar_siguiente(T0 + timedelta(seconds=1)).user == "ana"
    c.cerrar("ana")
    c.procesar(ev("comment", "ana", 30, texto="y con mi familia cómo me irá?"))
    assert c.pendientes(T0 + timedelta(seconds=31)) == []
    c.procesar(ev("gift", "ana", 40, regalo="Rose", valor=1))                   # con regalo sí vuelve a entrar
    [item] = c.pendientes(T0 + timedelta(seconds=41))
    assert item.valor == 1 and item.pregunta == "y con mi familia cómo me irá?"

def test_regalar_antes_del_turno_gratis_no_lo_gasta():
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    c.procesar(ev("comment", "ana", 0, texto="me va a buscar este mes?"))
    assert c.pendientes(T0 + timedelta(seconds=1))[0].valor == 0
    c.procesar(ev("gift", "ana", 2, regalo="Rose", valor=5))
    assert c.tomar_siguiente(T0 + timedelta(seconds=3)).valor == 5
    c.cerrar("ana")
    c.procesar(ev("comment", "ana", 10, texto="y en el trabajo me irá bien?"))
    assert c.tomar_siguiente(T0 + timedelta(seconds=11)).valor == 0             # su gratis seguía intacta

def test_cupo_de_gratis_en_la_fila():
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    for n in range(5):
        c.procesar(ev("comment", f"u{n}", n, texto="me va a buscar este mes?"))
    assert [i.user for i in c.pendientes(T0 + timedelta(seconds=6))] == ["u0", "u1", "u2"]
    c.tomar_siguiente(T0 + timedelta(seconds=6))
    c.cerrar("u0")
    assert [i.user for i in c.pendientes(T0 + timedelta(seconds=7))] == ["u1", "u2", "u3"]
    assert [i.user for i in c.pendientes(T0 + timedelta(seconds=300))] == ["u1", "u2", "u3"]   # u4 caducó
    sin = Cola(max_gratis=0)
    sin.procesar(ev("comment", "a", 0, texto="me va a buscar este mes?"))
    assert sin.pendientes(T0 + timedelta(seconds=1)) == []

def test_sin_fecha_no_hay_lectura_gratis():
    c = Cola(espera_gratis=CERO)
    c.procesar(ev("comment", "ana", 0, texto="me va a buscar este mes?"))
    [item] = c.sin_fecha(T0 + timedelta(seconds=1))
    item.pedido_fecha = T0 + timedelta(seconds=1)                 # la voz le pide la fecha
    assert c.tomar_siguiente(T0 + timedelta(seconds=90)) is None
    assert c.tomar_siguiente(T0 + timedelta(seconds=92)) is None and c.pendientes(T0 + timedelta(seconds=92)) == []
    c.procesar(ev("comment", "ana", 100, texto="y entonces me va a buscar?"))
    assert c.pendientes(T0 + timedelta(seconds=101)) == []        # sin fecha no vuelve a ocupar la fila
    c.procesar(ev("comment", "ana", 110, texto="05/05/90"))
    c.procesar(ev("comment", "ana", 115, texto="me va a buscar este mes?"))
    tomado = c.tomar_siguiente(T0 + timedelta(seconds=116))       # no había gastado su turno
    assert tomado.valor == 0 and tomado.dato.signo == "Tauro"

def test_con_regalo_si_se_lee_sin_fecha_al_vencer_el_plazo():
    c = Cola(espera_gratis=CERO)
    c.procesar(ev("comment", "ana", 0, texto="me va a buscar este mes?"))
    c.procesar(ev("gift", "ana", 1, regalo="Rose", valor=1))
    [item] = c.sin_fecha(T0 + timedelta(seconds=2))
    item.pedido_fecha = T0 + timedelta(seconds=2)
    assert c.tomar_siguiente(T0 + timedelta(seconds=93)) is item

def test_regalo_justo_despues_de_la_pregunta_no_gasta_la_gratis():
    c = Cola(espera_fecha=None)
    c.procesar(ev("comment", "ana", 0, texto="me va a buscar este mes?"))
    assert c.tomar_siguiente(T0 + timedelta(seconds=5)) is None      # margen para que llegue el regalo
    c.procesar(ev("gift", "ana", 6, regalo="Doughnut", valor=30))
    item = c.tomar_siguiente(T0 + timedelta(seconds=7))
    assert item.valor == 30 and item.pregunta == "me va a buscar este mes?"
    c.cerrar("ana")
    c.procesar(ev("comment", "ana", 60, texto="y en el trabajo me irá bien?"))
    assert c.tomar_siguiente(T0 + timedelta(seconds=70)) is None
    assert c.tomar_siguiente(T0 + timedelta(seconds=75)).valor == 0


# ---------- casos reales de los logs (lives del 8, 9 y 11 de octubre) ----------
def test_charla_del_live_no_es_pregunta():
    for t in ["Buenos días", "Holaa bendiciones", "Graciass", "m GRACIAS", "okey gracias", "nueva seguidora 🥺",
              "@Silvana rojas ah okii", "@Y ya te leen ahorita", "@Universo de Betito 🪬🔮",
              "cual es la lectura gratis?", "Disculpe hay gratis?", "Mi pregunta gratis nunca sale", "nunca pasa",
              "Cuanto me falta amiga", "yo mandé venadito", "Yo envié quiéreme y dedos coreanos 😞",
              "das respuestas bacanas", "DESPEDIDA BETO", "te envié un venadito",
              "Saludos corazón, hay lista de orden?"]:
        assert not es_pregunta(t), t

def test_preguntas_reales_siguen_entrando():
    from backend.cola import parece_pregunta
    for t in ["Hola conseguiré empleo rápido gracias", "hola Luis Humberto rojas me piensa",
              "buenas noches mi ex aún me ama y volvemos algún día", "Soy yulis del 85 Camilo volverá conmigo",
              "Yisel Suárez ¿Porque alejandro Palacio no me ha buscado?", "leeme alguito", "Rafael me quiere",
              "Hola buenos días como bastar mi trabajo", "le mandé un mensaje a Juan, me responderá?",
              "3/8/83 Eliany saravia hablamos y m dijo venia y nada m ama Alejandro Valera"]:
        assert es_pregunta(t) and parece_pregunta(t), t

def test_afirmacion_sin_senal_vale_con_regalo_pero_no_para_la_gratis():
    from backend.cola import parece_pregunta
    for t in ["mi papá le es infiel a mi mamá", "hoy es mi cumpleaños", "ya dejalo, ya le respondiste"]:
        assert es_pregunta(t) and not parece_pregunta(t), t
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    c.procesar(ev("comment", "a", 0, texto="mi papá le es infiel a mi mamá"))
    assert c.pendientes(T0 + timedelta(seconds=1)) == []
    c.procesar(ev("gift", "a", 2, regalo="Rose", valor=1))
    assert c.pendientes(T0 + timedelta(seconds=3))[0].pregunta == "mi papá le es infiel a mi mamá"

def test_nombre_con_fecha_no_es_pregunta():
    c = Cola(espera_gratis=CERO)
    c.procesar(ev("comment", "jp", 0, texto="Juan Pablo Yepes Valencia 16/09/2004"))
    assert c.pendientes(T0 + timedelta(seconds=1)) == []                    # no entra como pregunta gratis
    c.procesar(ev("comment", "jp", 5, texto="existe un futuro con esa persona?"))
    [item] = c.pendientes(T0 + timedelta(seconds=6))
    assert item.dato.signo == "Virgo" and item.pregunta == "existe un futuro con esa persona?"

def test_regalo_y_luego_solo_la_fecha_sigue_sin_pregunta():
    c = Cola()
    c.procesar(ev("gift", "jp", 0, regalo="Rose", valor=5))
    c.procesar(ev("comment", "jp", 5, texto="Juan Pablo Yepes Valencia 16/09/2004"))
    [item] = c.pendientes(T0 + timedelta(seconds=6))
    assert item.dato.signo == "Virgo" and item.pregunta == "" and c.falta(item) == ["pregunta"]

def test_fecha_con_afirmacion_larga_si_es_pregunta():
    c = Cola()
    c.procesar(ev("gift", "d", 0, regalo="Rose", valor=5))
    c.procesar(ev("comment", "d", 5, texto="soy darinel santiago 07 08 73 mi hija lizbeth tiene los documentos de la casa"))
    [item] = c.pendientes(T0 + timedelta(seconds=6))
    assert item.dato.signo == "Leo" and "documentos" in item.pregunta


# ---------- la pregunta de quien regala (tiempos medidos en los logs) ----------
def test_pregunto_le_leyeron_gratis_y_luego_regalo_conserva_su_pregunta():
    c = Cola(espera_fecha=None)
    c.procesar(ev("comment", "ana", 0, texto="me va a buscar Juan este mes?"))
    gratis = c.tomar_siguiente(T0 + timedelta(seconds=16))
    assert gratis.valor == 0
    c.procesar(ev("gift", "ana", 25, regalo="Doughnut", valor=30))        # regala mientras le leen la gratis
    c.cerrar("ana")
    [pago] = c.pendientes(T0 + timedelta(seconds=40))
    assert pago.valor == 30 and pago.pregunta == "me va a buscar Juan este mes?"
    c.tomar_siguiente(T0 + timedelta(seconds=41))
    c.cerrar("ana")
    c.procesar(ev("gift", "ana", 60, regalo="Rose", valor=1))             # otro regalo no repite la pregunta
    assert c.pendientes(T0 + timedelta(seconds=61))[0].pregunta == ""

def test_regalo_despues_de_la_gratis_ya_cerrada():
    c = Cola(espera_fecha=None)
    c.procesar(ev("comment", "ana", 0, texto="me va a buscar Juan este mes?"))
    c.tomar_siguiente(T0 + timedelta(seconds=16))
    c.cerrar("ana")
    c.procesar(ev("gift", "ana", 44, regalo="Rose", valor=5))
    assert c.pendientes(T0 + timedelta(seconds=45))[0].pregunta == "me va a buscar Juan este mes?"
    viejo = Cola(espera_fecha=None)
    viejo.procesar(ev("comment", "ana", 0, texto="me va a buscar Juan este mes?"))
    viejo.tomar_siguiente(T0 + timedelta(seconds=16))
    viejo.cerrar("ana")
    viejo.procesar(ev("gift", "ana", 400, regalo="Rose", valor=5))        # pasaron más de 5 minutos
    assert viejo.pendientes(T0 + timedelta(seconds=401))[0].pregunta == ""

def test_quien_regala_tiene_tres_minutos_para_escribir_su_pregunta():
    c = Cola(espera_fecha=None)
    c.procesar(ev("gift", "cami", 0, regalo="Hand Heart", valor=100))
    assert c.tomar_siguiente(T0 + timedelta(seconds=160)) is None
    c.procesar(ev("comment", "cami", 162, texto="Yudith 15 octubre 92. quiero saber si esa persona seguirá buscándome y porque?"))
    item = c.tomar_siguiente(T0 + timedelta(seconds=163))
    assert item.valor == 100 and "seguirá buscándome" in item.pregunta and item.dato.signo == "Libra"


# ---------- Lalita Vergara, log del 11 de octubre ----------
def test_problemas_tecnicos_y_gracias_con_emoji_no_son_pregunta():
    for t in ["Hola no te escucho", "😊muchas gracias no entendía jajaja", "no se escucha", "se fue el audio",
              "no hay sonido amiga"]:
        assert not es_pregunta(t), t
    assert es_pregunta("él no me escucha cuando le hablo, cambiará?")

def test_charla_no_ocupa_el_lugar_de_la_pregunta_de_quien_regalo():
    c = Cola(espera_fecha=None)
    c.procesar(ev("gift", "lali", 0, regalo="Heart Me", valor=1))
    c.procesar(ev("comment", "lali", 54, texto="Hola no te escucho"))
    c.procesar(ev("comment", "lali", 60, texto="listo ya te escucho bien"))                   # charla que sí se cuela
    [item] = c.pendientes(T0 + timedelta(seconds=61))
    assert item.pregunta == "listo ya te escucho bien"
    c.procesar(ev("comment", "lali", 70, texto="que va a suceder ahora con el papá de mis hijos?"))
    [item] = c.pendientes(T0 + timedelta(seconds=71))
    assert item.pregunta == "que va a suceder ahora con el papá de mis hijos?" and item.extras == []

def test_pregunta_que_llega_despues_del_mensaje_general_se_lee_con_el_regalo():
    c = Cola(espera_fecha=None)
    c.procesar(ev("gift", "lali", 0, regalo="Woodland Wonder", valor=30))
    general = c.tomar_siguiente(T0 + timedelta(seconds=180))               # no preguntó a tiempo
    assert general.pregunta == ""
    c.procesar(ev("comment", "lali", 200, texto="que va a suceder ahora con el papá de mis hijos? Miller Wilches"))
    c.cerrar("lali")
    [item] = c.pendientes(T0 + timedelta(seconds=225))
    assert item.valor == 30 and item.regalos == ["Woodland Wonder"] and "papá de mis hijos" in item.pregunta
    c.tomar_siguiente(T0 + timedelta(seconds=226))
    c.cerrar("lali")
    c.procesar(ev("comment", "lali", 240, texto="Miller Wilches está en malos pasos ?"))
    assert all(i.valor == 0 for i in c.pendientes(T0 + timedelta(seconds=260)))   # la deuda se paga una sola vez

def test_la_deuda_de_pregunta_vence_a_los_cinco_minutos():
    c = Cola(espera_fecha=None)
    c.procesar(ev("gift", "lali", 0, regalo="Rose", valor=5))
    c.tomar_siguiente(T0 + timedelta(seconds=180))
    c.cerrar("lali")
    c.procesar(ev("comment", "lali", 500, texto="me va a buscar este mes?"))
    assert all(i.valor == 0 for i in c.pendientes(T0 + timedelta(seconds=520)))


# ---------- live del 11 de octubre (hadaencantadatarot) ----------
def test_pregunta_que_empieza_con_arroba_no_es_una_mencion():
    c = Cola(espera_fecha=None)
    c.procesar(ev("gift", "maky", 0, regalo="Singing Mushroom", valor=99))
    c.procesar(ev("comment", "maky", 29, texto="@magaly Alcibar 29/4/85 y Saúl Peña cuáles son sus verdaderas intenciones ahora conmigo"))
    [item] = c.pendientes(T0 + timedelta(seconds=30))
    assert item.pregunta.startswith("magaly Alcibar") and item.dato.signo == "Tauro"
    assert c.sin_mencion("@que pasa con mi esposo 04/06/90@kreativa@gmail.com") == "que pasa con mi esposo 04/06/90"
    assert c.sin_mencion("@@hector sonora 19 feb 94. le llegara karma?") == "hector sonora 19 feb 94. le llegara karma?"

def test_mencion_a_otra_persona_del_chat_se_ignora():
    c = Cola(espera_fecha=None, espera_gratis=CERO)
    c.procesar({**ev("comment", "lali", 0, texto="hola a todos"), "nickname": "Lalita Vergara"})
    assert c.sin_mencion("@Lalita Vergara comoo así, si te ves re joven") is None
    c.procesar(ev("comment", "abc", 5, texto="@Lalita Vergara comoo así, si te ves re joven"))
    assert c.pendientes(T0 + timedelta(seconds=6)) == []

def test_charla_antes_del_regalo_no_se_vuelve_la_pregunta():
    for charla in ["De acuerdo totalmente", "La última 🙈🙈 ya bella jejeje", "yo FALTO", "Si acciones fue horrible el pasado",
                   "No yo tampoco quiero algo serio", "Si poner límites"]:
        c = Cola(espera_fecha=None)
        c.procesar(ev("comment", "m", 0, texto=charla))
        c.procesar(ev("gift", "m", 10, regalo="Confetti", valor=100))
        [item] = c.pendientes(T0 + timedelta(seconds=11))
        assert item.pregunta == "" and c.falta(item) == ["pregunta"], charla

def test_preguntas_sobre_el_live_no_gastan_la_gratis():
    for t in ["Mi pregunta te salío?", "La lista está muy larga?", "mi pregunta salio", "te envie la pregunta al interno",
              "Voy a enviarte otra pregunta y otra rosquilla", "¡Nuestra comunidad acaba de subir de r",
              "Bonito domingo bella ✨ gracias"]:
        assert not es_pregunta(t), t
    for t in ["mi pregunta es omar sequera 15 04 70 me es fiel", "Nancy Gómez Nuñez si me quiere 20 03 63",
              "si me llegara acercar a natalie qué sentimientos en ella actuarían?", "no me busca, volverá?"]:
        assert es_pregunta(t), t

def test_otra_fecha_despues_de_dar_la_suya_es_de_la_otra_persona():
    c = Cola()
    c.procesar(ev("comment", "alf", 0, texto="Alfredo Álvarez 13/06/91 y Miguel Villa 11/11/03 quiere volver conmigo por amor?"))
    c.procesar(ev("gift", "alf", 1, regalo="Singing Mushroom", valor=99))
    c.tomar_siguiente(T0 + timedelta(seconds=2))
    c.cerrar("alf")
    c.procesar(ev("gift", "alf", 100, regalo="Singing Mushroom", valor=99))
    c.procesar(ev("comment", "alf", 120, texto="Miguel Villa 11/11/03 El tiene una relación con Oscar Gil?"))
    [item] = c.pendientes(T0 + timedelta(seconds=121))
    assert item.dato.signo == "Géminis" and item.pareja.signo == "Escorpio" and c._datos["alf"].signo == "Géminis"


def test_casos_del_live_indiodeluz():
    from backend.cola import parece_pregunta
    for t in ["hay preguntitas gratuitas??", "son gratis las preguntas?", "cómo es lo de la pregunta gratuita"]:
        assert not es_pregunta(t), t
    assert parece_pregunta("Soy segundo 87 mi pareja deverdad me quiso y por q se terminó mi relación")
    assert parece_pregunta("mi pregunta gratis es si volverá Juan conmigo?")


def test_saludo_con_signo_de_pregunta_no_es_pregunta():      # Annai G, live del 12 de octubre
    for t in ["Hola lindo día, bien gracias y tú ?", "hola cómo estás?", "hola qué tal?"]:
        assert not es_pregunta(t), t
    assert es_pregunta("cómo está mi relación con Juan?") and es_pregunta("y tú crees que él vuelve?")
