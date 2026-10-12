from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging, re
from astro.signos import (DatoSigno, FECHA_MES, SIGNO_TXT, _norm, fecha_incompleta, repartir,
                          respuesta_duda, sin_fechas)
from backend.bitacora import anotar
from backend.filtro import MINIMO, evaluar
from tarot.tirada import CartaTirada, nivel_para

# Tiempos medidos en los lives de octubre: la mitad de quienes regalan primero tardan más de un
# minuto en escribir la pregunta, y quien pregunta primero regala hasta dos minutos después.
log = logging.getLogger("cola")

VENTANA = timedelta(seconds=300)          # cuánto vale una pregunta escrita antes del regalo
ESPERA_FECHA = timedelta(seconds=90)   # tras pedir la fecha de nacimiento; luego se lee sin signo
MAX_GRATIS = 3                            # preguntas gratis que caben a la vez en la fila
VIGENCIA_PASE = timedelta(minutes=10)     # lo que dura el pase al primer turno sin usarse
ESPERA_DUDA = timedelta(seconds=45)        # para contestar "¿esa fecha es tuya o de la otra persona?"
CARTEL = timedelta(seconds=25)            # lo que dura en pantalla el cartel "agotó su pregunta gratis"
CARTEL_CADA = timedelta(seconds=45)       # a la misma persona no se le vuelve a mostrar antes de esto
ESPERA_GRATIS = timedelta(seconds=15)     # margen para que llegue el regalo antes de leerla como gratis
ESPERA_PREGUNTA = timedelta(seconds=180)  # mínimo que se espera la pregunta de quien ya regaló
NO_PREGUNTA = {"presente", "gracias", "hola", "buenas", "buenas noches",
               "ok", "si", "sí", "no", "yo", "amen", "amén"}

# Lo que sigue se evalúa sobre el texto en minúsculas y sin tildes.
CORTESIA = re.compile(r"^(ok|okay|okey|m|gracias+|muchas gracias|mil gracias|muchas bendiciones|"
                      r"bendiciones|amen|presente)\b")
SALUDO = re.compile(r"\b(hola+|ola|holi\w*|buen[oa]?s? (dias?|tardes?|noches?)|buenas|saludos|bendiciones|"
                    r"gracias+|muchas|mil|ok(ey|ay)?|amen|presente|por ?favor|porfa\w*)\b")
# "¿hay preguntitas gratuitas?": pregunta por la dinámica, no a las cartas. La voz le explica cómo pedirla.
POR_GRATIS = re.compile(r"\b(hay|tienes?|dan|das|hacen|haces|son|es|cuales?|como) .{0,25}\b(gratis|gratuit[ao]s?)\b"
                        r"|\b(gratis|gratuit[ao]s?)\b\W*$|\b(lecturas?|preguntas?|preguntitas?) (gratis|gratuit[ao]s?)\b")
# Charla sobre el live, no una pregunta para las cartas: turnos, regalos enviados, elogios
META = re.compile(
    r"^(yo )?(ya )?(te )?(envie|mande|regale)\b|\blista de orden\b"
    r"|\b(nunca|no) (sale|pasa|me leen|me lees|me leyo|me leyeron|me toca|me respond\w*|me contest\w*)\b"
    r"|\b(cuanto|cuando) me (falta|toca)\b|\bya te leen\b|\bmi turno\b|\bsigo yo\b"
    r"|\bnuev[oa] seguidora?\b|\bte sigo\b|\bya te segui\b"
    r"|\b(buenas|lindas|bonitas|bacanas) respuestas\b|\brespuestas (bacanas|buenas|lindas|bonitas)\b"
    r"|\bdespedida\b"
    # comentarios sobre el propio live, vistos en el log del 11 de octubre
    r"|\bmi pregunta (ya |te |no |si |me )*(salio|sale|llego|paso|la leiste|la leyo|la viste)\b|\bla lista\b"
    r"|\b(yo falto|falto yo|falta la mia|faltan? (yo|la mia)|y la mia)\b|\bvoy a enviar(te|le)?\b"
    r"|\bal interno\b|\bnuestra comunidad acaba de\b|^de acuerdo\b|^(ya )?la ultima\b|^bonit[oa] (dia|tarde|noche|domingo|semana)\b"
    # problemas técnicos del live: "hola no te escucho", "se fue el audio"
    r"|\bno (te |se |la |los )?(escucho|escucha|escuchamos|oigo|oye|veo|ve)\b|\b(sin|no hay|se fue el) (audio|sonido)\b"
    r"|\bse (cayo|congelo|pego|trabo) (el live|la imagen|el video)\b")
