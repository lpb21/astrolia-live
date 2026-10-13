from datetime import timedelta
from fastapi.testclient import TestClient
from backend.cola import Cola
from backend.overlay import vista
from backend.worker import Worker
from tests.test_worker import GenFijo, T0, correr, preparar

AHORA = T0 + timedelta(seconds=2)


def test_vista_en_espera_trae_menu_y_turnos():
    c, w = preparar("", espera_fecha=timedelta(seconds=90))
    v = vista(c, w, AHORA)
    assert v["actual"] is None and v["hablando"] is None and v["en_cola"] == 1
    assert v["turnos"] == [{"nickname": "U", "nivel": "Mensaje del oráculo", "falta": ["pregunta"], "restante": 178, "signo": "", "pase": False}]
    assert v["boost"] is None
    assert [n["monedas"] for n in v["menu"]] == [0, 1, 5, 10, 30, 99, 199]
    assert [n["regalo"] for n in v["menu"]] == ["", "🌹 Rosa", "🫰 Corazón de dedos", "🌹 10 Rosas", "🍩 Rosquilla", "🎉 Confeti", "🙌 Manos bailando"]

def test_lectura_lleva_cartas_y_pregunta_sin_fecha(tmp_path):
    c, w = preparar("soy Ana 05/05/90 me va a buscar Juan?")
    correr(w)
    w.hablando = w.salidas[-1]
    (tmp_path / f"{w.hablando.cartas[0].carta.id}.png").write_bytes(b"x")
    h = vista(c, w, AHORA, tmp_path)["hablando"]
    assert h["tipo"] == "lectura" and h["nivel"] == "Mensaje del oráculo" and h["texto"] == "lectura de prueba"
    assert h["pregunta"] == "soy Ana me va a buscar Juan?" and h["signo"] == "Tauro"
    [carta] = h["cartas"]
    assert carta["posicion"] == "mensaje" and carta["imagen"] == f"cartas/{carta['id']}.png"

def test_carta_sin_archivo_no_tiene_imagen(tmp_path):
    c, w = preparar("mi novio me sigue queriendo?")
    correr(w)
    w.hablando = w.salidas[-1]
    assert vista(c, w, AHORA, tmp_path)["hablando"]["cartas"][0]["imagen"] is None

def test_mensaje_fijo_no_muestra_la_pregunta():
    c, w = preparar("mi hija se desmaya")
    correr(w)
    w.hablando = w.salidas[-1]
    h = vista(c, w, AHORA)["hablando"]
    assert h["tipo"] == "mensaje_fijo" and h["pregunta"] == "" and h["cartas"] == [] and h["texto"]

def test_no_salen_usuarios_ni_fechas():
    c, w = preparar("soy Ana 05/05/90 me va a buscar Juan?")
    correr(w)
    w.hablando = w.salidas[-1]
    c.procesar({"tipo": "gift", "user": "id_privado", "nickname": "Lu", "regalo": "Rose", "valor": 5, "ts": T0.isoformat()})
    v = vista(c, w, AHORA)
    assert v["turnos"][0]["signo"] == "" and v["hablando"]["signo"] == "Tauro"
    c.procesar({"tipo": "comment", "user": "id_privado", "nickname": "Lu", "texto": "10/08/1992", "ts": T0.isoformat()})
    assert vista(c, w, AHORA)["turnos"][0]["signo"] == "Leo"          # el signo sí, la fecha no
    texto = str(vista(c, w, AHORA))
    assert "id_privado" not in texto and "05/05" not in texto and "1990" not in texto and "1992" not in texto

def test_hablando_dura_lo_que_tarda_en_decirse():
    import asyncio
    c = Cola(espera_fecha=None)
    w = Worker(c, GenFijo(), palabras_por_seg=100)
    c.procesar({"tipo": "comment", "user": "u", "nickname": "U", "texto": "me va a buscar este mes?", "ts": T0.isoformat()})
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 1, "ts": T0.isoformat()})

    async def escena():
        tarea = asyncio.create_task(w.paso(AHORA))
        await asyncio.sleep(0.01)
        durante = (w.actual, w.hablando)
        await tarea
        return durante
    actual, hablando = asyncio.run(escena())
    assert actual.user == "u" and hablando.tipo == "lectura" and w.hablando is None and w.actual is None

def test_la_app_sirve_el_overlay():
    from backend.app import app
    cliente = TestClient(app)
    assert cliente.get("/overlay/estado").json()["hablando"] is None
    assert "overlay.js" in cliente.get("/overlay/").text


def test_la_carta_sale_de_img_live_y_si_falta_de_la_original(tmp_path):
    from backend.overlay import _imagen
    live, original = tmp_path / "img_live", tmp_path / "img"
    live.mkdir(); original.mkdir()
    (live / "la-luna.webp").write_bytes(b"x")
    (original / "la-luna.jpg").write_bytes(b"x")
    (original / "el-sol.jpg").write_bytes(b"x")
    carpetas = (("cartas", live), ("cartas-originales", original))
    assert _imagen("la-luna", carpetas) == "cartas/la-luna.webp"              # la preparada para el live
    assert _imagen("el-sol", carpetas) == "cartas-originales/el-sol.jpg"      # aún sin preparar: la original
    assert _imagen("la-torre", carpetas) is None                             # sin imagen: carta dibujada

def test_la_app_sirve_las_cartas_preparadas():
    from pathlib import Path
    import pytest
    from fastapi.testclient import TestClient
    from backend.app import app
    if not (Path(__file__).resolve().parent.parent / "tarot" / "img_live" / "la-luna.webp").is_file():
        pytest.skip("sin cartas preparadas; corre python -m tools.preparar_cartas")
    r = TestClient(app).get("/overlay/cartas/la-luna.webp")
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"


# ---------- animaciones de regalo del avatar ----------
def test_la_rosa_y_la_rosquilla_tienen_animacion_y_caducan():
    from backend.overlay import Efectos
    e = Efectos()
    e.regalo("Rose", AHORA)
    e.regalo("Finger Heart", AHORA)                       # sin animación propia
    e.regalo(" doughnut ", AHORA + timedelta(seconds=5))
    assert e.recientes(AHORA + timedelta(seconds=6)) == [{"id": 1, "clip": "rosa"}, {"id": 2, "clip": "rosquilla"}]
    assert e.recientes(AHORA + timedelta(seconds=14)) == [{"id": 2, "clip": "rosquilla"}]      # la rosa ya pasó
    assert e.recientes(AHORA + timedelta(seconds=60)) == []
