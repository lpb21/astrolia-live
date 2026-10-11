from datetime import datetime, timedelta, timezone
from backend.cola import Cola, es_pregunta

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
    assert c.tomar_siguiente(T0 + timedelta(seconds=59)) is None      # se le dan 60 s para preguntar
    assert c.tomar_siguiente(T0 + timedelta(seconds=60)) is item

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
    assert c.tomar_siguiente(T0 + timedelta(seconds=61)).user == "rico"

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
