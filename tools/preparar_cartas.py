"""Prepara las cartas para el live: tamaño fijo con buen filtro y enfoque ligero.
Lee tarot/img/*.jpg y escribe tarot/img_live/*.webp. No recorta ni decora.

Uso:
    python -m tools.preparar_cartas              # 800 px de alto
    python -m tools.preparar_cartas --alto 1000
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from PIL import Image, ImageFilter, ImageOps

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "tarot" / "img"
DESTINO = RAIZ / "tarot" / "img_live"


def preparar(ruta: Path, alto: int) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
    w, h = img.size
    if h != alto:
        img = img.resize((round(w * alto / h), alto), Image.LANCZOS)
    return img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alto", type=int, default=800, help="alto final en px (2 veces el alto en pantalla)")
    args = ap.parse_args()
    archivos = sorted(ORIGEN.glob("*.jpg"))
    if not archivos:
        print(f"No hay imágenes en {ORIGEN}; corre primero python -m tools.descargar_cartas")
        return 1
    DESTINO.mkdir(parents=True, exist_ok=True)
    chicas = []
    for ruta in archivos:
        with Image.open(ruta) as original:
            if original.size[1] < args.alto:
                chicas.append(f"{ruta.name} ({original.size[1]} px)")
        preparar(ruta, args.alto).save(DESTINO / f"{ruta.stem}.webp", "WEBP", quality=92)
    print(f"{len(archivos)} cartas listas en {DESTINO}")
    if chicas:
        print("Ojo, se agrandaron (pierden nitidez); conviene bajar el original:\n  " + "\n  ".join(chicas))
    return 0


if __name__ == "__main__":
    sys.exit(main())