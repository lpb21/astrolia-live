"""Voz: convierte en audio lo que el sistema dice. La lectura se parte en trozos cortos y cada trozo
se sintetiza aparte, para empezar a sonar en uno o dos segundos sin esperar el texto completo."""
from __future__ import annotations
import asyncio, io, logging, re, unicodedata, wave
from pathlib import Path
from typing import Protocol

log = logging.getLogger("voz")

MODELO = Path(__file__).parent.parent / "voz" / "es_MX-claude-high.onnx"    # lo baja tools/descargar_voz.py
PALABRAS_TROZO = 18

_FRASES = re.compile(r"[^.!?…]+[.!?…]+[\"”»)]*|[^.!?…]+$")
_PAUSAS = re.compile(r"(?<=[,;:])\s+")
_NO_SE_DICE = re.compile(r"[^\w\s.,;:¿?¡!()'\"%-]", re.UNICODE)


def trocear(texto: str, maximo: int = PALABRAS_TROZO) -> list[str]:
    """Parte el texto por frases y junta las cortas hasta `maximo` palabras por trozo."""
    trozos, actual = [], ""
    frases = []
    for frase in (f.strip() for f in _FRASES.findall(texto)):
        # Una frase muy larga se corta en sus comas, para que no tarde en empezar a sonar
        frases += _PAUSAS.split(frase) if len(frase.split()) > maximo + 8 else [frase]
    for frase in (f.strip() for f in frases):
        if not frase:
            continue
        junto = f"{actual} {frase}".strip()
        if actual and len(junto.split()) > maximo:
            trozos.append(actual)
            actual = frase
        else:
            actual = junto
    return trozos + [actual] if actual else trozos


def para_decir(texto: str) -> str:
    """El texto como debe llegar a la voz: sin emojis ni símbolos (los nombres de cuenta traen muchos)
    y con las letras decorativas pasadas a letras normales."""
    t = _NO_SE_DICE.sub(" ", unicodedata.normalize("NFKC", texto)).replace("_", " ")
    return " ".join(t.split())


class Voz(Protocol):
    async def sintetizar(self, texto: str) -> tuple[bytes, float]:
        """Devuelve (audio WAV, duración en segundos)."""
        ...


class VozPiper:
    """Voz local con Piper: gratis, sin cuenta y sin enviar nada a internet. En este equipo genera el
    audio a algo más del doble de la velocidad a la que se escucha."""

    def __init__(self, modelo: Path = MODELO):
        self.modelo = modelo
        self._voz = None
        self._candado = asyncio.Lock()        # una síntesis a la vez: usa todos los núcleos

    def _cargar(self):
        if self._voz is None:
            from piper import PiperVoice      # tarda en importar; solo si se va a usar
            self._voz = PiperVoice.load(str(self.modelo))
        return self._voz

    def _wav(self, texto: str) -> tuple[bytes, float]:
        salida = io.BytesIO()
        with wave.open(salida, "wb") as w:
            self._cargar().synthesize_wav(texto, w)
        datos = salida.getvalue()
        with wave.open(io.BytesIO(datos)) as w:
            return datos, w.getnframes() / w.getframerate()

    async def sintetizar(self, texto: str) -> tuple[bytes, float]:
        async with self._candado:
            return await asyncio.to_thread(self._wav, para_decir(texto) or ".")

    async def calentar(self) -> None:
        """Carga el modelo y hace una síntesis corta: la primera tarda varios segundos."""
        try:
            await self.sintetizar("Hola.")
            log.info(f"voz lista ({self.modelo.stem})")
        except Exception:
            log.exception("[VOZ] no se pudo cargar la voz; el live sigue sin audio")
