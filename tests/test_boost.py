import asyncio
from datetime import datetime, timedelta, timezone
from backend.boost import Boost
from backend.cola import Cola
from backend.overlay import vista
from backend.worker import Worker
from tests.test_worker import GenFijo

T0 = datetime(2026, 10, 9, 1, 0, tzinfo=timezone.utc)
CERO = timedelta(0)


def t(seg):
    return T0 + timedelta(seconds=seg)

def ev(c, tipo, user, seg, **k):
    c.procesar({"tipo": tipo, "user": user, "nickname": user.capitalize(), "ts": t(seg).isoformat(), **k})

def correr(w, seg):
    return asyncio.run(w.paso(t(seg)))


def test_gana_quien_mas_likes_da_en_la_ronda():
    b = Boost(cada=None)
    b.like("antes", "Antes", 500, t(0))                 # sin ronda abierta no cuenta
    b.iniciar(t(10))
    b.like("ana", "Ana", 15, t(11))
    b.like("lu", "Lu", 15, t(12))
    b.like("ana", "Ana", 15, t(30))
    b.like("lu", "Lu", 40, t(71))                       # llegó tarde: la ronda dura 60 s
    assert b.vista(t(40)) == {"restante": 30, "top": [{"nickname": "Ana", "likes": 30}, {"nickname": "Lu", "likes": 15}]}
    assert b.activo(t(69)) and not b.toca_cerrar(t(69)) and b.toca_cerrar(t(70)) and b.vista(t(70)) is None
    g = b.cerrar(t(70))
    assert (g.user, g.likes) == ("ana", 30) and b.inicio is None

def test_empate_gana_quien_llego_primero_y_sin_likes_no_hay_ganador():
    b = Boost(cada=None)
    b.iniciar(t(0))
    b.like("lu", "Lu", 20, t(5))
    b.like("ana", "Ana", 20, t(3))
    assert b.cerrar(t(60)).user == "ana"
    b.iniciar(t(100))
    assert b.cerrar(t(160)) is None

def test_arranca_sola_cada_cierto_tiempo_o_a_pedido():
    b = Boost(cada=timedelta(minutes=10))
    assert not b.toca_iniciar(t(0)) and not b.toca_iniciar(t(599)) and b.toca_iniciar(t(600))
    b.iniciar(t(600))
    assert not b.toca_iniciar(t(601))                   # ya hay una en curso
    b.cerrar(t(660))
    assert not b.toca_iniciar(t(700)) and b.toca_iniciar(t(1260))
    manual = Boost(cada=None)
    assert not manual.toca_iniciar(t(9999))
    manual.pedido = True
    assert manual.toca_iniciar(t(0))


def test_el_pase_sube_de_primero_a_quien_ya_esta_en_la_fila():
    c = Cola(espera_fecha=None)
    ev(c, "comment", "rica", 0, texto="me va a buscar este mes?")
    ev(c, "gift", "rica", 1, regalo="Leon", valor=200)
    ev(c, "comment", "ana", 2, texto="le gusto a Pedro o no?")
    ev(c, "gift", "ana", 3, regalo="Rose", valor=1)
    assert [i.user for i in c.pendientes(t(4))] == ["rica", "ana"]
    assert c.dar_pase("ana", "Ana", t(5)) is True
    assert [i.user for i in c.pendientes(t(6))] == ["ana", "rica"]
    assert c.tomar_siguiente(t(6)).valor == 1           # conserva el nivel de su regalo

def test_el_pase_no_gasta_la_gratis_ni_espera_el_margen():
    c = Cola(espera_fecha=None)
    ev(c, "comment", "ana", 0, texto="me va a buscar este mes?")
    assert c.dar_pase("ana", "Ana", t(1)) is True
    item = c.tomar_siguiente(t(2))                      # sin esperar los 15 s de la gratis
    assert item.prioridad and item.valor == 0
    c.cerrar("ana")
    ev(c, "comment", "ana", 30, texto="y en el trabajo me irá bien?")
    assert c.tomar_siguiente(t(50)).user == "ana"       # su pregunta gratis seguía intacta

