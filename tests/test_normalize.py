from ingest.normalize import limpiar

def test_limpiar_casos_reales():
    assert limpiar("hoooola me ama?????") == "hola me ama?"
    assert limpiar("0000000000debería esperar q Leonel") == "debería esperar q Leonel"
    assert limpiar("me volvera a hablar?[thanks]👻") == "me volvera a hablar?👻"
    assert limpiar("𝑒𝑛 𝑔𝑒𝑛𝑒𝑟𝑎𝑙") == "en general"
    assert limpiar("llevo mucho tiempo esperando, jajaja") == "llevo mucho tiempo esperando, jajaja"