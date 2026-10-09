from backend.filtro import evaluar

def test_emergencia_medica_menor():
    r = evaluar("Hola q le pasa a mi hija Scarleht Valdivieso por se desmalla y le late muy rapido su corazón")
    assert r.sensible and r.categoria == "salud" and r.mensaje

def test_embarazo():
    r = evaluar("Soy Verónica quedare embarazada pronto")
    assert r.categoria == "embarazo" and r.accion == "saltar"

def test_posible_menor():
    r = evaluar("Mi papa me obligará a terminar con mi novio o aceptará que este con el?")
    assert r.categoria == "menor"

def test_brujeria_terceros():
    r = evaluar("Effy Lance le hizo trabajo a Matías García y Shaiel Lance?")
    assert r.categoria == "brujeria"

def test_dinero_legal():
    r = evaluar("¿Llego a un acuerdo bueno con una excuñada por una herencia?")
    assert r.categoria == "dinero_legal"

def test_crisis_gana_sobre_otras():
    r = evaluar("no quiero vivir, estoy enferma")
    assert r.categoria == "crisis"

def test_preguntas_normales_pasan():
    for t in ["mi novio Jaciel me sigue queriendo?",
              "Como me irá en mi sustentacion de tesis",
              "soy aries leeme las cartas porfavor",
              "ahora si me llegaré a mudar?",
              "hola si saldré de esta crisis que estoy atravesando"]:
        assert not evaluar(t).sensible, t