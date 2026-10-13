"""Voz: convierte en audio lo que el sistema dice. La lectura se parte en trozos cortos y cada trozo
se sintetiza aparte, para empezar a sonar en uno o dos segundos sin esperar el texto completo."""
from __future__ import annotations
import array, asyncio, io, logging, re, time, unicodedata, wave
from pathlib import Path
from typing import Protocol

log = logging.getLogger("voz")

MODELO = Path(__file__).parent.parent / "voz" / "es_MX-claude-high.onnx"    # lo baja tools/descargar_voz.py
PALABRAS_TROZO = 18
FRASE_LARGA = 40          # solo una frase más larga que esto se corta en sus comas: cortar suena a tropiezo
UMBRAL_SILENCIO = 350     # amplitud (de 32767) por debajo de la cual se considera silencio
AIRE_ANTES, AIRE_DESPUES = 0.04, 0.22    # segundos de silencio que se dejan al recortar cada trozo
# espeak marca "día" o "envía" como i + ʲ + a. Esta voz se entrenó sin esa marca y la pronuncia como
# una consonante ("dira", "envida"); quitándola dice la i y la a seguidas, como debe ser.
SOBRAN = {"ʲ"}

_FRASES = re.compile(r"[^.!?…]+[.!?…]+[\"”»)]*|[^.!?…]+$")
_PAUSAS = re.compile(r"(?<=[,;:])\s+")
_NO_SE_DICE = re.compile(r"[^\w\s.,;:¿?¡!()'\"%-]", re.UNICODE)


def trocear(texto: str, maximo: int = PALABRAS_TROZO) -> list[str]:
    """Parte el texto por frases y junta las cortas hasta `maximo` palabras por trozo."""
    trozos, actual = [], ""
    frases = []
    for frase in (f.strip() for f in _FRASES.findall(texto)):
        # Una frase muy larga se corta en sus comas, para que no tarde en empezar a sonar
        frases += _PAUSAS.split(frase) if len(frase.split()) > FRASE_LARGA else [frase]
    for frase in (f.strip() for f in frases):
        if not frase:
            continue
        junto = f"{actual} {frase}".strip()
        if actual and len(junto.split()) > maximo and len(actual.split()) >= 6:    # un trozo muy corto se une al siguiente
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


def recortar_silencio(datos: bytes) -> tuple[bytes, float]:
    """Quita el silencio del principio y del final de un WAV de 16 bits, dejando un respiro corto, para
    que los trozos no queden separados por huecos. Devuelve (WAV, duración)."""
    with wave.open(io.BytesIO(datos)) as w:
        params, cuadros = w.getparams(), w.readframes(w.getnframes())
    if params.sampwidth != 2 or not cuadros:
        return datos, len(cuadros) / max(params.framerate * params.nchannels * params.sampwidth, 1)
    muestras = array.array("h", cuadros)
    paso = params.nchannels
    suena = [i for i in range(0, len(muestras), paso * 32) if abs(muestras[i]) > UMBRAL_SILENCIO]
    if suena:
        desde = max(suena[0] - int(AIRE_ANTES * params.framerate) * paso, 0)
        hasta = min(suena[-1] + paso * 32 + int(AIRE_DESPUES * params.framerate) * paso, len(muestras))
        muestras = muestras[desde - desde % paso:hasta - hasta % paso]
    salida = io.BytesIO()
    with wave.open(salida, "wb") as w:
        w.setparams(params)
        w.writeframes(muestras.tobytes())
    return salida.getvalue(), len(muestras) / paso / params.framerate


SIN_NOMBRE = "corazón"      # cómo se le dice a quien tiene por nombre solo emojis o símbolos


def nombre_decible(nickname: str, si_no_hay: str = SIN_NOMBRE) -> str:
    """El nombre de la cuenta como se puede decir y leer: sin emojis ni adornos. Si no queda ninguna
    letra ("🖤"), devuelve un apelativo cariñoso en vez de un silencio."""
    limpio = para_decir(nickname).strip(" .,;:-'\"")
    return limpio if re.search(r"[^\W\d_]", limpio) else si_no_hay


class Voz(Protocol):
    async def sintetizar(self, texto: str) -> tuple[bytes, float]:
        """Devuelve (audio WAV, duración en segundos)."""
        ...


class VozPiper:
    """Voz local con Piper: gratis, sin cuenta y sin enviar nada a internet. En este equipo genera el
    audio a algo más del doble de la velocidad a la que se escucha."""

    def __init__(self, modelo: Path = MODELO, hablante: int | None = None):
        self.modelo = modelo
        self.hablante = hablante              # solo para modelos con varias voces (p. ej. es_ES-sharvard: 1 = mujer)
        self._voz = None
        self._candado = asyncio.Lock()        # una síntesis a la vez: usa todos los núcleos
        self.ritmo = 0.5                      # segundos de cómputo por segundo de audio (se va midiendo)

    def _cargar(self):
        if self._voz is None:
            from piper import PiperVoice      # tarda en importar; solo si se va a usar
            voz = PiperVoice.load(str(self.modelo))
            fonemas = voz.phonemize
            voz.phonemize = lambda texto: [[f for f in frase if f not in SOBRAN] for frase in fonemas(texto)]
            self._voz = voz
        return self._voz

    def _wav(self, texto: str) -> tuple[bytes, float]:
        salida = io.BytesIO()
        with wave.open(salida, "wb") as w:
            voz = self._cargar()
            if self.hablante is None:
                voz.synthesize_wav(texto, w)
            else:
                from piper import SynthesisConfig
                voz.synthesize_wav(texto, w, syn_config=SynthesisConfig(speaker_id=self.hablante))
        return recortar_silencio(salida.getvalue())

    async def sintetizar(self, texto: str) -> tuple[bytes, float]:
        async with self._candado:
            inicio = time.perf_counter()
            audio, dur = await asyncio.to_thread(self._wav, para_decir(texto) or ".")
            if dur > 1:           # cuánto tarda en generar un segundo de audio; lo usa el worker para no dejar huecos
                self.ritmo = 0.7 * self.ritmo + 0.3 * (time.perf_counter() - inicio) / dur
            return audio, dur

    async def calentar(self) -> None:
        """Carga el modelo y hace una síntesis corta: la primera tarda varios segundos."""
        try:
            await self.sintetizar("Hola.")
            log.info(f"voz lista ({self.modelo.stem})")
        except Exception:
            log.exception("[VOZ] no se pudo cargar la voz; el live sigue sin audio")
