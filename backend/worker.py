from __future__ import annotations
import asyncio, logging
from dataclasses import dataclass, field
import random
from datetime import datetime, timedelta, timezone
from typing import Protocol
from astro.cielo import Cielo, cielo
from astro.signos import es_menor
from backend.bitacora import anotar
from backend.boost import Boost
from backend.cola import Cola, Item
from backend.filtro import evaluar
from backend.frases import (AVISO_GRATIS, BENDICIONES, BIENVENIDA, Y_LOS_DEMAS, DUDA_FECHA, FECHA_INCOMPLETA, PIDE_FECHA_PROPIA, BOOST_GANO, BOOST_GANO_SIN_PREGUNTA, BOOST_INICIO, FALLO,
                            NO_SE_LEE, PIDE_FECHA, PIDE_PREGUNTA, SOLO_ADULTOS)
from backend.prompt import armar_prompt
from tarot.tirada import CartaTirada, nivel_para, tirar

log = logging.getLogger("worker")
MAX_HISTORIAL = 50
# Una lectura queda en pantalla al menos BASE + POR_CARTA por carta, y PAUSA más al terminar de decirla
MIN_LECTURA_BASE, MIN_LECTURA_POR_CARTA, PAUSA_LECTURA = 6.0, 3.0, 3.0
SALUDOS_POR_VEZ = 3    # a cuántas personas se nombra en una bienvenida
CIERRES_POR_TURNO = 4  # frases de fe que se le ofrecen a la IA en cada lectura
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
    tipo: str          # "lectura" | "mensaje_fijo" | "pide_fecha" | "pide_pregunta" | "boost" | "aviso" | "bienvenida"
    texto: str
    ts: datetime
    cartas: list[CartaTirada] = field(default_factory=list)
    nivel: str = ""
    signo: str = ""    # signo solar de quien pregunta; en pantalla va en lugar de su fecha