# "te envié la pregunta al interno": la mandó por mensaje privado, que el sistema no puede leer
INTERNO = re.compile(r"\b(al|por|por el|en el|x) (interno|privado|inbox|dm|md)\b|\bmensaje (interno|privado)\b")
REACCION = re.compile(r"^(si+|no|exacto|exactamente|asi es|correcto|totalmente|claro|cierto|tal cual|es verdad|verdad)\b")
# Señales de que el texto pregunta algo: interrogativos, "quiero saber", futuros, "me ama"…
SENAL = re.compile(
    r"\?|¿|\b(que|quien|quienes|como|cuando|cuanto|cuanta|donde|cual|por ?que|por ?q|xq|pq|q)\b"
    r"|\b(quiero|quisiera|queria|necesito|deseo|puedo) saber\b|\bsaber si\b"
    r"|\bm[e]? (ama|quiere|piensa|extrana|busca|engana|conviene|va|ira)\b"
    r"|\b(volver|vuelv|regres|sient|sentimientos|futuro|leeme|lee me|lectura)\w*"
    r"|\b(voy|va|vamos|van) a\b|\b(debo|deberia|podre|tendre|tendra|sera|estara|habra)\b"
    r"|\b\w{3,}(are|ere|ire|ara|era|ira|aran|eran|iran|aremos|eremos|iremos)\b")


def es_pregunta(texto: str) -> bool:
    """Descarta lo que claramente no es una pregunta: saludos, gracias, respuestas a otra
    persona (@alguien) y charla sobre el live. Lo demás se acepta: quien ya regaló puede
    preguntar afirmando ("mi esposo me engaña")."""
    t = re.sub(r"^[^a-z0-9¿@]+", "", _norm(texto.strip()))     # sin emojis ni signos al inicio
    if len(t) < 8 or t in NO_PREGUNTA or t.startswith("@"):
        return False
    if CORTESIA.match(t) and "?" not in t and len(t.split()) <= 6:
        return False    # "ok gracias por su respuesta", "gracias por tus palabras"
    if POR_GRATIS.search(t) and len(t.split()) <= 7:
        return False    # "hay preguntitas gratuitas?", "mi pregunta gratis nunca sale": hablan de la dinámica
    if META.search(t) or INTERNO.search(t):
        return False    # "cuál es la pregunta gratis?", "yo mandé venadito", "ya te la mandé por privado"
    if REACCION.match(t) and not SENAL.search(t):
        return False    # le contesta a la lectura: "sí, fue horrible el pasado", "no, yo tampoco quiero algo serio"
    if len(re.findall(r"[a-zñ]{2,}", SALUDO.sub(" ", t))) < 2:
        return False    # "buenos días", "holaa bendiciones"
    return len(re.findall(r"[a-zñ]", t)) >= 6


def parece_pregunta(texto: str) -> bool:
    """Más estricto que es_pregunta: el texto trae una señal de pregunta. Es lo que se exige
    para el turno gratis y para distinguir "nombre + fecha" de "nombre + fecha + pregunta"."""
    return es_pregunta(texto) and bool(SENAL.search(_norm(texto)))


# Con esto no hay duda de que pregunta; lo demás que pase es_pregunta es dudoso y lo puede decidir la IA
SEGURA = re.compile(r"\?|¿|\b(quiero|quisiera|queria|necesito|deseo) saber\b|\bsaber si\b"
                    r"|\b(me )?(puedes|podrias|podria|puede) (decir|leer)\b|\bleeme\b")


def trae_pregunta(texto: str) -> bool:
    """Un comentario con fecha o signo que además pregunta algo: "soy Ana 05/05/90 y en el
    trabajo, ¿me ascenderán?". "Juan Pablo Yepes 16/09/2004" solo trae el dato. Sin señal de
    pregunta, cuenta si es más largo que un nombre completo ("…mi hija tiene los documentos de la casa")."""
    t = sin_fechas(_norm(texto))
    for patron in (FECHA_MES, SIGNO_TXT):
        t = patron.sub(" ", t)
    return parece_pregunta(t) or (es_pregunta(t) and len(re.findall(r"[a-zñ]{2,}", t)) >= 6)


