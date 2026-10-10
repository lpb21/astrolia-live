import asyncio
from datetime import datetime, timedelta, timezone
from backend.cola import Cola
from backend.worker import Worker

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

def test_embarazo_se_salta_sin_llamar_al_modelo():
    gen = GenFijo()
    c, w = preparar("quedaré embarazada pronto", gen)
    correr(w)
    assert gen.prompts == [] and w.salidas == [] and c.historial[-1].estado == "saltado"

def test_salud_mensaje_fijo_sin_modelo():
    gen = GenFijo()
    c, w = preparar("mi hija se desmaya", gen)
    correr(w)
    assert gen.prompts == [] and w.salidas[-1].tipo == "mensaje_fijo"

def test_segundo_filtro_del_modelo():
    gen = GenFijo({"sensible": True, "categoria": "salud", "respuesta": ""})
    c, w = preparar("me irá bien con mi tratamiento?", gen)
    correr(w)
    assert w.salidas == [] and w.saltados[-1]["categoria"] == "salud"

def test_error_del_generador_no_tumba_el_worker():
    c, w = preparar("me buscará este mes?", GenFijo(error=RuntimeError("timeout")))
    assert correr(w)
    assert w.saltados[-1]["categoria"] == "error" and w.actual is None

def test_pausa_no_toma_items():
    c, w = preparar("me buscará este mes?")
    w.pausado = True
    assert not correr(w)
    assert len(c.pendientes(T0 + timedelta(seconds=2))) == 1

def test_lectura_general_llega_al_prompt():
    gen = GenFijo()
    c, w = preparar("", gen)
    correr(w, 125)
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
    assert not correr(w)
    assert gen.prompts == [] and w.salidas == []
    assert c.historial[-1].estado == "saltado" and w.saltados[-1]["categoria"] == "menor"
    assert c.pendientes(T0 + timedelta(seconds=2)) == []

def test_menor_que_da_la_fecha_despues_tambien_se_descarta():
    gen = GenFijo()
    c, w = preparar("me va a hablar Juan esta semana?", gen, ESPERA)
    correr(w)                                   # se le pide la fecha
    comentar(c, "15/03/2010", 20)
    assert not correr(w, 21)
    assert gen.prompts == [] and w.saltados[-1]["categoria"] == "menor"

def test_fecha_de_la_pareja_menor_no_descarta_a_quien_pregunta():
    gen = GenFijo()
    c, w = preparar("soy Ana 05/05/90 mi hijo 15/03/2010 pasará el año?", gen, ESPERA)
    correr(w)
    assert all(s["categoria"] != "menor" or s["motivo"] != "fecha de nacimiento" for s in w.saltados)
