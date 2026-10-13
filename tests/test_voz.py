import asyncio
from datetime import timedelta
from backend.cola import Cola
from backend.overlay import vista
from backend.voz import para_decir, trocear
from backend.worker import Worker
from tests.test_worker import GenFijo, T0, comentar, correr

LARGA = ("Dani, gracias por esa rosa, qué lindo detalle. Me preguntas si él vuelve, y lo primero que aparece "
         "en tu pasado es el Seis de Copas: ahí hubo ternura de verdad. Hoy, en el presente, el Dos de Espadas "
         "me muestra a dos personas que prefieren no mirar lo que pasó. Y hacia el futuro llega La Estrella.")


class VozFalsa:
    def __init__(self, falla_en=None):
        self.pedidos, self.falla_en = [], falla_en

    async def sintetizar(self, texto):
        self.pedidos.append(texto)
        if self.falla_en is not None and len(self.pedidos) > self.falla_en:
            raise RuntimeError("sin voz")
        return b"RIFF" + texto.encode()[:8], len(texto.split()) / 2.5


def lectura(voz, texto=LARGA):
    gen = GenFijo({"sensible": False, "categoria": "", "respuesta": texto})
    c = Cola(espera_fecha=None)
    w = Worker(c, gen, palabras_por_seg=0, voz=voz)
    comentar(c, "me va a buscar Juan este mes?", 0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 5, "ts": T0.isoformat()})
    correr(w)
    return c, w


def test_trocear_por_frases():
    t = trocear(LARGA)
    assert len(t) == 4 and " ".join(t) == LARGA and all(len(x.split()) <= 26 for x in t)
    larga = "Uno dos tres cuatro cinco seis siete ocho nueve diez, " * 4 + "y fin."
    assert len(trocear(larga)) >= 2 and " ".join(trocear(larga)) == larga      # se corta en las comas
    assert trocear("Hola.") == ["Hola."] and trocear("sin punto final") == ["sin punto final"] and trocear("") == []

def test_para_decir_quita_lo_que_la_voz_no_debe_leer():
    assert para_decir("𝙹𝚞𝚍𝚒𝚝𝚑 𝙼𝚞ñ𝚊𝚗𝚝𝚎, ya casi es tu turno 🌙✨") == "Judith Muñante, ya casi es tu turno"
    assert para_decir("✨✨👑**Ingobernable**👑✨✨: ¿me escuchas?") == "Ingobernable : ¿me escuchas?"
    assert para_decir("JoseCorreavi91@ y A_L_E") == "JoseCorreavi91 y A L E"

def test_la_lectura_sale_en_trozos_con_su_audio():
    voz = VozFalsa()
    c, w = lectura(voz)
    s = w.salidas[-1]
    assert s.tipo == "lectura" and s.completo and [t["texto"] for t in s.trozos] == trocear(LARGA)
    assert voz.pedidos[0].startswith("Barajando para U")            # anuncia el turno mientras la IA escribe
    assert voz.pedidos[1:] == trocear(LARGA) and all(t["audio"] in w.audios and t["dur"] > 0 for t in s.trozos)
    assert [x.tipo for x in w.salidas] == ["barajando", "lectura"]
    w.hablando = s
    h = vista(c, w, T0 + timedelta(seconds=2))["hablando"]
    assert h["completo"] and h["trozos"][0] == {"texto": trocear(LARGA)[0], "audio": f"audio/{s.trozos[0]['audio']}.wav",
                                                "dur": s.trozos[0]["dur"]}

def test_los_avisos_tambien_suenan():
    voz = VozFalsa()
    c = Cola()
    w = Worker(c, GenFijo(), palabras_por_seg=0, voz=voz)
    comentar(c, "me va a buscar Juan este mes?", 0)
    c.procesar({"tipo": "gift", "user": "u", "nickname": "U", "regalo": "Rose", "valor": 5, "ts": T0.isoformat()})
    correr(w)
    assert w.salidas[-1].tipo == "pide_fecha" and w.salidas[-1].trozos and voz.pedidos

