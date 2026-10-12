import asyncio, json
from types import SimpleNamespace as NS
import pytest
from backend.generador import FORMATO, GeneradorClaude

PROMPT = {"system": "sistema", "messages": [{"role": "user", "content": "<tirada>…</tirada>"}]}


class ClienteFalso:
    """Imita client.beta.messages.create y guarda lo que se le pidió."""
    def __init__(self, texto="", stop="end_turn"):
        self.pedidos = []
        self.beta = NS(messages=NS(create=self._create))
        self._r = NS(model="claude-opus-5-5", stop_reason=stop, _request_id="req_1",
                     usage=NS(input_tokens=10, output_tokens=5),
                     content=[NS(type="thinking", thinking=""), NS(type="text", text=texto)])

    async def _create(self, **kw):
        self.pedidos.append(kw)
        return self._r


def generar(cliente):
    return asyncio.run(GeneradorClaude(cliente).generar(PROMPT))


def test_devuelve_el_json_de_la_lectura():
    c = ClienteFalso(json.dumps({"sensible": False, "categoria": "", "respuesta": "Tu carta es El Sol."}))
    assert generar(c) == {"sensible": False, "categoria": "", "respuesta": "Tu carta es El Sol."}
    [p] = c.pedidos
    assert p["model"] == "claude-sonnet-5-5" and p["system"] == "sistema" and p["messages"] == PROMPT["messages"]
    assert p["output_config"] == {"effort": "low", "format": FORMATO}
    assert p["fallbacks"] == "default" and p["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in p and "temperature" not in p        # este modelo los rechaza

def test_segundo_filtro_pasa_tal_cual():
    c = ClienteFalso(json.dumps({"sensible": True, "categoria": "salud", "respuesta": ""}))
    assert generar(c)["categoria"] == "salud"

def test_rechazo_del_modelo_es_tema_que_no_se_lee():
    assert generar(ClienteFalso(stop="refusal")) == {"sensible": True, "categoria": "modelo", "respuesta": ""}

def test_respuesta_cortada_o_vacia_es_error():
    with pytest.raises(RuntimeError):
        generar(ClienteFalso('{"sensible": false, "categ', stop="max_tokens"))
    with pytest.raises(RuntimeError):
        generar(ClienteFalso(json.dumps({"sensible": False, "categoria": "", "respuesta": "  "})))

def test_modelo_por_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    assert GeneradorClaude(ClienteFalso()).modelo == "claude-sonnet-5-5"
    
def test_modelo_segun_valor():
    c = ClienteFalso(json.dumps({"sensible": False, "categoria": "", "respuesta": "ok"}))
    g = GeneradorClaude(c)
    for valor in (0, 1, 9, 10, 500):
        asyncio.run(g.generar({**PROMPT, "valor": valor}))
    assert [p["model"] for p in c.pedidos] == ["claude-haiku-5-5"] * 3 + ["claude-sonnet-5-5"] * 2

def test_limite_de_gasto_se_reconoce():
    import anthropic, httpx
    from backend.generador import LimiteGasto
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    exc = anthropic.BadRequestError("You have reached your specified API usage limits.",
                                    response=httpx.Response(400, request=req), body=None)
    async def create(**kw):
        raise exc
    c = NS(beta=NS(messages=NS(create=create)))
    with pytest.raises(LimiteGasto):
        asyncio.run(GeneradorClaude(c).generar(PROMPT))
