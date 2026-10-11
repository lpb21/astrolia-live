"""Descarga las 78 cartas del Rider-Waite-Smith de 1909 (dominio público) desde Wikimedia Commons
y las guarda con los id de tarot/mazo.json: tarot/img/la-torre.jpg, tarot/img/sota-espadas.jpg...

Uso:
    python -m tools.descargar_cartas            # descarga lo que falte
    python -m tools.descargar_cartas --simular  # solo muestra qué buscaría
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
import httpx

API = "https://commons.wikimedia.org/w/api.php"
WIKI = "https://en.wikipedia.org/w/api.php"
# Wikimedia exige un User-Agent que identifique la herramienta y un contacto
UA = "AstroliaLive/0.1 (descarga unica de cartas RWS 1909; contacto: astrolia)"
RAIZ = Path(__file__).resolve().parent.parent
MAZO = RAIZ / "tarot" / "mazo.json"
DESTINO = RAIZ / "tarot" / "img"

MAYORES = ["Fool", "Magician", "High Priestess", "Empress", "Emperor", "Hierophant", "Lovers",
           "Chariot", "Strength", "Hermit", "Wheel of Fortune", "Justice", "Hanged Man", "Death",
           "Temperance", "Devil", "Tower", "Star", "Moon", "Sun", "Judgement", "World"]
PALOS = {"copas": ("Cups", "Cups"), "oros": ("Pents", "Pentacles"),
         "espadas": ("Swords", "Swords"), "bastos": ("Wands", "Wands")}
RANGOS = ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
          "Page", "Knight", "Queen", "King"]


def candidatos(carta: dict) -> list[str]:
    """Nombres de archivo posibles en Commons, del más probable al menos probable."""
    n = carta["numero"]
    if carta["arcano"] == "mayor":
        nombre = MAYORES[n]
        return [f"RWS Tarot {n:02d} {nombre}.jpg", f"RWS Tarot {n:02d} {nombre}.png"]
    corto, largo = PALOS[carta["palo"]]
    return [f"{corto}{n:02d}.jpg", f"Tarot {RANGOS[n - 1]} of {largo}.jpg"]


ALTO = 1000   # px de alto; suficiente para el overlay


def descargar(http: httpx.Client, url: str) -> bytes | None:
    """Descarga con reintentos; ante un 429 espera lo que pida el servidor."""
    for intento in range(5):
        try:
            r = http.get(url)
            if r.status_code == 429:
                espera = int(r.headers.get("Retry-After", "0") or 0) or 15 * (intento + 1)
                print(f"  servidor ocupado, espero {espera} s…")
                time.sleep(espera)
                continue
            r.raise_for_status()
            return r.content
        except httpx.HTTPError as exc:
            print(f"  reintento {intento + 1}: {exc!r}")
            time.sleep(5 * (intento + 1))
    return None


def titulo_wikipedia(carta: dict) -> str | None:
    if carta["arcano"] == "mayor":
        return None
    return f"{RANGOS[carta['numero'] - 1]} of {PALOS[carta['palo']][1]}"


def desde_wikipedia(http: httpx.Client, cartas: list[dict]) -> dict[str, str]:
    """Plan B: {id: archivo} con la imagen principal del artículo de Wikipedia de cada carta."""
    titulos = {t: c["id"] for c in cartas if (t := titulo_wikipedia(c))}
    if not titulos:
        return {}
    r = http.get(WIKI, params={"action": "query", "format": "json", "redirects": 1,
                               "prop": "pageimages", "piprop": "name", "titles": "|".join(titulos)})
    r.raise_for_status()
    q = r.json().get("query", {})
    alias = {x["from"]: x["to"] for x in q.get("normalized", []) + q.get("redirects", [])}
    inverso = {}
    for t, id_ in titulos.items():
        final = t
        while final in alias:
            final = alias[final]
        inverso[final] = id_
    return {inverso[p["title"]]: p["pageimage"].replace("_", " ")
            for p in q.get("pages", {}).values() if p.get("pageimage") and p["title"] in inverso}


def consultar(http: httpx.Client, titulos: list[str]) -> dict[str, dict]:
    """Devuelve {título pedido: imageinfo} de los que existen, siguiendo redirecciones."""
    encontrados: dict[str, dict] = {}
    for i in range(0, len(titulos), 50):                       # la API acepta 50 títulos por consulta
        lote = titulos[i:i + 50]
        r = http.get(API, params={
            "action": "query", "format": "json", "redirects": 1, "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiextmetadatafilter": "LicenseShortName",
            "iiurlheight": ALTO,          # Wikimedia pide usar miniaturas, no originales
            "titles": "|".join(f"File:{t}" for t in lote)})
        r.raise_for_status()
        q = r.json().get("query", {})
        alias = {x["from"]: x["to"] for x in q.get("normalized", []) + q.get("redirects", [])}
        por_titulo = {p["title"]: p for p in q.get("pages", {}).values()
                      if "missing" not in p and p.get("imageinfo")}
        for t in lote:
            final = f"File:{t}"
            while final in alias:
                final = alias[final]
            if final in por_titulo:
                encontrados[t] = por_titulo[final]["imageinfo"][0]
        time.sleep(0.5)
    return encontrados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simular", action="store_true", help="no descarga, solo lista lo que buscaría")
    args = ap.parse_args()

    cartas = json.loads(MAZO.read_text(encoding="utf-8"))
    if args.simular:
        for c in cartas:
            print(f"{c['id']:28} -> {' | '.join(candidatos(c))}")
        return 0

    DESTINO.mkdir(parents=True, exist_ok=True)
    faltan = [c for c in cartas if not (DESTINO / f"{c['id']}.jpg").exists()]
    print(f"{len(cartas) - len(faltan)} ya descargadas, {len(faltan)} por descargar")

    with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as http:
        info = consultar(http, [t for c in faltan for t in candidatos(c)])
        sin_patron = [c for c in faltan if not any(t in info for t in candidatos(c))]
        extra = desde_wikipedia(http, sin_patron)
        if extra:
            print(f"Plan B (Wikipedia): {len(extra)} de {len(sin_patron)} encontradas")
            info.update(consultar(http, list(extra.values())))
        fuentes, sin_archivo, revisar, fallidas = [], [], [], []

        for c in faltan:
            opciones = candidatos(c) + ([extra[c["id"]]] if c["id"] in extra else [])
            elegido = next((t for t in opciones if t in info), None)
            if elegido is None:
                sin_archivo.append(c["id"])
                continue
            ii = info[elegido]
            licencia = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
            if "public domain" not in licencia.lower():
                revisar.append(f"{c['id']} ({elegido}): licencia '{licencia}'")
            contenido = descargar(http, ii.get("thumburl") or ii["url"])
            if contenido is None:
                fallidas.append(c["id"])
                continue
            (DESTINO / f"{c['id']}.jpg").write_bytes(contenido)
            fuentes.append(f"{c['id']}.jpg\t{ii['descriptionurl']}\t{licencia}")
            print(f"  ok {c['id']:28} <- {elegido}")
            time.sleep(1.5)                                      # trato amable con los servidores

    if fuentes:
        with (DESTINO / "FUENTES.tsv").open("a", encoding="utf-8") as f:
            f.write("\n".join(fuentes) + "\n")
    if revisar:
        print("\nRevisar licencia a mano (no dice 'public domain'):\n  " + "\n  ".join(revisar))
    if fallidas:
        print("\nExisten pero falló la descarga (vuelve a correr el script en unos minutos):\n  "
              + "\n  ".join(fallidas))
    if sin_archivo:
        print("\nNo encontradas en Commons; búscalas a mano y guárdalas con este nombre:\n  "
              + "\n  ".join(f"{i}.jpg" for i in sin_archivo))
    if sin_archivo or fallidas:
        return 1
    print(f"\nListo: {len(cartas)} cartas en {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())