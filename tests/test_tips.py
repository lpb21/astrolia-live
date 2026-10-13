import asyncio, json
from datetime import timedelta
from types import SimpleNamespace as NS
import anthropic
from backend import frases
from backend.cola import Cola
from backend.tips import FORMATO, TipsClaude
from backend.worker import Worker
from tests.test_worker import GenFijo, T0

BUENO = "Antes de preguntar por alguien más, respira y pregúntate qué necesitas tú hoy. Esa suele ser la pregunta que de verdad importa."
OTRO = "La Estrella nos recuerda que después de una etapa dura vuelve la calma. Si la ves en tu lectura, es hora de confiar otra vez."


class ClienteFalso:
    def __init__(self, tips=(), stop="end_turn", error=None):
        self.pedidos, self.tips, self.stop, self.error = [], list(tips), stop, error
        self.messages = NS(create=self._create)

    async def _create(self, **kw):
        self.pedidos.append(kw)
        if self.error:
            raise self.error
        return NS(stop_reason=self.stop, content=[NS(type="text", text=json.dumps({"tips": self.tips}))])


def tanda(cliente, ya=()):
    return asyncio.run(TipsClaude(cliente).tanda("Luna en Libra", ["La Estrella: esperanza"], list(ya), ["ejemplo de tono"]))


def test_pide_una_tanda_y_arma_la_peticion():
    c = ClienteFalso([BUENO, OTRO])
    assert tanda(c, ya=["uno ya dicho"]) == [BUENO, OTRO]
    [p] = c.pedidos
    assert p["model"] == "claude-haiku-5-5" and p["output_config"] == {"effort": "low", "format": FORMATO}
    contenido = p["messages"][0]["content"]
    assert "Luna en Libra" in contenido and "La Estrella: esperanza" in contenido and "- uno ya dicho" in contenido
    assert "ejemplo de tono" in p["system"] and "No repitas" in p["system"]

def test_descarta_los_que_no_sirven():
    malos = ["muy corto", "palabra " * 60, "Si te duele la cabeza toma esta pastilla y verás que mañana amaneces mejor sin ir al hospital ni al médico.", 7]
    assert tanda(ClienteFalso(malos + [BUENO])) == [BUENO]

def test_si_la_ia_falla_no_hay_tips_nuevos():
    assert tanda(ClienteFalso(error=anthropic.APIConnectionError(message="sin red", request=None))) == []
    assert tanda(ClienteFalso([BUENO], stop="refusal")) == []


class TipsFalsos:
    def __init__(self, tandas):
        self.tandas, self.pedidos = list(tandas), []

    async def tanda(self, cielo, cartas, ya_dichos, ejemplos, n=8):
        self.pedidos.append({"cielo": cielo, "cartas": cartas, "ya_dichos": list(ya_dichos)})
        return self.tandas.pop(0) if self.tandas else []


def test_el_relleno_usa_los_tips_de_la_ia_y_pide_mas_cuando_quedan_pocos():
    tips = TipsFalsos([["tip uno de la ia", "tip dos de la ia", "tip tres de la ia"], ["tip cuatro de la ia"]])
    w = Worker(Cola(), GenFijo(), palabras_por_seg=0, relleno=timedelta(seconds=3), tips=tips)

    async def escena():
        dichos = []
        for seg in range(0, 31, 3):
            await w.paso(T0 + timedelta(seconds=seg))
            await asyncio.sleep(0)                              # deja correr la tanda en segundo plano
            await asyncio.sleep(0)
        return [s.texto for s in w.salidas if s.tipo == "relleno"]
    dichos = asyncio.run(escena())
    assert dichos[0] in frases.TIPS                            # el primero sale de los fijos mientras llega la tanda
    assert [d for d in dichos if "de la ia" in d] == ["tip uno de la ia", "tip dos de la ia", "tip tres de la ia", "tip cuatro de la ia"]
    assert "Luna" in tips.pedidos[0]["cielo"] and len(tips.pedidos[0]["cartas"]) == 6
    assert "tip uno de la ia" in tips.pedidos[1]["ya_dichos"]   # le recuerda lo ya dicho para que no repita
    assert dichos[-1] in frases.TIPS                            # sin más tandas, vuelve a los fijos

def test_sin_ia_de_tips_salen_los_fijos():
    w = Worker(Cola(), GenFijo(), palabras_por_seg=0, relleno=timedelta(seconds=3))
    asyncio.run(w.paso(T0)); asyncio.run(w.paso(T0 + timedelta(seconds=3)))
    assert w.salidas[-1].texto in frases.TIPS