def _clave(texto: str) -> str:
    """La pregunta reducida a sus letras, para reconocerla cuando la repiten."""
    return re.sub(r"[^a-zñ0-9]", "", _norm(texto))


@dataclass
class Item:
    user: str
    nickname: str
    pregunta: str               # "" = aún no pregunta; si llega su turno así, es lectura general
    valor: int
    regalos: list[str]
    ts: datetime                # cuándo entró a la fila (al llegar el regalo)
    estado: str = "pendiente"   # pendiente | leyendo | hecho | saltado
    extras: list[str] = field(default_factory=list)   # preguntas posteriores, máx 3
    dato: DatoSigno | None = None           # signo / fecha de nacimiento de quien pregunta
    pedido_fecha: datetime | None = None    # cuándo se le pidió la fecha en voz
    pedido_pregunta: datetime | None = None # cuándo se le pidió la pregunta en voz
    nivel: str = ""                         # nombre del nivel con el que se leyó
    pareja: DatoSigno | None = None         # signo de la otra persona, si lo dieron (nunca su fecha)
    cartas: list[CartaTirada] = field(default_factory=list)   # la tirada; se saca cuando llega su turno
    dudosa: DatoSigno | None = None         # fecha del mensaje que no se sabe si es suya o de la otra persona
    pedido_duda: datetime | None = None     # cuándo se le preguntó de quién es
    fecha_de_pareja: bool = False           # la fecha que dio era de la otra persona; falta la suya
    dijo_interno: bool = False              # dijo que mandó la pregunta por privado; falta pedirle que la escriba aquí
    pedido_chat: bool = False               # ya se le pidió escribirla en el chat
    incompleta: str = ""                    # dio solo el "anio" o solo el "mes"; falta avisarle qué falta
    avisos_fecha: list[str] = field(default_factory=list)   # lo que ya se le dijo que faltaba
    prioridad: bool = False                 # pase al primer turno (ganó el boost de likes)


@dataclass
class _Pendiente:
    nickname: str
    ts: datetime
    texto: str = ""
    valor: int = 0
    regalos: list[str] = field(default_factory=list)


