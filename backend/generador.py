from __future__ import annotations
import json, logging, os
import anthropic

log = logging.getLogger("generador")

# Por nivel: lo barato con el modelo rápido; desde UMBRAL monedas, el que mejor escribe
MODELO = "claude-sonnet-5-5"
MODELO_RAPIDO = "claude-haiku-5-5"
UMBRAL = 10            # monedas desde las que se usa MODELO ("Tres tiempos con consejo")
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


class LimiteGasto(RuntimeError):
    """Se alcanzó el límite de gasto de la API: reintentar no sirve hasta subirlo o hasta el mes siguiente."""


def _es_limite_gasto(exc: anthropic.APIStatusError) -> bool:
    texto = str(exc).lower()
    return "usage limits" in texto or "enforced_spend_limit_reached" in texto


class GeneradorClaude:
    """Lecturas con Claude. Toma la clave de ANTHROPIC_API_KEY (archivo .env)."""

    def __init__(self, cliente: anthropic.AsyncAnthropic | None = None, modelo: str | None = None,
                 modelo_rapido: str | None = None):
        self.cliente = cliente or anthropic.AsyncAnthropic(timeout=ESPERA, max_retries=1)
        self.modelo = modelo or os.getenv("ANTHROPIC_MODEL") or MODELO
        self.modelo_rapido = modelo_rapido or os.getenv("ANTHROPIC_MODEL_RAPIDO") or MODELO_RAPIDO

    def modelo_para(self, valor: int) -> str:
        return self.modelo if valor >= UMBRAL else self.modelo_rapido

    async def generar(self, prompt: dict) -> dict:
        try:
            r = await self._pedir(prompt)
        except (anthropic.BadRequestError, anthropic.RateLimitError) as exc:
            if _es_limite_gasto(exc):
                raise LimiteGasto(str(exc)) from exc
            raise
        return self._leer(r)

    async def _pedir(self, prompt: dict):
        return await self.cliente.beta.messages.create(
            model=self.modelo_para(prompt.get("valor", UMBRAL)),
            max_tokens=MAX_TOKENS,
            system=prompt["system"],
            messages=prompt["messages"],
            output_config={"effort": "low", "format": FORMATO},   # lecturas cortas y en vivo: prima la rapidez
            # Si el modelo declina por sus filtros de seguridad, la API reintenta sola con otro modelo
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",         # en Haiku no hay respaldo: un rechazo queda como rechazo
        )

    def _leer(self, r) -> dict:
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
