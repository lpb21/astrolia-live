from backend.filtro import evaluar

def test_emergencia_medica_menor():
    r = evaluar("Hola q le pasa a mi hija Scarleht Valdivieso por se desmalla y le late muy rapido su corazón")
    assert r.sensible and r.categoria == "salud" and r.mensaje

def test_embarazo():
    r = evaluar("Soy Verónica quedare embarazada pronto")
    assert r.categoria == "embarazo" and r.accion == "mensaje_fijo"      # va por DM: no se lee en el live

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
        
def test_falsos_positivos_reportados():
    for t in ["soy cáncer, él volverá?", "sin embargo él me escribe", "tengo chance de volver",
              "mi novio es médico", "perdió el juicio por mí", "mi jefa es muy demandante"]:
        assert not evaluar(t).sensible, t

def test_casos_reales_siguen_bloqueados():
    assert evaluar("mi mamá tiene cáncer, se va a curar?").categoria == "salud"
    assert evaluar("me van a embargar la casa").categoria == "dinero_legal"
    assert evaluar("tengo un juicio laboral").categoria == "dinero_legal"

def test_cancer_como_signo_pasa():
    for t in ["soy cáncer, él volverá?", "soy de cáncer", "mi signo es Cáncer me va a buscar?",
              "él es cáncer y yo leo, nos irá bien?", "que siente jorge Sánchez (cáncer) por mi?",
              "mi ex es cáncer volverá?", "los cáncer son muy sensibles verdad?", "tengo luna en cáncer",
              "mi novio tiene el sol en cáncer", "tengo ascendente cancer", "con cáncer me llevo bien?",
              "tengo un novio cáncer", "soy cáncer, mi relación va a mejorar?",
              "él es cáncer, superará lo nuestro?"]:
        assert not evaluar(t).sensible, t

def test_cancer_como_enfermedad_se_bloquea():
    for t in ["mi mamá tiene cáncer, se va a curar?", "tengo cancer de higado", "me detectaron cáncer",
              "mi abuela murió de cáncer", "superaré el cáncer?", "mi esposo está luchando contra el cáncer",
              "el cancer de mi hermana va a sanar?", "me salió un cáncer en la piel", "soy paciente de cáncer",
              "vencerá mi mamá el cáncer?", "mi tía con cáncer mejorará?", "mi papa sufre de cancer",
              "se me va a quitar el cáncer?", "quimioterapia de mi mamá funcionará?",
              "lo que tiene mi mamá es cáncer, se curará?", "soy cáncer y mi mamá tiene cáncer"]:
        assert evaluar(t).categoria == "salud", t


def test_casos_de_los_logs_de_octubre():
    casos = {
        "Isabel maria quiero saber si tengo asma  o disnea o otra cosa": "salud",
        "por que me vine dolores en la espalda de la nada?": "salud",
        "mi salud cualquier regslo": "salud",
        "mi hija será mamá de una nena o varón?": "embarazo",
        "MI HIJO BRAYAN CORRE PELIGRO": "violencia",
        "me pasó algo me quitaron un dinero quiero saber quién fue": "acusacion",
        "unas mujeres estan regando rumores de mi familia, como saber quienes son": "acusacion",
        "Mauricio Dávila le irá bien en su tema legal?": "dinero_legal",
        "Paqui irá bien ir con mamá al notario el 15 octubre?": "dinero_legal",
    }
    for texto, categoria in casos.items():
        assert evaluar(texto).categoria == categoria, texto

def test_profesor_de_musica_no_es_menor():
    assert not evaluar("que siente jorge Sánchez (cáncer) por mi?. Es mi profesor de bajo (instrumento 🎸)").sensible
    for t in ["quien me ama de verdad?", "quiero saber quien es el amor de mi vida", "mi economía mejorará", "voy a poder salir de mis deudas", "me llegará un dinero que espero",
              "Pilar rivas me darán la paga de viuda Gracias", "cobrare el salario de mis hijas?",
              "es legalmente mi esposo, volverá?"]:
        assert not evaluar(t).sensible, t


def test_preocupacion_por_un_familiar_no_se_bloquea():      # Lalita Vergara
    for t in ["Hola soy Laura vergara, que va a suceder ahora con el papá de mis hijos? Miller Wilches",
              "Miller Wilches está en malos pasos ?"]:
        assert not evaluar(t).sensible, t