class Worker:
    def __init__(self, cola: Cola, generador: Generador,
                 palabras_por_seg: float = 2.5, espera_vacia: float = 1.0,
                 rng: random.Random | None = None, boost: Boost | None = None,
                 aviso_gratis: timedelta | None = None, bienvenida: timedelta | None = None):
        self.cola = cola
        self.bienvenida = bienvenida          # pausa mínima entre un saludo y el siguiente; None = no saludar
        self._llegadas: dict[str, str] = {}   # quienes entraron y aún no se saludan (user -> nombre)
        self._saludados: set[str] = set()     # a cada quien se le saluda una vez por live
        self._ultima_bienvenida: datetime | None = None
        self.aviso_gratis = aviso_gratis      # cada cuánto la voz recuerda cómo pedir la pregunta gratis
        self._proximo_aviso: datetime | None = None
        # Las frases de fe se barajan una vez y se van ofreciendo de a cuatro, sin repetir hasta dar la vuelta
        self._cierres = list(BENDICIONES)
        (rng or random).shuffle(self._cierres)
        self._cierre_n = 0
        self._usos: dict[tuple, int] = {}     # cuántas veces se ha dicho cada aviso, para rotar sus frases
        self.boost = boost             # None = sin boost de likes
        self.generador = generador
        self.palabras_por_seg = palabras_por_seg
        self.espera_vacia = espera_vacia
        self.rng = rng                 # solo para pruebas; None = azar del sistema
        self.pausado = False
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

    async def _entregar(self, item: Item, tipo: str, texto: str, ahora: datetime) -> None:
        log.info(f"[{tipo.upper()}] {item.user}: {texto[:80]}")
        await self._decir(Salida(item.user, item.nickname, item.pregunta,
                                 tipo, texto, ahora, list(item.cartas), item.nivel,
                                 item.dato.signo if item.dato else ""))
        self.cola.cerrar(item.user, "hecho")

    async def _rechazar(self, item: Item, categoria: str, motivo: str, ahora: datetime,
                        frases: tuple[str, ...] = NO_SE_LEE) -> None:
        """Salta el turno, pero diciéndolo en voz: quien regaló no se queda sin respuesta."""
        await self._decir(Salida(item.user, item.nickname, "", "mensaje_fijo", self._frase(frases), ahora))
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
        anotar(salida.tipo, salida.user, salida.nickname, salida.ts, texto=salida.texto, nivel=salida.nivel,
               pregunta=salida.pregunta, signo=salida.signo, cartas=[f"{t.posicion}: {t.carta.nombre}" for t in salida.cartas])
        if self.palabras_por_seg <= 0:
            return
        self.hablando = salida
        try:
            await asyncio.sleep(self._duracion(salida))
        finally:
            self.hablando = None

    def _duracion(self, salida: Salida) -> float:
        """Segundos que la salida queda al aire: lo que tarda en decirse y, si es una lectura,
        un mínimo para que las cartas alcancen a verse más una pausa antes del turno siguiente."""
        seg = len(salida.texto.split()) / self.palabras_por_seg
        if salida.tipo != "lectura":
            return seg
        return max(seg, MIN_LECTURA_BASE + MIN_LECTURA_POR_CARTA * len(salida.cartas)) + PAUSA_LECTURA

    def llegada(self, user: str, nickname: str) -> None:
        """Alguien entró al live. Se le saluda cuando no haya a quién leerle, y no muy seguido."""
        if self.bienvenida is None or user in self._saludados or not nickname.strip():
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

    async def _recordar_gratis(self, ahora: datetime) -> bool:
        if self.aviso_gratis is None or self.cola.max_gratis <= 0:
            return False
        if self._proximo_aviso is None:
            self._proximo_aviso = ahora + min(self.aviso_gratis, timedelta(minutes=1))   # el primero, pronto
        if ahora < self._proximo_aviso:
            return False
        self._proximo_aviso = ahora + self.aviso_gratis
        log.info("[AVISO] pregunta gratis")
        await self._decir(Salida("", "", "", "aviso", self._frase(AVISO_GRATIS), ahora))
        return True

    async def _procesar(self, item: Item, ahora: datetime) -> None:
        if es_menor(item.dato, ahora.date()):
            await self._rechazar(item, "menor", "fecha de nacimiento", ahora, SOLO_ADULTOS)
            return
        if item.pregunta:
            f = evaluar(item.pregunta)
            if f.sensible:
                if f.accion == "mensaje_fijo":
                    await self._entregar(item, "mensaje_fijo", f.mensaje, ahora)
                else:
                    await self._rechazar(item, f.categoria, f.termino, ahora)
                return

        item.nivel = nivel_para(item.valor).nombre
        item.cartas = tirar(item.valor, self.rng)     # la tirada se hace cuando llega el turno
        prompt = armar_prompt(item, self._cielo_actual(ahora), item.dato, cierres=self._cierres_del_turno())
        r = await self.generador.generar(prompt)
        if r.get("sensible"):
            await self._rechazar(item, r.get("categoria") or "modelo", "segundo filtro", ahora)
            return
        await self._entregar(item, "lectura", r["respuesta"], ahora)

    async def _descartar_menores(self, ahora: datetime) -> bool:
        """Saca de la cola, con un aviso, a quien por su fecha de nacimiento tiene menos de 18 años."""
        menores = [i for i in self.cola.pendientes(ahora) if es_menor(i.dato, ahora.date())]
        for item in menores:
            await self._rechazar(item, "menor", "fecha de nacimiento", ahora, SOLO_ADULTOS)
        return bool(menores)

    async def _avisar(self, tipo: str, faltan: list[Item], frases: tuple, ahora: datetime) -> bool:
        if not faltan:
            return False
        nombres = ", ".join(i.nickname for i in faltan)
        uno, varios = self._frase(frases)
        texto = (uno if len(faltan) == 1 else varios).format(n=nombres)
        log.info(f"[{tipo.upper()}] {nombres}")
        for i in faltan:
            anotar(tipo, i.user, i.nickname, ahora, texto=texto)
        await self._decir(Salida("", nombres, "", tipo, texto, ahora))
        return True

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
        texto = self._frase(frases).format(n=item.nickname)
        log.info(f"[{tipo.upper()}] {item.user}: {texto[:60]}")
        anotar(tipo, item.user, item.nickname, ahora, texto=texto)
        await self._decir(Salida("", item.nickname, "", tipo, texto, ahora))

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
            texto = self._frase(FECHA_INCOMPLETA[caso]).format(n=item.nickname)
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
            texto = self._frase(BOOST_GANO if hay_pregunta else BOOST_GANO_SIN_PREGUNTA).format(n=g.nickname, likes=g.likes)
            await self._decir(Salida(g.user, g.nickname, "", "boost", texto, ahora))
            return True
        if b.toca_iniciar(ahora):
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
        pidio = await self._preguntar_dudas(ahora) or pidio
        pidio = await self._pedir_fechas(ahora) or pidio
        pidio = await self._completar_fechas(ahora) or pidio
        item = self.cola.tomar_siguiente(ahora)
        if item is None:                      # nadie listo para leer: buen momento para saludar a quien llegó
            return await self._dar_bienvenida(ahora) or pidio
        self.actual = item
        try:
            await self._procesar(item, ahora)
        except Exception as exc:
            log.exception(f"[ERROR] procesando {item.user}")
            await self._rechazar(item, "error", repr(exc), ahora, FALLO)
        finally:
            self.actual = None
        return True

    async def correr(self) -> None:
        log.info("worker iniciado")
        while True:
            if not await self.paso():
                await asyncio.sleep(self.espera_vacia)