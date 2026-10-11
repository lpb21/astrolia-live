import random
from collections import Counter
from datetime import datetime, timezone
from astro.cielo import cielo
from backend.cola import Item
from backend.prompt import armar_prompt, palabras_para
from tarot.mazo import MAZO
from tarot.tirada import NIVELES, nivel_para, posiciones_para, tirar

TS = datetime(2026, 10, 9, 1, 0, tzinfo=timezone.utc)


def test_mazo_completo():
    assert len(MAZO) == 78 and len({c.id for c in MAZO}) == 78 and len({c.nombre for c in MAZO}) == 78
    assert Counter(c.arcano for c in MAZO) == {"mayor": 22, "menor": 56}
    assert Counter(c.palo for c in MAZO if c.palo) == {"bastos": 14, "copas": 14, "espadas": 14, "oros": 14}
    assert all(c.claves for c in MAZO)
    assert {"la-torre", "sota-espadas", "la-rueda-de-la-fortuna", "as-oros"} <= {c.id for c in MAZO}

def test_posiciones_segun_valor():
    assert posiciones_para(0) == ("respuesta",)
    assert posiciones_para(1) == posiciones_para(4) == ("mensaje",)
    assert posiciones_para(5) == posiciones_para(9) == ("pasado", "presente", "futuro")
    assert posiciones_para(10) == posiciones_para(49) == ("pasado", "presente", "futuro", "consejo")
    assert posiciones_para(50) == posiciones_para(99) == ("pasado", "presente", "futuro", "obstáculo", "consejo")
    assert posiciones_para(100)[-1] == "consejo" and len(posiciones_para(100)) == 6
    assert posiciones_para(5000) == posiciones_para(100)

def test_niveles():
    nombres = [nivel_para(v).nombre for v in (0, 4, 5, 10, 20, 31, 98, 100, 200)]
    assert nombres == ["Sí o no", "Mensaje del oráculo", "Tres tiempos", "Tres tiempos con consejo",
                       "Lectura con ritual", "Lectura doble", "Lectura profunda", "Lectura completa",
                       "Lectura maestra"]
    assert nivel_para(31) != nivel_para(98)                       # ya no reciben lo mismo
    assert [n.minimo for n in NIVELES] == sorted((n.minimo for n in NIVELES), reverse=True)
    assert [n.minimo for n in NIVELES if n.en_menu] == [200, 100, 30, 10, 5, 1, 0]
    assert not nivel_para(29).segunda_pregunta and nivel_para(30).segunda_pregunta

def test_tirada_sin_cartas_repetidas():
    rng = random.Random(7)
    for _ in range(500):
        t = tirar(100, rng)
        assert len({x.carta.id for x in t}) == 6
        assert [x.posicion for x in t] == list(posiciones_para(100))

def test_tirada_reproducible_con_semilla_y_distinta_sin_ella():
    assert tirar(30, random.Random(1)) == tirar(30, random.Random(1))
    assert len({tuple(x.carta.id for x in tirar(30)) for _ in range(20)}) > 1

def test_todas_las_cartas_pueden_salir():
    rng = random.Random(3)
    assert len({x.carta.id for _ in range(600) for x in tirar(100, rng)}) == 78

def test_prompt_lleva_la_tirada_y_el_largo_crece():
    it = Item("u", "Ana", "me va a buscar?", 30, ["Doughnut"], TS)
    it.cartas = tirar(30, random.Random(2))
    p = armar_prompt(it, cielo(TS), None)
    c = p["messages"][0]["content"]
    assert c.index("<tirada>") < c.index("<contexto_astrologico>")
    for t in it.cartas:
        assert f"{t.posicion.capitalize()}: {t.carta.nombre}" in c
    assert "entre 115 y 135 palabras" in c and "Entre 115 y 135 palabras" in p["system"]
    assert palabras_para(1) == (40, 60) and palabras_para(6)[0] > palabras_para(3)[1]
