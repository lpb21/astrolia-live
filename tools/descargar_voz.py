"""Descarga la voz de Piper que usa el live (gratis, corre en este equipo) a voz/.

Uso:
    python -m tools.descargar_voz                       # es_MX-claude-high (por defecto)
    python -m tools.descargar_voz es_MX-ald-medium      # otra voz de https://huggingface.co/rhasspy/piper-voices
"""
from __future__ import annotations
import sys
from pathlib import Path
import httpx

DESTINO = Path(__file__).resolve().parent.parent / "voz"
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def bajar(nombre: str) -> int:
    """Baja el modelo y su configuración a voz/ si no están. Devuelve 0 si quedó lista."""
    try:
        region, persona, calidad = nombre.split("-")
    except ValueError:
        print("El nombre debe ser como es_MX-claude-high (idioma_PAÍS-voz-calidad)")
        return 1
    DESTINO.mkdir(exist_ok=True)
    carpeta = f"{BASE}/{region.split('_')[0]}/{region}/{persona}/{calidad}"
    with httpx.Client(follow_redirects=True, timeout=120) as http:
        for ext in (".onnx.json", ".onnx"):
            destino = DESTINO / f"{nombre}{ext}"
            if destino.exists():
                print(f"ya está {destino.name}")
                continue
            print(f"bajando {destino.name}…")
            with http.stream("GET", f"{carpeta}/{nombre}{ext}") as r:
                if r.status_code != 200:
                    print(f"No se encontró esa voz ({r.status_code}): {carpeta}/{nombre}{ext}")
                    return 1
                with destino.open("wb") as f:
                    for trozo in r.iter_bytes(1 << 20):
                        f.write(trozo)
    print(f"Listo: {DESTINO / nombre}.onnx")
    return 0


def main() -> int:
    return bajar(sys.argv[1] if len(sys.argv) > 1 else "es_MX-claude-high")


if __name__ == "__main__":
    sys.exit(main())
