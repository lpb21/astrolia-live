"""Tips para los ratos sin preguntas, escritos por la IA sobre la marcha. Se piden por tandas (una
llamada trae varios) para que siempre haya alguno listo y la voz no espere."""
from __future__ import annotations
import json, logging, os
import anthropic
from backend.filtro import evaluar

log = logging.getLogger("tips")

MODELO = "claude-haiku-5-5"      # textos cortos y de mucho volumen: el modelo rápido y barato
ESPERA = 25.0
POR_TANDA = 8
MIN_PALABRAS, MAX_PALABRAS = 10, 45

FORMATO = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {"tips": {"type": "array", "items": {"type": "string"}}},
        "required": ["tips"],
        "additionalProperties": False,
    },
}

SISTEMA = """Eres la voz de Astrolia, tarotista y astróloga, en un live de TikTok. En los ratos en que nadie pregunta, llenas el silencio con comentarios breves para quienes están conectados.

Escribe {n} comentarios distintos entre sí. Cada uno:
- Tiene entre 18 y 35 palabras y se entiende solo, sin depender de los otros.
- Se va a decir en voz alta: español latino, cálido, de tú o hablándole al grupo; sin listas, emojis, comillas ni símbolos.
- No empieza igual que los demás. Varía también el tipo; reparte entre estos:
  1. cómo hacerle una buena pregunta a las cartas;
  2. qué enseña una de las cartas de <cartas> (nómbrala con su nombre exacto);
  3. un ritual sencillo y seguro: escribir, agradecer, una vela, un vaso de agua, ordenar un espacio;
  4. una reflexión sobre amor propio, límites o decidir con calma;
  5. algo del cielo de hoy, usando solo lo que viene en <cielo>;
  6. una invitación a participar: dejar su pregunta con fecha de nacimiento, seguir la cuenta, dar toques a la pantalla;
  7. una frase de fe, con Dios como guía.

No prometas resultados ni des fechas. No hables de salud, embarazo, temas legales, inversiones ni brujería. No le hables a una persona en particular ni inventes nombres. No repitas ni parafrasees los de <ya_dichos>.

Ejemplos del tono (no los copies):
{ejemplos}"""


class TipsClaude:
    def __init__(self, cliente: anthropic.AsyncAnthropic | None = None, modelo: str | None = None):
        self.cliente = cliente or anthropic.AsyncAnthropic(timeout=ESPERA, max_retries=0)
        self.modelo = modelo or os.getenv("ANTHROPIC_MODEL_TIPS") or MODELO

    async def tanda(self, cielo: str, cartas: list[str], ya_dichos: list[str], ejemplos: list[str],
                    n: int = POR_TANDA) -> list[str]:
        """Devuelve hasta `n` tips nuevos; lista vacía si la IA falla (se siguen usando los fijos)."""
        try:
            r = await self.cliente.messages.create(
                model=self.modelo,
                max_tokens=2000,
                thinking={"type": "disabled"},
                output_config={"effort": "low", "format": FORMATO},
                system=SISTEMA.format(n=n, ejemplos="\n".join(f"- {e}" for e in ejemplos)),
                messages=[{"role": "user", "content":
                           f"<cielo>\n{cielo}\n</cielo>\n<cartas>\n" + "\n".join(cartas) + "\n</cartas>\n"
                           "<ya_dichos>\n" + "\n".join(f"- {t}" for t in ya_dichos) + "\n</ya_dichos>\n\n"
                           f"Escribe los {n} comentarios, solo con el JSON."}],
            )
            if r.stop_reason != "end_turn":
                log.warning(f"[TIPS] sin tanda ({r.stop_reason})")
                return []
            tips = json.loads(next(b.text for b in r.content if b.type == "text"))["tips"]
        except (anthropic.APIError, ValueError, KeyError, StopIteration) as exc:
            log.warning(f"[TIPS] se siguen usando los fijos ({type(exc).__name__})")
            return []
        buenos = [" ".join(t.split()) for t in tips
                  if isinstance(t, str) and MIN_PALABRAS <= len(t.split()) <= MAX_PALABRAS and not evaluar(t).sensible]
        log.info(f"[TIPS] {len(buenos)} tips nuevos")
        return buenos
