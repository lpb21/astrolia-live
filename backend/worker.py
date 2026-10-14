from __future__ import annotations
import asyncio, logging
from collections import OrderedDict
from dataclasses import dataclass, field
import random
from datetime import datetime, timedelta, timezone
from typing import Protocol
from astro.cielo import Cielo, cielo
from astro.signos import es_menor, nombre_dicho
from backend.bitacora import anotar
from backend.boost import Boost
from backend.cola import PEQUENO, Cola, Item
from backend.filtro import MINIMO, evaluar
from backend.generador import LimiteGasto
from backend import frases
from backend.frases import (AVISO_GRATIS, BENDICIONES, BIENVENIDA, ESCRIBE_EN_CHAT, GRATIS_AGOTADA, PIDE_ROSQUILLA, SALUD, LECTURA_PRIVADA, SINASTRIA, Y_LOS_DEMAS, DUDA_FECHA, FECHA_INCOMPLETA, PIDE_FECHA_PROPIA, BOOST_GANO, BOOST_GANO_SIN_PREGUNTA, BOOST_INICIO, FALLO,
                            NO_SE_LEE, PIDE_FECHA, PIDE_PREGUNTA, SOLO_ADULTOS)
from backend.prompt import PALABRAS_CORTO, PALABRAS_GRUPO, armar_prompt, pesa, _resumen_cielo as resumen_cielo
from backend.voz import Voz, nombre_decible, trocear
from tarot.tirada import CartaTirada, nivel_para, tirar

log = logging.getLogger("worker")
MAX_HISTORIAL = 50
ENTRE_TROZOS = 0.12    # segundos que el navegador tarda en pasar de un trozo de audio al siguiente
MAX_AUDIOS = 80        # trozos de audio que se conservan para que el overlay los pida
# Una lectura queda en pantalla al menos BASE + POR_CARTA por carta, y PAUSA más al terminar de decirla
MIN_LECTURA_BASE, MIN_LECTURA_POR_CARTA, PAUSA_LECTURA = 6.0, 3.0, 3.0
MIN_TIPS_LISTOS = 2          # con esto o menos en espera, se pide otra tanda a la IA
MAX_TIPS_RECORDADOS = 24     # cuántos tips ya dichos se le recuerdan para que no los repita
CARTA_MOMENTO_CADA = timedelta(minutes=3)    # lo más seguido que sale la carta del momento (usa la IA)
CIELO_CADA = timedelta(minutes=10)           # lo más seguido que se cuenta el cielo de hoy
EVENTO_CADA = timedelta(minutes=15)          # lo más seguido que se cuenta un evento astrológico (astro/eventos.py)
CIELO_EN_LECTURA_CADA = 3                    # el cielo del día se nombra en una de cada tantas lecturas
VOZ_LENTA = 0.9                              # segundos de cómputo por segundo de audio desde los que la voz no da abasto
MAX_GRUPO = 5                                # a cuántas personas se les lee junta la carta corta
SALUDOS_POR_VEZ = 3    # a cuántas personas se nombra en una bienvenida
CIERRES_POR_TURNO = 1  # frases de fe por lectura: una sola (con cuatro para elegir, la IA llegó a decir dos)
MAX_PEDIDOS = 3        # a cuántas personas se les pide la fecha en un mismo aviso


class Generador(Protocol):
    async def generar(self, prompt: dict) -> dict: ...


class GeneradorFalso:
    async def generar(self, prompt: dict) -> dict:
        return {"sensible": False, "categoria": "", "respuesta": "Respuesta de prueba del generador falso."}


@dataclass
class Salida:
    user: str
    nickname: str
    pregunta: str
    tipo: str          # "lectura" | "mensaje_fijo" | "pide_fecha" | "pide_pregunta" | "boost" | "aviso" | "bienvenida" | "pide_regalo" | "agotada" | "relleno" | "carta_momento" | "barajando"
    texto: str
    ts: datetime
    cartas: list[CartaTirada] = field(default_factory=list)
    nivel: str = ""
    signo: str = ""    # signo solar de quien pregunta; en pantalla va en lugar de su fecha
    # Con voz: el texto en trozos, cada uno con su audio y su duración real. Se van agregando mientras
    # se sintetizan; `completo` avisa que ya no vienen más.
    trozos: list[dict] = field(default_factory=list)
    completo: bool = False