class Cola:
    def __init__(self, ventana: timedelta = VENTANA, espera_fecha: timedelta | None = ESPERA_FECHA,
                 espera_pregunta: timedelta = ESPERA_PREGUNTA, max_gratis: int = MAX_GRATIS,
                 espera_gratis: timedelta = ESPERA_GRATIS):
        self.ventana = ventana
        self.espera_gratis = espera_gratis
        self.max_gratis = max_gratis                  # 0 = sin preguntas gratis
        # Quién ya usó su pregunta gratis. PROVISIONAL: vive en memoria y se reinicia con el
        # backend (o sea, por live); pasa a la base de datos junto con el historial por persona.
        self._gratis_usada: set[str] = set()
        self._gratis_sin_fecha: set[str] = set()      # se les pidió la fecha y no la dieron
        self._ultima: dict[str, tuple[datetime, str]] = {}   # última pregunta de cada quien, aunque ya se leyera gratis
        # Regaló, no alcanzó a preguntar y se le leyó un mensaje general: si pregunta enseguida, se le debe la lectura
        self._deben_pregunta: dict[str, tuple[datetime, int, list[str]]] = {}
        self._leidas: dict[str, set[str]] = {}        # preguntas que ya se le respondieron a cada quien
        self._repitio: set[str] = set()               # su último mensaje fue una pregunta ya respondida
        # Lo que dijo la IA de los mensajes dudosos (True = consulta para las cartas, False = comentario)
        self._veredictos: OrderedDict[str, bool] = OrderedDict()
        # Ya usaron su gratis y vuelven a preguntar sin regalo: se les avisa una vez (cartel y voz)
        self._agotada_por_avisar: dict[str, str] = {}
        self._agotada_avisada: set[str] = set()
        self._cartel: dict[str, tuple[datetime, str]] = {}    # user -> (cuándo insistió, nombre) para el cartel
        self.preguntaron_por_gratis = False           # alguien preguntó si hay preguntas gratis
        self._nombres: set[str] = set()               # nombres de cuenta vistos en el chat, para reconocer menciones
        self._pases: dict[str, datetime] = {}         # pase al primer turno todavía sin usar
        self.espera_pregunta = espera_pregunta
        self.espera_fecha = espera_fecha              # None = no exigir fecha de nacimiento
        self._datos: dict[str, DatoSigno] = {}        # último dato de nacimiento que dio cada usuario
        self._preguntas: dict[str, _Pendiente] = {}   # pregunta esperando regalo
        self._regalos: dict[str, _Pendiente] = {}     # regalo de alguien a quien se le está leyendo
        self._items: dict[str, Item] = {}             # un ítem abierto por usuario
        self.historial: list[Item] = []
        self._msg_vistos: OrderedDict[int, None] = OrderedDict()

    # ---------- entrada ----------
    def dudoso(self, texto: str) -> bool:
        """Mensajes que las reglas no saben si son consulta o comentario: sin signo de interrogación ni
        "quiero saber", pero tampoco charla evidente. Son los que se le pasan a la IA."""
        limpio = self.sin_mencion(texto)
        if limpio is None or not es_pregunta(limpio) or SEGURA.search(_norm(limpio)):
            return False
        return _clave(limpio) not in self._veredictos

    def ya_le_leyeron(self, user: str) -> bool:
        return bool(self._leidas.get(user))

    def _veredicto(self, texto: str) -> bool | None:
        return self._veredictos.get(_clave(texto))

    def _es_pregunta(self, texto: str) -> bool:
        # Un tema delicado se atiende siempre, diga lo que diga la IA: es lo que dispara el mensaje de cuidado
        return es_pregunta(texto) and (self._veredicto(texto) is not False or evaluar(texto).sensible)

    def _clara(self, texto: str) -> bool:
        """Pregunta clara: lo dice la IA si opinó; si no, las señales de siempre."""
        v = self._veredicto(texto)
        return parece_pregunta(texto) if v is None else v

    def _trae(self, texto: str) -> bool:
        v = self._veredicto(texto)
        return trae_pregunta(texto) if v is None else v

    def procesar(self, ev: dict, veredicto: bool | None = None) -> None:
        msg_id = ev.get("msg_id") or 0
        if msg_id:
            if msg_id in self._msg_vistos:
                return
            self._msg_vistos[msg_id] = None
            if len(self._msg_vistos) > 20000:
                self._msg_vistos.popitem(last=False)
        ts = datetime.fromisoformat(ev["ts"])
        if ev["tipo"] in ("comment", "gift") and len(nombre := _norm(ev["nickname"]).strip()) >= 3:
            self._nombres.add(nombre)
        if ev["tipo"] == "comment":
            texto = self.sin_mencion(ev["texto"])
            if texto is None:
                return                               # le respondía a otra persona del chat
            ev = {**ev, "texto": texto}
            if POR_GRATIS.search(_norm(texto)) and len(texto.split()) <= 7:
                self.preguntaron_por_gratis = True
            if veredicto is not None:
                self._veredictos[_clave(texto)] = veredicto
                if len(self._veredictos) > 5000:
                    self._veredictos.popitem(last=False)
            item = self._items.get(ev["user"])
            if (item and item.estado == "pendiente" and not item.pregunta and not item.pedido_chat
                    and INTERNO.search(_norm(texto))):
                item.dijo_interno = True             # la voz le pedirá que la escriba en el chat
        if ev["tipo"] == "comment" and self._on_dato(ev["user"], ev["texto"], ev["nickname"]):
            return
        if ev["tipo"] == "comment" and self._es_pregunta(ev["texto"]):
            self._on_pregunta(ev["user"], ev["nickname"], ev["texto"], ts)
        elif ev["tipo"] == "gift":
            self._on_regalo(ev["user"], ev["nickname"], ev["regalo"], ev["valor"], ts)

    def sin_mencion(self, texto: str) -> str | None:
        """Hay quien escribe su pregunta empezando con "@" ("@magaly 29/4/85 y Saúl…"). Eso no es
        una mención: se le quita la arroba. None solo si de verdad le habla a alguien del chat
        ("@Lalita Vergara eres muy linda")."""
        t = texto.strip()
        if "@" not in t:
            return texto
        if t.startswith("@") and sin_fechas(t) == " ".join(t.split()):
            resto = _norm(t.lstrip("@ "))
            if any(resto.startswith(n) for n in self._nombres):
                return None
        return " ".join(re.sub(r"@?[A-Za-z][\w.+-]*@[\w-]+(\.\w+)+|@", " ", t).split())      # también fuera correos pegados

    def _on_dato(self, user, texto, nickname="") -> bool:
        """Guarda la fecha o el signo si el comentario lo trae. True si el comentario solo traía
        el dato ("Juan Pablo 16/09/2004") y no hay que tratarlo además como pregunta; si junto
        al dato viene una pregunta, sigue su camino."""
        item = self._items.get(user)
        abierto = item is not None and item.estado == "pendiente"
        if abierto and item.dudosa and item.pedido_duda and (resp := respuesta_duda(texto)):
            self._resolver_duda(item, resp == "propia")
            return True                              # "mía" / "de él": era la respuesta, no una pregunta
        r = self._reparto(user, texto, nickname)
        dato, pareja = r.propio, r.pareja
        if pareja and abierto and item.pareja is None:
            item.pareja = pareja
            item.fecha_de_pareja = item.fecha_de_pareja or r.de_pareja
        if r.dudosa:
            if abierto and item.dato is None and item.dudosa is None and item.pedido_duda is None:
                item.dudosa = r.dudosa               # la voz le preguntará de quién es
            return not self._trae(texto)
        if dato is None:
            parcial = fecha_incompleta(texto)
            if (parcial and item and item.estado == "pendiente" and item.dato is None
                    and parcial not in item.avisos_fecha):
                item.incompleta = parcial        # la voz le dirá qué le falta, una vez por cada caso
            return False
        self._datos[user] = dato
        if item and item.estado == "pendiente" and item.dato is None:
            item.dato = dato
        return not self._trae(texto)

    def _on_pregunta(self, user, nickname, texto, ts):
        item = self._items.get(user)
        self._repitio.discard(user)
        esperando = item is not None and item.estado == "pendiente" and not item.pregunta
        if item is None and user in self._gratis_usada and user not in self._pases and self._clara(texto):
            # Ya usó su gratis y vuelve a preguntar sin regalo: cartel cada vez que insiste (con una pausa
            # por persona) y aviso en voz una sola vez
            previo = self._cartel.get(user)
            if previo is None or ts - previo[0] >= CARTEL_CADA:
                self._cartel[user] = (ts, nickname)
            if user not in self._agotada_avisada:
                self._agotada_por_avisar[user] = nickname
        if _clave(texto) in self._leidas.get(user, ()) and not esperando and user not in self._pases:
            # Ya se le respondió y la vuelve a escribir (suele pasar mientras espera a la anfitriona):
            # no se lee otra vez gratis ni se pega a un regalo futuro. Sí vale si regaló y falta su pregunta.
            self._repitio.add(user)
            return
        self._ultima[user] = (ts, texto)
        if item and item.estado == "pendiente":
            if not item.pregunta:
                item.pregunta = texto        # ya estaba en la fila por su regalo y llegó la pregunta
            elif not self._clara(item.pregunta) and self._clara(texto):
                item.pregunta = texto        # lo anterior era charla ("no entendía jajaja"); esta sí es la pregunta
            elif texto != item.pregunta and texto not in item.extras:
                item.extras = (item.extras + [texto])[-3:]
            return
        self._preguntas[user] = _Pendiente(nickname, ts, texto=texto)
        if item is None and user in self._pases:      # tenía el pase y por fin escribió su pregunta
            self._crear(user, nickname, 0, [], ts)

    def _on_regalo(self, user, nickname, regalo, valor, ts):
        item = self._items.get(user)
        if item and item.estado == "pendiente":
            item.valor += valor
            item.regalos.append(regalo)
            return
        if item:                             # se le está leyendo: el regalo abre un turno nuevo al cerrar
            r = self._regalos.setdefault(user, _Pendiente(nickname, ts))
            r.valor += valor
            r.regalos.append(regalo)
            return
        self._crear(user, nickname, valor, [regalo], ts)

    def _crear(self, user, nickname, valor, regalos, ts):
        """El regalo entra a la fila de inmediato, con la pregunta reciente si la hay."""
        p = self._preguntas.pop(user, None)
        texto = p.texto if p and ts - p.ts <= self.ventana else ""
        if not texto and valor > 0:
            # Preguntó, se le leyó gratis y después regaló: el regalo es para esa misma pregunta
            u = self._ultima.get(user)
            texto = u[1] if u and ts - u[0] <= self.ventana else ""
        if valor > 0 and texto and not self._sirve_de_pregunta(texto):
            texto = ""       # "de acuerdo totalmente", "yo falto": charla anterior al regalo, no su pregunta
        pase = self._pases.pop(user, None)
        r = self._reparto(user, texto, nickname)
        self._items[user] = Item(user, nickname, texto, valor, list(regalos), ts,
                                 dato=self._datos.get(user), pareja=r.pareja, dudosa=r.dudosa,
                                 fecha_de_pareja=r.de_pareja,
                                 prioridad=pase is not None and ts - pase <= VIGENCIA_PASE)

    def _sirve_de_pregunta(self, texto: str) -> bool:
        """Lo escrito ANTES de regalar se toma como la pregunta si tiene señal de pregunta, si es una
        frase larga ("mi papá le es infiel a mi mamá") o si toca un tema delicado, que debe atenderse."""
        if (v := self._veredicto(texto)) is not None:
            return v or evaluar(texto).sensible
        return (parece_pregunta(texto) or len(re.findall(r"[a-zñ]{2,}", _norm(texto))) >= 6
                or evaluar(texto).sensible)

    def _reparto(self, user, texto, nickname):
        """De quién es cada fecha del mensaje. Si ya se conoce la de quien escribe, una fecha
        dudosa solo puede ser de la otra persona."""
        r = repartir(texto, nickname, user)
        mia = self._datos.get(user)
        if r.dudosa and mia:
            d = r.dudosa
            r.pareja, r.dudosa = DatoSigno(d.signo, None, d.en_cuspide, "fecha"), None
        elif (mia and mia.fecha and r.propio and r.propio.fecha and r.propio.fecha != mia.fecha
                and not re.search(r"\b(soy|mi fecha|naci)\b", _norm(texto))):
            # Ya dio su fecha y ahora escribe otra distinta ("Miguel Villa 11/11/03 tiene otra relación?"):
            # es de la persona por la que pregunta; la suya no se cambia.
            d = r.propio
            r.propio, r.pareja = None, r.pareja or DatoSigno(d.signo, None, d.en_cuspide, "fecha")
        return r

    def _resolver_duda(self, item: Item, es_suya: bool) -> None:
        d, item.dudosa = item.dudosa, None
        if es_suya:
            item.dato = self._datos[item.user] = d
        else:
            item.pareja = DatoSigno(d.signo, None, d.en_cuspide, "fecha")    # de la pareja solo se guarda el signo
            item.fecha_de_pareja = True

    def dar_pase(self, user: str, nickname: str, ahora: datetime) -> bool:
        """Pase al primer turno. Si ya está en la fila o tiene una pregunta esperando, sube de una;
        si no, el pase queda guardado para su próxima pregunta. True si ya hay pregunta que leer."""
        self._vencer(ahora)
        item = self._items.get(user)
        if item and item.estado == "pendiente":
            item.prioridad = True
            return bool(item.pregunta)
        self._pases[user] = ahora
        if item is None and user in self._preguntas:
            self._crear(user, nickname, 0, [], self._preguntas[user].ts)
            return True
        return False

    # ---------- mantenimiento ----------
    def _vencer(self, ahora: datetime) -> None:
        for user, r in list(self._regalos.items()):
            if user not in self._items:
                del self._regalos[user]
                self._crear(user, r.nickname, r.valor, r.regalos, r.ts)
        for user, p in list(self._preguntas.items()):
            if ahora - p.ts > self.ventana:
                del self._preguntas[user]
        for user, (leido, valor, regalos) in list(self._deben_pregunta.items()):
            p = self._preguntas.get(user)
            if ahora - leido > self.ventana:
                del self._deben_pregunta[user]
            elif p and user not in self._items and self._clara(p.texto):
                del self._deben_pregunta[user]       # su pregunta llegó tarde: se lee con el nivel de su regalo
                log.info(f"[PREGUNTA_TARDIA] {user}: se le lee con su regalo ({p.texto[:60]!r})")
                anotar("pregunta_tardia", user, p.nickname, ahora, texto="Su pregunta llegó después del mensaje general: se lee con su regalo")
                self._crear(user, p.nickname, valor, regalos, p.ts)
        self._sacar_gratis_sin_fecha(ahora)
        self._subir_gratis()

    def _sacar_gratis_sin_fecha(self, ahora: datetime) -> None:
        """Sin fecha no hay lectura gratis: pasado el plazo sale de la fila sin gastar su turno,
        y solo vuelve a entrar cuando ya se conoce su fecha."""
        for user, item in list(self._items.items()):
            if (item.valor == 0 and item.estado == "pendiente" and self.falta(item) == ["fecha"]
                    and item.pedido_fecha is not None and ahora - item.pedido_fecha > self.espera_fecha):
                self._gratis_sin_fecha.add(user)
                log.info(f"[SIN_FECHA] {user} sale de la fila: no dio su fecha de nacimiento ({item.pregunta[:60]!r})")
                anotar("sin_fecha", user, item.nickname, ahora, texto="Salió de la fila: no dio su fecha de nacimiento")
                self.cerrar(user, "saltado")

    def _subir_gratis(self) -> None:
        """Pasa a la fila, con valor 0 (nivel "Sí o no"), las preguntas sin regalo más antiguas de
        quienes no han usado su turno gratis. Quedan al final: cualquier regalo listo va antes."""
        cupo = self.max_gratis - sum(1 for i in self._items.values()
                                    if i.valor == 0 and i.estado == "pendiente" and not i.prioridad)
        libres = sorted((p.ts, user) for user, p in self._preguntas.items()
                        if user not in self._gratis_usada and user not in self._items
                        and self._clara(p.texto)          # la gratis exige una pregunta clara
                        and (user not in self._gratis_sin_fecha or user in self._datos))
        for ts, user in libres[:max(cupo, 0)]:
            self._crear(user, self._preguntas[user].nickname, 0, [], ts)

    # ---------- salida ----------
    def pendientes(self, ahora: datetime) -> list[Item]:
        self._vencer(ahora)
        abiertos = [i for i in self._items.values() if i.estado == "pendiente"]
        return sorted(abiertos, key=lambda i: (not i.prioridad, -i.valor, i.ts))

    def situacion(self, user: str) -> str:
        """En una frase, en qué quedó la persona después de su último mensaje (para la revisión)."""
        item = self._items.get(user)
        if item:
            if item.estado == "leyendo":
                return "Se le está leyendo"
            falta = self.falta(item)
            pendiente = (" · falta su pregunta" if "pregunta" in falta else
                         " · falta su fecha de nacimiento" if "fecha" in falta else
                         " · no se sabe si la fecha es suya o de la otra persona" if item.dudosa else "")
            return f"En la fila ({'ganó el boost' if item.prioridad else nivel_para(item.valor).nombre}){pendiente}"
        p = self._preguntas.get(user)
        if p is None:
            return "Esa pregunta ya se le respondió: se lee de nuevo solo si regala" if user in self._repitio else ""
        if user in self._gratis_usada:
            return "Ya usó su pregunta gratis: se lee si regala"
        if user in self._gratis_sin_fecha and user not in self._datos:
            return "No dio su fecha: vuelve a entrar cuando la escriba"
        if not self._clara(p.texto):
            return "No tiene forma clara de pregunta: se lee si regala"
        return "Esperando cupo para la pregunta gratis"

    def falta(self, item: Item) -> list[str]:
        """Qué le falta escribir a la persona: "pregunta" o "fecha". La fecha solo se exige
        cuando hay pregunta; el mensaje sin pregunta no la necesita."""
        if not item.pregunta:
            return ["pregunta"]
        if item.dato is None and item.dudosa is None and self.espera_fecha is not None:
            return ["fecha"]
        return []

    def _lista(self, item: Item, ahora: datetime) -> bool:
        falta = self.falta(item)
        if item.valor == 0 and not item.prioridad and ahora - item.ts < self.espera_gratis:
            return False                     # si regala en ese margen, su pregunta sube al nivel del regalo
        if "pregunta" in falta:              # tiene hasta su turno, y como mínimo espera_pregunta
            return ahora - item.ts >= self.espera_pregunta
        if item.dudosa and item.pregunta:    # espera la respuesta; si no llega, se lee igual y la IA lo maneja
            return item.pedido_duda is not None and ahora - item.pedido_duda > ESPERA_DUDA
        if "fecha" in falta:                 # con regalo se lee sin signo al vencer el plazo; gratis, no
            return item.valor > 0 and item.pedido_fecha is not None and ahora - item.pedido_fecha > self.espera_fecha
        return True

    def sin_fecha(self, ahora: datetime) -> list[Item]:
        """Ítems con pregunta a los que todavía no se les ha pedido la fecha de nacimiento."""
        return [i for i in self.pendientes(ahora) if self.falta(i) == ["fecha"] and i.pedido_fecha is None]

    def cartel(self, ahora: datetime) -> str | None:
        """Nombres para el cartel "agotó su pregunta gratis": quienes insistieron hace poco (hasta 3)."""
        vigentes = sorted((ts, n) for ts, n in self._cartel.values() if timedelta(0) <= ahora - ts < CARTEL)
        return ", ".join(n for _, n in vigentes[-3:]) or None

    def agotaron_gratis(self, maximo: int) -> list[tuple[str, str]]:
        """(usuario, nombre) de quienes ya usaron su pregunta gratis y volvieron a preguntar sin regalo.
        Cada persona sale una sola vez en todo el live."""
        elegidos = [(u, n) for u, n in self._agotada_por_avisar.items() if u not in self._items][:maximo]
        for user, _ in elegidos:
            del self._agotada_por_avisar[user]
            self._agotada_avisada.add(user)
        return elegidos

    def falta_regalo(self, ahora: datetime) -> list[Item]:
        """Ítems cuya pregunta es de un tema que solo se lee con regalo y aún no alcanzan el mínimo."""
        return [i for i in self.pendientes(ahora)
                if i.pregunta and i.valor < MINIMO.get(evaluar(i.pregunta).categoria, 0)]

    def apartar(self, user: str) -> None:
        """Saca el turno de la fila sin gastar nada: su pregunta queda guardada por si envía el regalo."""
        item = self._items.get(user)
        if item and item.pregunta:
            self._ultima[user] = (item.ts, item.pregunta)
        self.cerrar(user, "saltado")
        self._gratis_usada.discard(user)

    def por_interno(self, ahora: datetime) -> list[Item]:
        """Regalaron y dijeron que mandaron la pregunta por privado; aún no se les pide escribirla en el chat."""
        return [i for i in self.pendientes(ahora) if i.dijo_interno and not i.pedido_chat and not i.pregunta]

    def con_duda(self, ahora: datetime) -> list[Item]:
        """Ítems con una fecha que no se sabe de quién es y a los que aún no se les ha preguntado."""
        return [i for i in self.pendientes(ahora) if i.dudosa and i.pregunta and i.pedido_duda is None]

    def con_fecha_incompleta(self, ahora: datetime) -> list[Item]:
        """Ítems cuya persona respondió la fecha a medias y todavía no sabe qué le falta."""
        return [i for i in self.pendientes(ahora) if i.incompleta and i.dato is None]

    def sin_pregunta(self, ahora: datetime) -> list[Item]:
        """Ítems que regalaron sin preguntar y a los que todavía no se les ha pedido la pregunta."""
        return [i for i in self.pendientes(ahora) if not i.pregunta and i.pedido_pregunta is None]

    def tomar_siguiente(self, ahora: datetime) -> Item | None:
        for item in self.pendientes(ahora):
            if self._lista(item, ahora):
                item.estado = "leyendo"
                if item.valor == 0 and not item.prioridad:      # el pase del boost no gasta la gratis
                    self._gratis_usada.add(item.user)
                elif item.valor > 0 and not item.pregunta:
                    self._deben_pregunta[item.user] = (ahora, item.valor, list(item.regalos))
                return item
        return None

    def cerrar(self, user: str, estado: str = "hecho") -> None:
        item = self._items.pop(user, None)
        if (item and estado == "hecho" and item.valor > 0
                and self._ultima.get(user, (None, None))[1] == item.pregunta):
            del self._ultima[user]           # ya se leyó con regalo: otro regalo no la repite
        if item:
            item.estado = estado
            self.historial.append(item)
            if estado == "hecho" and item.pregunta:
                self._leidas.setdefault(user, set()).add(_clave(item.pregunta))