def test_pase_guardado_para_quien_aun_no_pregunta():
    c = Cola(espera_fecha=None)
    ev(c, "comment", "rica", 0, texto="me va a buscar este mes?")
    ev(c, "gift", "rica", 1, regalo="Leon", valor=200)
    assert c.dar_pase("ana", "Ana", t(2)) is False
    ev(c, "comment", "ana", 40, texto="le gusto a Pedro o no?")
    assert [i.user for i in c.pendientes(t(41))] == ["ana", "rica"]
    c2 = Cola(espera_fecha=None)
    c2.dar_pase("ana", "Ana", t(0))
    ev(c2, "comment", "rica", 1, texto="me va a buscar este mes?")
    ev(c2, "gift", "rica", 2, regalo="Leon", valor=200)
    ev(c2, "comment", "ana", 700, texto="le gusto a Pedro o no?")      # el pase venció a los 10 min
    assert not c2.pendientes(t(701))[0].prioridad


def test_el_worker_anuncia_la_ronda_y_le_da_el_turno_a_quien_gana():
    gen = GenFijo()
    c = Cola(espera_fecha=None)
    b = Boost(cada=None)
    w = Worker(c, gen, palabras_por_seg=0, boost=b)
    ev(c, "comment", "rica", 0, texto="me va a buscar este mes?")
    ev(c, "gift", "rica", 1, regalo="Leon", valor=200)
    ev(c, "comment", "ana", 2, texto="le gusto a Pedro o no?")
    b.pedido = True
    assert correr(w, 5)
    assert w.salidas[0].tipo == "boost" and "60 segundos" in w.salidas[0].texto and b.activo(t(6))
    assert vista(c, w, t(6))["boost"]["restante"] == 59
    b.like("ana", "Ana", 120, t(20))
    b.like("rica", "Rica", 80, t(25))
    ev(c, "comment", "pedro", 30, texto="me conviene cambiar de trabajo?")
    ev(c, "gift", "pedro", 31, regalo="Leon", valor=100)
    assert correr(w, 65)
    anuncio = next(s for s in w.salidas if s.tipo == "boost" and "ganó" in s.texto)
    assert "Ana ganó el boost con 120 tap tap" in anuncio.texto and "pasa de primera" in anuncio.texto
    correr(w, 66)
    assert [s.nickname for s in w.salidas if s.tipo == "lectura"] == ["Rica", "Ana", "Pedro"]   # Ana pasó sin regalar

def test_ganador_sin_pregunta_recibe_la_invitacion_y_el_pase_se_ve_en_el_overlay():
    c = Cola(espera_fecha=None)
    b = Boost(cada=None)
    w = Worker(c, GenFijo(), palabras_por_seg=0, boost=b)
    b.iniciar(t(0))
    b.like("ana", "Ana", 50, t(10))
    correr(w, 60)
    assert "Escribe tu pregunta" in w.salidas[-1].texto
    ev(c, "comment", "ana", 70, texto="le gusto a Pedro o no?")
    assert vista(c, w, t(71))["turnos"][0]["pase"] is True


def test_quien_ya_gano_queda_fuera_de_las_siguientes_rondas_y_de_la_lista():
    # chole30767 ganó tres rondas seguidas en el live del 13-oct-2026
    b = Boost(duracion=timedelta(seconds=60), cada=timedelta(minutes=5))
    b.iniciar(t(0))
    b.like("chole", "Chole", 150, t(10))
    b.like("lu", "Lu", 40, t(20))
    assert b.cerrar(t(61)).user == "chole"
    b.iniciar(t(400))
    b.like("chole", "Chole", 300, t(410))
    b.like("lu", "Lu", 20, t(420))
    assert b.vista(t(430))["top"] == [{"nickname": "Lu", "likes": 20}]
    assert b.cerrar(t(461)).user == "lu"
    b.iniciar(t(800))
    b.like("chole", "Chole", 99, t(810))
    assert b.cerrar(t(861)) is None                                    # solo tocaron quienes ya habían ganado