class Worker:
    def __init__(self, cola: Cola, generador: Generador,
                 palabras_por_seg: float = 2.5, espera_vacia: float = 1.0,
                 rng: random.Random | None = None, boost: Boost | None = None,
                 aviso_gratis: timedelta | None = None, bienvenida: timedelta | None = None,
                 voz: Voz | None = None, relleno: timedelta | None = None, tips=None,
                 sin_live: timedelta | None = None, eventos=None):
        self.cola = cola
        self.eventos = eventos                # astro.eventos.FuenteEventos; None = sin API de eventos (lo de hoy)
        self._n_lecturas = 0                  # para nombrar el cielo solo en una de cada CIELO_EN_LECTURA_CADA
        # Sin live no hay a quién hablarle: si la ingesta avisa que el live terminó, o pasa `sin_live` sin
        # que llegue ningún evento, la voz deja de rellenar (tips, carta del momento, boost, avisos).
        self.sin_live = sin_live              # None = no se vigila
        self._senal: datetime | None = None   # último evento recibido del live
        self._conectado: bool | None = None   # lo que dijo la ingesta; None = aún no ha dicho nada
        self.tips = tips                      # IA que escribe tips nuevos; None = solo los fijos de frases.py
        self._tips_listos: list[str] = []     # tips de la IA esperando su turno
        self._tips_dichos: list[str] = []     # los últimos que se dijeron, para pedirle que no los repita
        self._pidiendo_tips: asyncio.Task | None = None
        self.relleno = relleno                # silencio tras el cual la voz llena el rato; None = se queda callada
        self._ultima_voz: datetime | None = None
        self._n_relleno = 0
        self._ultimo_relleno: dict[str, datetime] = {}
        self.voz = voz                        # None = sin audio: la duración se calcula por palabras
        self.audios: OrderedDict[str, bytes] = OrderedDict()   # id de trozo -> WAV
        self._n_audio = 0
        self.bienvenida = bienvenida          # pausa mínima entre un saludo y el siguiente; None = no saludar
        self._llegadas: dict[str, str] = {}   # quienes entraron y aún no se saludan (user -> nombre)
        self._saludados: set[str] = set()     # a cada quien se le saluda una vez por live
        self._ultima_bienvenida: datetime | None = None
        self.aviso_gratis = aviso_gratis      # cada cuánto la voz recuerda cómo pedir la pregunta gratis
        self._proximo_aviso: datetime | None = None
        self._ultimo_aviso: datetime | None = None
        # Las frases de fe se barajan una vez y se van ofreciendo de a cuatro, sin repetir hasta dar la vuelta
        self._cierres = list(BENDICIONES)
        (rng or random).shuffle(self._cierres)
        self._cierre_n = 0
        self._usos: dict[tuple, int] = {}     # cuántas veces se ha dicho cada aviso, para rotar sus frases
        self.boost = boost             # None = sin boost de likes
        self._avisado_lenta = False
        self._menores_avisados: set[str] = set()      # a quién ya se le dijo que el live es para mayores
        self.generador = generador
        self.palabras_por_seg = palabras_por_seg
        self.espera_vacia = espera_vacia
        self.rng = rng                 # solo para pruebas; None = azar del sistema
        self.pausado = False
        self.alerta = ""                       # motivo de una pausa automática, para el panel
        self.actual: Item | None = None
        self.hablando: Salida | None = None   # lo que se está diciendo ahora; lo muestra el overlay
        self.salidas: list[Salida] = []
        self.saltados: list[dict] = []
        self._cielo: Cielo | None = None

    def _cielo_actual(self, ahora: datetime) -> Cielo:
        if self._cielo is None or ahora - self._cielo.momento > timedelta(hours=1):
            self._cielo = cielo(ahora)
        return self._cielo

    def _saltar(self, item: Item, categoria: str, motivo: str) -> None:
        self.cola.cerrar(item.user, "saltado")
        anotar("saltado", item.user, item.nickname, texto=f"Turno saltado ({categoria}: {motivo})")
        self.saltados = (self.saltados + [{"user": item.user, "pregunta": item.pregunta,
                                           "categoria": categoria, "motivo": motivo}])[-MAX_HISTORIAL:]
        log.info(f"[SALTADO] {item.user} ({categoria}: {motivo})")

    async def _entregar(self, item: Item, tipo: str, texto: str, ahora: datetime, a_quien: str | None = None) -> None:
        log.info(f"[{tipo.upper()}] {item.user}{' (grupo: ' + a_quien + ')' if a_quien else ''}: {texto[:80]}")
        await self._decir(Salida(item.user, a_quien or (self._nombre(item) if tipo == "lectura" else item.nickname), item.pregunta,
                                 tipo, texto, ahora, list(item.cartas), item.nivel,
                                 item.dato.signo if item.dato else ""))
        self.cola.cerrar(item.user, "hecho")

    @staticmethod
    def _nombre(item: Item) -> str:
        """Cómo se le dice en el turno: el nombre con que se presentó ("soy Lizet…") o, si no, el de su cuenta."""
        return nombre_dicho(item.pregunta) or item.nickname

    async def _rechazar(self, item: Item, categoria: str, motivo: str, ahora: datetime,
                        frases: tuple[str, ...] = NO_SE_LEE) -> None:
        """Salta el turno, pero diciéndolo en voz: quien regaló no se queda sin respuesta.
        A quien es menor se le dice una sola vez por live; si sigue escribiendo, se salta en silencio."""
        if categoria != "menor" or item.user not in self._menores_avisados:
            await self._decir(Salida(item.user, item.nickname, "", "mensaje_fijo", self._frase(frases), ahora))
        if categoria == "menor":
            self._menores_avisados.add(item.user)
        self._saltar(item, categoria, motivo)

    def _cierres_del_turno(self) -> tuple[str, ...]:
        n = len(self._cierres)
        elegidas = tuple(self._cierres[(self._cierre_n + k) % n] for k in range(min(CIERRES_POR_TURNO, n)))
        self._cierre_n = (self._cierre_n + CIERRES_POR_TURNO) % max(n, 1)
        return elegidas

    def _frase(self, frases: tuple):
        """La frase que toca de un aviso: van rotando para que la voz no repita siempre la misma."""
        n = self._usos.get(frases, 0)
        self._usos[frases] = n + 1
        return frases[n % len(frases)]

    async def _decir(self, salida: Salida) -> None:
        """Registra la salida y la deja en `hablando` el tiempo que tarda en decirse."""
        self.salidas = (self.salidas + [salida])[-MAX_HISTORIAL:]
        anotar(salida.tipo, salida.user, salida.nickname, texto=salida.texto, nivel=salida.nivel,
               pregunta=salida.pregunta, signo=salida.signo, cartas=[f"{t.posicion}: {t.carta.nombre}" for t in salida.cartas])
        if self.voz is not None and await self._decir_con_voz(salida):
            return
        if self.palabras_por_seg <= 0:
            return
        self.hablando = salida
        try:
            await asyncio.sleep(self._duracion(salida))
        finally:
            self.hablando = None

    async def _trozo_con_audio(self, texto: str) -> dict:
        audio, dur = await self.voz.sintetizar(texto)
        self._n_audio += 1
        clave = f"a{self._n_audio}"
        self.audios[clave] = audio
        while len(self.audios) > MAX_AUDIOS:
            self.audios.popitem(last=False)
        return {"texto": texto, "audio": clave, "dur": round(dur, 2)}

    async def _decir_con_voz(self, salida: Salida) -> bool:
        """Dice la salida con audio real. Sintetiza el primer trozo, lo pone al aire y va preparando los
        siguientes mientras suena. Devuelve False si la voz falló antes de empezar (se sigue sin audio)."""
        textos = trocear(salida.texto)
        ritmo = getattr(self.voz, "ritmo", 0.5)       # segundos de cómputo por segundo de audio
        try:
            listos = [await self._trozo_con_audio(textos[0])]
            # Antes de salir al aire se adelanta lo necesario para que el trozo siguiente alcance a estar
            # listo mientras suena lo ya preparado; si no, queda un silencio entre frases.
            while len(listos) < len(textos):
                falta = len(textos[len(listos)].split()) / 2.6 * ritmo * 1.25
                if sum(t["dur"] for t in listos) >= falta:
                    break
                listos.append(await self._trozo_con_audio(textos[len(listos)]))
        except Exception:
            log.exception("[VOZ] falló la síntesis; esta salida va sin audio")
            return False
        salida.trozos = listos
        esperar = self.palabras_por_seg > 0           # en las pruebas no se espera a que "suene"
        reloj = asyncio.get_running_loop().time
        inicio = reloj()
        fin = inicio + 1.0                            # el overlay tarda un momento en enterarse y empezar
        self.hablando = salida
        try:
            fin += sum(t["dur"] + ENTRE_TROZOS for t in listos)
            for texto in textos[len(listos):]:
                try:
                    trozo = await self._trozo_con_audio(texto)
                except Exception:
                    log.exception("[VOZ] falló un trozo; se corta ahí el audio")
                    break
                salida.trozos = salida.trozos + [trozo]
                fin = max(fin, reloj()) + trozo["dur"] + ENTRE_TROZOS    # un trozo no suena antes de estar listo
            salida.completo = True
            if salida.cartas:                              # que las cartas alcancen a verse, y una pausa
                fin = max(fin, inicio + MIN_LECTURA_BASE + MIN_LECTURA_POR_CARTA * len(salida.cartas)) + PAUSA_LECTURA
            if esperar:
                await asyncio.sleep(max(fin - reloj(), 0) + 0.4)
        finally:
            self.hablando = None
        return True

    def _duracion(self, salida: Salida) -> float:
        """Segundos que la salida queda al aire: lo que tarda en decirse y, si es una lectura,
        un mínimo para que las cartas alcancen a verse más una pausa antes del turno siguiente."""
        seg = len(salida.texto.split()) / self.palabras_por_seg
        if not salida.cartas:
            return seg
        return max(seg, MIN_LECTURA_BASE + MIN_LECTURA_POR_CARTA * len(salida.cartas)) + PAUSA_LECTURA

    def senal(self, ahora: datetime) -> None:
        """Llegó un evento del live (comentario, regalo, toque, entrada): hay live y hay gente."""
        self._senal, self._conectado = ahora, True

    def conexion(self, conectado: bool, ahora: datetime) -> None:
        """La ingesta avisa que se conectó al live o que el live terminó o se cayó."""
        if conectado != self._conectado:
            log.info("[LIVE] conectado" if conectado else "[LIVE] terminó o se perdió la conexión: la voz deja de rellenar")
        self._conectado = conectado
        if conectado:
            self._senal = ahora

    def en_vivo(self, ahora: datetime) -> bool:
        if self._conectado is False:
            return False
        if self.sin_live is None:
            return True
        if self._senal is None:               # recién arrancado: se le da ese mismo plazo a la ingesta
            self._senal = ahora
        return ahora - self._senal <= self.sin_live

    def llegada(self, user: str, nickname: str) -> None:
        """Alguien entró al live. Se le saluda cuando no haya a quién leerle, y no muy seguido."""
        nickname = nombre_decible(nickname, "")          # a quien no tiene nombre que decir no se le saluda
        if self.bienvenida is None or user in self._saludados or not nickname:
            return
        self._saludados.add(user)
        self._llegadas[user] = nickname.strip()
        while len(self._llegadas) > 30:                       # en una oleada se saluda a los últimos
            del self._llegadas[next(iter(self._llegadas))]

    async def _dar_bienvenida(self, ahora: datetime) -> bool:
        if not self._llegadas or self.bienvenida is None:
            return False
        if self._ultima_bienvenida and ahora - self._ultima_bienvenida < self.bienvenida:
            return False
        nombres = list(self._llegadas.values())[-SALUDOS_POR_VEZ:]
        mas = len(self._llegadas) > len(nombres)
        self._llegadas.clear()
        self._ultima_bienvenida = ahora
        juntos = nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]
        una, varias = self._frase(BIENVENIDA)
        if mas:
            juntos = ", ".join(nombres) + Y_LOS_DEMAS
        texto = (una if len(nombres) == 1 and not mas else varias).format(n=juntos)
        log.info(f"[BIENVENIDA] {juntos}")
        await self._decir(Salida("", "", "", "bienvenida", texto, ahora))
        return True

    def voz_lenta(self) -> bool:
        """La voz tarda más en generarse de lo que dura: el equipo no da abasto (pasó el 13-oct-2026 con
        LIVE Studio transmitiendo). Mientras siga así no se rellena ni se saluda: todo va a las lecturas."""
        lenta = self.voz is not None and getattr(self.voz, "ritmo", 0) > VOZ_LENTA
        if lenta and not self._avisado_lenta:
            log.warning(f"[VOZ] lenta: tarda {self.voz.ritmo:.1f} s por cada segundo de audio. El equipo está "
                        "sobrecargado; se suspenden tips, saludos y avisos hasta que se recupere.")
        self._avisado_lenta = lenta
        return lenta

    async def _recordar_gratis(self, ahora: datetime) -> bool:
        if self.cola.alguien_listo(ahora) or self.voz_lenta():
            return False                      # primero quien ya espera su lectura; el recordatorio va después
        if self.aviso_gratis is None or self.cola.max_gratis <= 0 or not self.en_vivo(ahora):
            return False
        if self._proximo_aviso is None:
            self._proximo_aviso = ahora + min(self.aviso_gratis, timedelta(minutes=1))   # el primero, pronto
        if self.cola.preguntaron_por_gratis:
            # Alguien preguntó "¿hay preguntas gratis?": se responde ya, salvo que se acabe de decir
            self.cola.preguntaron_por_gratis = False
            if self._ultimo_aviso is None or ahora - self._ultimo_aviso >= timedelta(seconds=60):
                self._proximo_aviso = ahora
        if ahora < self._proximo_aviso:
            return False
        self._ultimo_aviso = ahora
        self._proximo_aviso = ahora + self.aviso_gratis
        log.info("[AVISO] pregunta gratis")
        await self._decir(Salida("", "", "", "aviso", self._frase(AVISO_GRATIS), ahora))
        return True

    async def _procesar(self, item: Item, ahora: datetime) -> None:
        breve = False
        if es_menor(item.dato, ahora.date()):
            await self._rechazar(item, "menor", "fecha de nacimiento", ahora, SOLO_ADULTOS)
            return
        if item.pregunta:
            f = evaluar(item.pregunta)
            if f.sensible:
                propias = {"salud": SALUD, "embarazo": LECTURA_PRIVADA, "compatibilidad": SINASTRIA}.get(f.categoria)
                if f.accion == "mensaje_fijo" or (f.accion == "invitar" and item.valor == 0):
                    texto = self._frase(propias).format(n=nombre_decible(self._nombre(item))) if propias else f.mensaje
                    await self._entregar(item, "mensaje_fijo", texto, ahora)
                    return
                if f.accion == "invitar":
                    pass               # compatibilidad con regalo: se lee, y la IA invita a la sinastría al final
                elif f.accion == "breve":
                    breve = True       # tema legal: se lee, pero solo un sí o no muy corto, sea cual sea el regalo
                elif f.accion != "con_regalo" or item.valor < MINIMO.get(f.categoria, 0):
                    await self._rechazar(item, f.categoria, f.termino, ahora)
                    return
                # tema que se lee con regalo (embarazo) y lo envió: sigue a la lectura

        # Regalo pequeño sin pregunta: una carta y un mensaje corto, junto con quienes estén en la misma
        grupo = self.cola.tomar_grupo(item, ahora, MAX_GRUPO - 1) if not item.pregunta and 0 < item.valor < PEQUENO else []
        corto = not item.pregunta and 0 < item.valor < PEQUENO
        try:
            await self._leer(item, ahora, breve, corto, grupo)
        finally:
            for otro in grupo:                        # pase lo que pase con la lectura, no quedan colgados
                self.cola.cerrar(otro.user, "hecho")

    async def _leer(self, item: Item, ahora: datetime, breve: bool, corto: bool, grupo: list[Item]) -> None:
        nombres = tuple(nombre_decible(self._nombre(i)) for i in [item] + grupo)
        a_quien = nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]
        con_cielo = self._n_lecturas % CIELO_EN_LECTURA_CADA == 0
        self._n_lecturas += 1
        item.nivel = nivel_para(0 if breve else item.valor).nombre
        item.cartas = tirar(0 if breve else item.valor, self.rng)     # la tirada se hace cuando llega el turno
        prompt = armar_prompt(item, self._cielo_actual(ahora), item.dato, breve=breve, con_cielo=con_cielo,
                              palabras=(PALABRAS_GRUPO if grupo else PALABRAS_CORTO) if corto else None,
                              grupo=nombres if grupo else (),
                              cierres=self._cierres_del_turno() if not breve and pesa(item.pregunta) else ())
        prompt["valor"] = item.valor                  # el generador elige el modelo según lo que se regaló
        escribiendo = asyncio.ensure_future(self.generador.generar(prompt))
        if self.voz is not None:        # mientras la IA escribe, la voz anuncia el turno: sin silencio de espera
            try:
                await self._decir(Salida(item.user, a_quien, "", "barajando", self._frase(frases.BARAJANDO).format(n=a_quien), ahora))
            except Exception:
                log.exception("[VOZ] falló el anuncio del turno")
        r = await escribiendo
        if r.get("sensible"):
            categoria = r.get("categoria") or "modelo"
            n = nombre_decible(self._nombre(item))
            aviso = ((self._frase(SALUD).format(n=n),) if "salud" in categoria.lower() else
                     (self._frase(LECTURA_PRIVADA).format(n=n),) if "embarazo" in categoria.lower() else NO_SE_LEE)
            await self._rechazar(item, categoria, "segundo filtro", ahora, aviso)
            return
        for otro in grupo:                            # en la revisión, cada quien ve la lectura que compartió
            anotar("lectura", otro.user, otro.nickname, ahora, texto=r["respuesta"], nivel=item.nivel,
                   cartas=[f"{t.posicion}: {t.carta.nombre}" for t in item.cartas])
        await self._entregar(item, "lectura", r["respuesta"], ahora, a_quien if grupo else None)

    async def _descartar_menores(self, ahora: datetime) -> bool:
        """Saca de la cola, con un aviso, a quien por su fecha de nacimiento tiene menos de 18 años."""
        menores = [i for i in self.cola.pendientes(ahora) if es_menor(i.dato, ahora.date())]
        for item in menores:
            await self._rechazar(item, "menor", "fecha de nacimiento", ahora, SOLO_ADULTOS)
        return bool(menores)

    async def _avisar(self, tipo: str, faltan: list[Item], frases: tuple, ahora: datetime) -> bool:
        if not faltan:
            return False
        nombres = ", ".join(nombre_decible(i.nickname) for i in faltan)
        uno, varios = self._frase(frases)
        texto = (uno if len(faltan) == 1 else varios).format(n=nombres, plazo=self._plazo_pregunta(faltan, ahora))
        log.info(f"[{tipo.upper()}] {nombres}")
        for i in faltan:
            anotar(tipo, i.user, i.nickname, ahora, texto=texto)
        await self._decir(Salida("", nombres, "", tipo, texto, ahora))
        return True

    def _plazo_pregunta(self, faltan: list[Item], ahora: datetime) -> str:
        """Lo que le queda para escribir su pregunta a quien regaló, dicho en palabras: "3 minutos", "150 segundos"."""
        total = self.cola.espera_pregunta.total_seconds()
        resta = total - max((ahora - i.ts).total_seconds() for i in faltan)
        seg = int(total if resta >= total - 15 else max(round(resta / 10) * 10, 10))
        if seg >= 60:                     # en minutos enteros, hacia abajo: "140 segundos" no se entiende al oído
            return "1 minuto" if seg < 120 else f"{seg // 60} minutos"
        return f"{seg} segundos"

    async def _pedir_preguntas(self, ahora: datetime) -> bool:
        faltan = self.cola.sin_pregunta(ahora)[:MAX_PEDIDOS]
        for item in faltan:
            item.pedido_pregunta = ahora
        return await self._avisar("pide_pregunta", faltan, PIDE_PREGUNTA, ahora)

    async def _pedir_fechas(self, ahora: datetime) -> bool:
        faltan = self.cola.sin_fecha(ahora)[:MAX_PEDIDOS]
        for item in faltan:
            item.pedido_fecha = ahora
        de_pareja = [i for i in faltan if i.fecha_de_pareja]      # ya dieron la de la otra persona
        for item in de_pareja:
            await self._uno("pide_fecha", item, PIDE_FECHA_PROPIA, ahora)
        return await self._avisar("pide_fecha", [i for i in faltan if not i.fecha_de_pareja], PIDE_FECHA, ahora) \
            or bool(de_pareja)

    async def _uno(self, tipo: str, item: Item, frases: tuple[str, ...], ahora: datetime) -> None:
        """Un aviso para una sola persona."""
        texto = self._frase(frases).format(n=nombre_decible(item.nickname))
        log.info(f"[{tipo.upper()}] {item.user}: {texto[:60]}")
        anotar(tipo, item.user, item.nickname, ahora, texto=texto)
        await self._decir(Salida("", item.nickname, "", tipo, texto, ahora))

    async def _avisar_gratis_agotada(self, ahora: datetime) -> bool:
        """A quien ya usó su pregunta gratis y vuelve a preguntar sin regalo: cartel en pantalla y aviso
        en voz, una sola vez por persona."""
        quienes = self.cola.agotaron_gratis(MAX_PEDIDOS)
        if not quienes:
            return False
        nombres = ", ".join(nombre_decible(n) for _, n in quienes)
        uno, varios = self._frase(GRATIS_AGOTADA)
        texto = (uno if len(quienes) == 1 else varios).format(n=nombres)
        log.info(f"[GRATIS_AGOTADA] {nombres}")
        for user, nickname in quienes:
            anotar("gratis_agotada", user, nickname, ahora, texto=texto)
        await self._decir(Salida("", nombres, "", "agotada", texto, ahora))
        return True

    async def _pedir_regalo_tema(self, ahora: datetime) -> bool:
        """A quien pregunta por un tema que solo se lee con regalo (embarazo) y no lo ha enviado, se lo
        dice de una vez, sin hacerle esperar turno ni pedirle la fecha. Su pregunta queda guardada."""
        items = self.cola.falta_regalo(ahora)[:MAX_PEDIDOS]
        for item in items:
            self.cola.apartar(item.user)
            log.info(f"[PIDE_REGALO] {item.user}: {item.pregunta[:60]!r}")
            await self._uno("pide_regalo", item, PIDE_ROSQUILLA, ahora)
        return bool(items)

    async def _pedir_en_chat(self, ahora: datetime) -> bool:
        """A quien dijo que mandó su pregunta por privado, le pide escribirla en el chat."""
        items = self.cola.por_interno(ahora)[:MAX_PEDIDOS]
        for item in items:
            item.pedido_chat = True
            await self._uno("pide_pregunta", item, ESCRIBE_EN_CHAT, ahora)
        return bool(items)

    async def _preguntar_dudas(self, ahora: datetime) -> bool:
        """Pregunta de quién es la fecha cuando el mensaje nombra a dos personas. El turno de esa
        persona espera la respuesta; los demás se siguen leyendo."""
        dudas = self.cola.con_duda(ahora)[:MAX_PEDIDOS]
        for item in dudas:
            item.pedido_duda = ahora
            await self._uno("pide_fecha", item, DUDA_FECHA, ahora)
        return bool(dudas)

    async def _completar_fechas(self, ahora: datetime) -> bool:
        """A quien respondió solo el año o solo el mes, le dice qué falta y le reinicia el plazo."""
        faltan = self.cola.con_fecha_incompleta(ahora)
        for item in faltan:
            caso, item.incompleta = item.incompleta, ""
            item.avisos_fecha.append(caso)
            item.pedido_fecha = ahora
            log.info(f"[FECHA_INCOMPLETA] {item.user}: solo dio el {'año' if caso == 'anio' else 'mes'}")
            texto = self._frase(FECHA_INCOMPLETA[caso]).format(n=nombre_decible(item.nickname))
            anotar("pide_fecha", item.user, item.nickname, ahora, texto=texto)
            await self._decir(Salida("", item.nickname, "", "pide_fecha", texto, ahora))
        return bool(faltan)

    async def _boost(self, ahora: datetime) -> bool:
        """Abre la ronda de likes cuando toca y, al terminar, le da el primer turno a quien ganó.
        Se anuncia entre lecturas; los likes cuentan por su hora, no por cuándo se anuncia."""
        b = self.boost
        if b is None:
            return False
        if b.toca_cerrar(ahora):
            g = b.cerrar(ahora)
            if g is None:
                return False
            hay_pregunta = self.cola.dar_pase(g.user, g.nickname, ahora)
            log.info(f"[BOOST] gana {g.user} con {g.likes} likes")
            texto = self._frase(BOOST_GANO if hay_pregunta else BOOST_GANO_SIN_PREGUNTA).format(n=nombre_decible(g.nickname), likes=g.likes)
            await self._decir(Salida(g.user, g.nickname, "", "boost", texto, ahora))
            return True
        if self.en_vivo(ahora) and b.toca_iniciar(ahora):
            b.iniciar(ahora)
            log.info("[BOOST] empieza la ronda")
            await self._decir(Salida("", "", "", "boost",
                                     self._frase(BOOST_INICIO).format(seg=round(b.duracion.total_seconds())), ahora))
            return True
        return False

    async def paso(self, ahora: datetime | None = None) -> bool:
        """Pide fechas que falten y procesa un ítem. Devuelve True si hizo algo."""
        if self.pausado:
            return False
        ahora = ahora or datetime.now(timezone.utc)
        pidio = await self._boost(ahora)
        pidio = await self._recordar_gratis(ahora) or pidio
        pidio = await self._descartar_menores(ahora) or pidio
        pidio = await self._pedir_preguntas(ahora) or pidio
        pidio = await self._pedir_regalo_tema(ahora) or pidio
        pidio = await self._pedir_en_chat(ahora) or pidio
        pidio = await self._preguntar_dudas(ahora) or pidio
        pidio = await self._pedir_fechas(ahora) or pidio
        pidio = await self._completar_fechas(ahora) or pidio
        pidio = await self._avisar_gratis_agotada(ahora) or pidio
        item = self.cola.tomar_siguiente(ahora)
        if item is None and (not self.en_vivo(ahora) or self.voz_lenta()):
            return pidio                      # sin live, o con la voz sin dar abasto, no se saluda ni se rellena
        if item is None:                      # nadie listo para leer: buen momento para saludar a quien llegó
            dijo = await self._dar_bienvenida(ahora) or pidio
            dijo = dijo or await self._rellenar(ahora)
            if dijo:
                self._marcar_voz(ahora)
            return dijo
        self.actual = item
        try:
            await self._procesar(item, ahora)
        except LimiteGasto as exc:
            # Sin presupuesto, todos los turnos fallarían: se pausa y el turno vuelve a la fila intacto
            self.pausado = True
            self.alerta = "Se alcanzó el límite de gasto de la API: live en pausa. Sube el límite y reanuda."
            item.estado = "pendiente"
            log.critical(f"[LIMITE] {exc}")
        except Exception as exc:
            log.exception(f"[ERROR] procesando {item.user}")
            await self._rechazar(item, "error", repr(exc), ahora, FALLO)
        finally:
            self.actual = None
        self._marcar_voz(ahora)
        return True

    def _marcar_voz(self, ahora: datetime) -> None:
        """Anota cuándo terminó de hablar (en las pruebas, la hora simulada del paso)."""
        self._ultima_voz = datetime.now(timezone.utc) if self.palabras_por_seg > 0 else ahora

    async def _rellenar(self, ahora: datetime) -> bool:
        """Si lleva un rato sin nada que decir, llena el silencio: un tip, la carta del momento o el cielo
        de hoy, por turnos. Solo corre cuando no hay nadie a quien leer, así que no atrasa ningún turno."""
        if self.relleno is None:
            return False
        if self._ultima_voz is None:
            self._ultima_voz = ahora
        if ahora - self._ultima_voz < self.relleno:
            return False
        # Casi siempre un tip; la carta del momento y el cielo salen cada cierto tiempo, no en cada silencio
        def toca(nombre: str, cada: timedelta) -> bool:
            ultimo = self._ultimo_relleno.get(nombre)
            return ultimo is None or ahora - ultimo >= cada
        evento = (await self.eventos.siguiente(ahora)) if self.eventos is not None and toca("evento", EVENTO_CADA) else None
        if evento:                                    # solo con una API de eventos configurada (astro/eventos.py)
            self._ultimo_relleno["evento"] = ahora
            self._n_relleno += 1
            log.info("[RELLENO] evento")
            await self._decir(Salida("", "", "", "relleno", evento, ahora))
            return True
        tipo = ("carta" if self._n_relleno >= 1 and toca("carta", CARTA_MOMENTO_CADA) else
                "cielo" if self._n_relleno >= 2 and toca("cielo", CIELO_CADA) else "tip")
        self._ultimo_relleno[tipo] = ahora
        self._n_relleno += 1
        log.info(f"[RELLENO] {tipo}")
        if tipo == "carta":
            await self._carta_del_momento(ahora)
        elif tipo == "cielo":
            await self._decir(Salida("", "", "", "relleno", self._texto_cielo(ahora), ahora))
        else:
            await self._decir(Salida("", "", "", "relleno", self._siguiente_tip(ahora), ahora))
        return True

    def _siguiente_tip(self, ahora: datetime) -> str:
        """Un tip de la IA si hay alguno listo; si no, uno de los fijos. Cuando quedan pocos, pide otra
        tanda en segundo plano, para que la voz nunca espere por ellos."""
        if self.tips is not None and len(self._tips_listos) <= MIN_TIPS_LISTOS and (
                self._pidiendo_tips is None or self._pidiendo_tips.done()):
            self._pidiendo_tips = asyncio.ensure_future(self._pedir_tips(ahora))
        tip = self._tips_listos.pop(0) if self._tips_listos else self._frase(frases.TIPS)
        self._tips_dichos = (self._tips_dichos + [tip])[-MAX_TIPS_RECORDADOS:]
        return tip

    async def _pedir_tips(self, ahora: datetime) -> None:
        try:
            cartas = [f"{t.carta.nombre}: {t.carta.claves}" for t in tirar(100, self.rng)]
            ejemplos = list(frases.TIPS[:6])
            nuevos = await self.tips.tanda(resumen_cielo(self._cielo_actual(ahora)), cartas,
                                           self._tips_dichos + self._tips_listos, ejemplos)
            self._tips_listos += [t for t in nuevos if t not in self._tips_dichos and t not in self._tips_listos]
        except Exception:
            log.exception("[TIPS] falló la tanda; se siguen usando los fijos")

    def _texto_cielo(self, ahora: datetime) -> str:
        c = self._cielo_actual(ahora)
        texto = self._frase(frases.CIELO).format(signo=c.posiciones["Luna"].signo, fase=c.nombre_fase.lower(),
                                                 consejo=frases.FASES.get(c.nombre_fase, "escucha tu intuición"))
        retro = [p for p in ("Mercurio", "Venus", "Marte") if c.posiciones[p].retrogrado]
        return texto + (frases.RETROGRADO.format(planeta=retro[0]) if retro else "")

    async def _carta_del_momento(self, ahora: datetime) -> None:
        """Una carta para todos los conectados. La redacta la IA; si no hay o falla, una frase fija."""
        [tirada] = tirar(1, self.rng)
        carta = tirada.carta
        texto = self._frase(frases.CARTA_MOMENTO).format(carta=carta.nombre, claves=carta.claves)
        if not isinstance(self.generador, GeneradorFalso):
            general = Item("", "todos", "", 1, [], ahora, cartas=[tirada], nivel="Carta del momento")
            try:
                prompt = armar_prompt(general, self._cielo_actual(ahora), None, para_todos=True)
                prompt["valor"] = 0                    # el modelo rápido basta
                r = await self.generador.generar(prompt)
                texto = r.get("respuesta") or texto
            except Exception:
                log.exception("[RELLENO] falló la carta del momento con IA; va la frase fija")
        await self._decir(Salida("", "", "", "carta_momento", texto, ahora, [tirada], "Carta del momento"))

    async def correr(self) -> None:
        log.info("worker iniciado")
        if self.tips is not None and self.relleno is not None:      # la primera tanda, para que ya haya al primer silencio
            self._pidiendo_tips = asyncio.ensure_future(self._pedir_tips(datetime.now(timezone.utc)))
        while True:
            if not await self.paso():
                await asyncio.sleep(self.espera_vacia)