from __future__ import annotations
import json, logging, os
import anthropic

log = logging.getLogger("generador")

MODELO = "claude-opus-5-5"
MAX_TOKENS = 4000      # incluye lo que el modelo razona; la lectura más larga ronda 300 tokens
ESPERA = 40.0          # segundos por intento: en vivo, más vale saltar el turno que dejar la voz en silencio

# El mismo JSON que pide el prompt, pero garantizado por la API (siempre válido y con estos campos)
FORMATO = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "sensible": {"type": "boolean"},
            "categoria": {"type": "string"},
            "respuesta": {"type": "string"},
        },
        "required": ["sensible", "categoria", "respuesta"],
        "additionalProperties": False,
    },
}


class GeneradorClaude:
    """Lecturas con Claude. Toma la clave de ANTHROPIC_API_KEY (archivo .env)."""

    def __init__(self, cliente: anthropic.AsyncAnthropic | None = None, modelo: str | None = None):
        self.cliente = cliente or anthropic.AsyncAnthropic(timeout=ESPERA, max_retries=1)
        self.modelo = modelo or os.getenv("ANTHROPIC_MODEL") or MODELO

    async def generar(self, prompt: dict) -> dict:
        r = await self.cliente.beta.messages.create(
            model=self.modelo,
            max_tokens=MAX_TOKENS,
            system=prompt["system"],
            messages=prompt["messages"],
            output_config={"effort": "low", "format": FORMATO},   # lecturas cortas y en vivo: prima la rapidez
            # Si el modelo declina por sus filtros de seguridad, la API reintenta sola con otro modelo
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        u = r.usage
        log.info(f"[CLAUDE] {r.model} {r.stop_reason} entrada={u.input_tokens} salida={u.output_tokens} id={r._request_id}")
        if r.stop_reason == "refusal":           # declinó toda la cadena: se trata como tema que no se lee
            return {"sensible": True, "categoria": "modelo", "respuesta": ""}
        if r.stop_reason == "max_tokens":
            raise RuntimeError("la respuesta se cortó por max_tokens")
        datos = json.loads(next(b.text for b in r.content if b.type == "text"))
        if not datos["sensible"] and not datos["respuesta"].strip():
            raise RuntimeError("el modelo devolvió una lectura vacía")
        return datos
