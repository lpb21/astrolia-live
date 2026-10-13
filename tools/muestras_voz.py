"""Muestras para escoger la voz: baja las voces en español de Piper y graba con cada una el mismo
texto de una lectura. Deja una página con un reproductor por voz.

Uso:
    python -m tools.muestras_voz                 # todas las voces de VOCES (unos 480 MB la primera vez)
    python -m tools.muestras_voz --instaladas    # solo las que ya están en voz/, sin descargar nada
    python -m tools.muestras_voz es_AR-daniela-high es_MX-claude-high

Después abre voz/muestras/index.html en el navegador. Para usar la que elijas, pon en .env la línea
que la página muestra debajo de cada voz y reinicia el backend.
"""
from __future__ import annotations
import asyncio, html, sys
from pathlib import Path

from backend.voz import VozPiper, trocear
from tools.descargar_voz import DESTINO, bajar

# (modelo, hablante o None, cómo suena). Todas gratis, de https://huggingface.co/rhasspy/piper-voices
VOCES = (
    ("es_MX-claude-high", None, "México · la que usa el live hoy"),
    ("es_AR-daniela-high", None, "Argentina · mujer"),
    ("es_ES-sharvard-medium", 1, "España · mujer"),
    ("es_ES-sharvard-medium", 0, "España · hombre"),
    ("es_MX-ald-medium", None, "México · hombre"),
    ("es_ES-davefx-medium", None, "España · hombre"),
    ("es_ES-mls_10246-low", None, "España · calidad baja"),
    ("es_ES-mls_9972-low", None, "España · calidad baja"),
)
TEXTO = ("Barajando para Daniela. Daniela, gracias por la rosquilla, qué detalle tan bonito. "
         "Me preguntas si Andrés te va a buscar. En tu presente sale el Dos de Copas: hay cariño de los dos lados, "
         "aunque hoy ninguno se anima a dar el primer paso. Tu consejo es la Reina de Espadas: di lo que sientes "
         "con claridad y sin miedo. ¡Arranca el boost de tap tap! Tienen sesenta segundos.")
SALIDA = DESTINO / "muestras"


def _unir(partes: list[bytes]) -> bytes:
    """Une los WAV de cada trozo en uno solo (mismo formato: salen del mismo modelo)."""
    import io, wave
    salida = io.BytesIO()
    with wave.open(salida, "wb") as w:
        for k, parte in enumerate(partes):
            with wave.open(io.BytesIO(parte)) as r:
                if k == 0:
                    w.setparams(r.getparams())
                w.writeframes(r.readframes(r.getnframes()))
    return salida.getvalue()


async def grabar(modelo: str, hablante: int | None) -> Path:
    """Graba TEXTO con esa voz tal como sonaría en el live (mismos trozos y mismos arreglos de pronunciación)."""
    voz = VozPiper(DESTINO / f"{modelo}.onnx", hablante)
    partes = [(await voz.sintetizar(t))[0] for t in trocear(TEXTO)]
    destino = SALIDA / (modelo + (f"-{hablante}" if hablante is not None else "") + ".wav")
    destino.write_bytes(_unir(partes))
    return destino


def pagina(hechas: list[tuple[str, int | None, str, Path]]) -> str:
    filas = []
    for modelo, hablante, nota, archivo in hechas:
        env = f"VOZ_MODELO=voz/{modelo}.onnx" + (f"\nVOZ_HABLANTE={hablante}" if hablante is not None else "")
        filas.append(f"<section><h2>{html.escape(nota)}</h2><p class=m>{html.escape(modelo)}</p>"
                     f"<audio controls preload=none src=\"{html.escape(archivo.name)}\"></audio>"
                     f"<pre>{html.escape(env)}</pre></section>")
    return ("<!doctype html><html lang=es><meta charset=utf-8><meta name=viewport content='width=device-width, initial-scale=1'>"
            "<title>Astrolia Live — voces</title><style>"
            "body{font:16px/1.45 system-ui,sans-serif;background:#151022;color:#efe9fb;max-width:720px;margin:0 auto;padding:24px 16px}"
            "h1{font-size:22px}h2{font-size:18px;margin:0}section{background:#1f1833;border:1px solid #372c55;border-radius:10px;"
            "padding:14px;margin:12px 0}.m{color:#a79cc2;margin:2px 0 10px;font-size:14px}audio{width:100%}"
            "pre{background:#151022;border-radius:6px;padding:8px 10px;margin:10px 0 0;color:#ecc878;white-space:pre-wrap}"
            "blockquote{color:#a79cc2;border-left:3px solid #372c55;margin:12px 0;padding-left:12px}</style>"
            "<h1>Voces disponibles</h1><p>Todas dicen el mismo texto. Para usar una, copia en <code>.env</code> "
            "lo que aparece debajo de ella y reinicia el backend.</p>"
            f"<blockquote>{html.escape(TEXTO)}</blockquote>" + "".join(filas) + "</html>")


async def _todas(voces) -> list:
    hechas = []
    for modelo, hablante, nota in voces:
        print(f"grabando {modelo}" + (f" (voz {hablante})" if hablante is not None else "") + "…")
        hechas.append((modelo, hablante, nota, await grabar(modelo, hablante)))
    return hechas


def main() -> int:
    args = sys.argv[1:]
    voces = list(VOCES)
    if "--instaladas" in args:
        voces = [v for v in voces if (DESTINO / f"{v[0]}.onnx").is_file()]
    elif args:
        voces = [v for v in VOCES if v[0] in args] or [(a, None, a) for a in args]
    if "--instaladas" not in args:
        voces = [v for v in voces if bajar(v[0]) == 0]
    if not voces:
        print("No hay ninguna voz para grabar.")
        return 1
    SALIDA.mkdir(parents=True, exist_ok=True)
    hechas = asyncio.run(_todas(voces))
    (SALIDA / "index.html").write_text(pagina(hechas), encoding="utf-8")
    print(f"Listo: abre {SALIDA / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