def test_si_la_voz_falla_al_empezar_se_sigue_sin_audio():
    c, w = lectura(VozFalsa(falla_en=0))
    s = w.salidas[-1]
    assert [x.tipo for x in w.salidas] == ["barajando", "lectura"]
    assert s.tipo == "lectura" and s.trozos == [] and c.historial[-1].estado == "hecho"

def test_si_falla_a_la_mitad_queda_lo_que_alcanzo_a_sonar():
    c, w = lectura(VozFalsa(falla_en=3))              # el anuncio del turno y dos trozos de la lectura
    s = w.salidas[-1]
    assert len(s.trozos) == 2 and s.completo and c.historial[-1].estado == "hecho"     # completo: ya no vienen más

def test_sin_voz_no_hay_trozos():
    c, w = lectura(None)
    assert w.salidas[-1].trozos == [] and w.audios == {}

def test_la_app_entrega_el_audio():
    from fastapi.testclient import TestClient
    from backend import app as m
    cliente = TestClient(m.app)
    m.worker.audios["a999"] = b"RIFFdatos"
    r = cliente.get("/overlay/audio/a999.wav")
    assert r.status_code == 200 and r.content == b"RIFFdatos" and r.headers["content-type"] == "audio/wav"
    assert cliente.get("/overlay/audio/no-existe.wav").status_code == 404
    del m.worker.audios["a999"]


def _wav(muestras, hz=22050):
    import io, wave, array
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(hz)
        w.writeframes(array.array("h", muestras).tobytes())
    return b.getvalue()

def test_recortar_silencio_deja_solo_un_respiro():
    from backend.voz import recortar_silencio, AIRE_ANTES, AIRE_DESPUES
    hz = 22050
    voz = [8000, -8000] * (hz // 2)                                  # 1 s de sonido
    datos, dur = recortar_silencio(_wav([0] * hz + voz + [0] * (2 * hz)))    # 1 s de silencio antes y 2 s después
    assert 1.0 <= dur <= 1.0 + AIRE_ANTES + AIRE_DESPUES + 0.02
    assert datos[:4] == b"RIFF"
    solo_silencio, d = recortar_silencio(_wav([0] * hz))
    assert d == 1.0                                                  # sin sonido no se toca

def test_frase_larga_no_se_corta_en_las_comas_salvo_que_sea_enorme():
    normal = "Me preguntas si él vuelve, y lo primero que aparece en tu pasado, que fue hermoso, es el Seis de Copas, donde hubo ternura real."
    assert trocear(normal) == [normal]
    enorme = "uno dos tres cuatro cinco seis siete ocho nueve diez, " * 5 + "y fin."
    assert len(trocear(enorme)) >= 2

def test_un_saludo_corto_se_une_a_la_frase_siguiente():
    t = trocear("Hola, Ana. Me preguntas si él vuelve, y lo primero que aparece en tu pasado es el Seis de Copas, con ternura.")
    assert len(t) == 1

def test_la_voz_adelanta_trozos_para_no_dejar_silencios():
    class VozLenta(VozFalsa):
        ritmo = 0.9                                                  # casi tan lenta como el audio
    voz = VozLenta()
    c, w = lectura(voz)
    assert w.salidas[-1].completo and len(voz.pedidos) == 1 + len(trocear(LARGA))


def test_nombre_decible():
    from backend.voz import nombre_decible
    assert nombre_decible("🪐♥️Yuli Triana💫🍃") == "Yuli Triana"
    assert nombre_decible("𝓐𝓷𝓭𝓻𝓮𝓲𝓽𝓪🦋") == "Andreita"
    assert nombre_decible("🖤") == "corazón" and nombre_decible("✨✨ 123 ✨") == "corazón"
    assert nombre_decible("🖤", "") == "" and nombre_decible("U") == "U"
