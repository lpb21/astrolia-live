import functools, os, logging, asyncio
from datetime import datetime
from pathlib import Path
import dataclasses
import httpx
from dotenv import load_dotenv
from TikTokLive import TikTokLiveClient
from TikTokLive.client.web.web_settings import WebDefaults
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent, GiftEvent, FollowEvent, LikeEvent, JoinEvent
from TikTokLive.client.errors import UserOfflineError
from ingest.normalize import LiveEvent, limpiar
from collections import OrderedDict

_visto = set()

def dump(nombre, obj):
    if nombre in _visto:
        return
    _visto.add(nombre)
    try:
        campos = {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}
    except TypeError:
        campos = {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    log.info(f"[DUMP {nombre}] " + ", ".join(f"{k}={v!r}"[:80] for k, v in campos.items()))

load_dotenv()
Path("logs").mkdir(exist_ok=True)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

# Un par de archivos por arranque, con fecha, hora y cuenta: cada live queda en los suyos
_SESION = f"logs/{datetime.now():%Y-%m-%d_%H-%M-%S}_{os.getenv('TIKTOK_USER') or 'live'}"
_archivo = logging.FileHandler(f"{_SESION}_ingest.log", encoding="utf-8")
_archivo.setFormatter(_fmt)
_consola = logging.StreamHandler()
_consola.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_consola, _archivo])
log = logging.getLogger("ingest")
logging.getLogger("httpx").setLevel(logging.WARNING)

eventos_log = logging.getLogger("eventos")
eventos_log.propagate = False          # no va a consola ni a ingest.log
_ev = logging.FileHandler(f"{_SESION}_eventos.jsonl", encoding="utf-8")
_ev.setFormatter(logging.Formatter("%(message)s"))
eventos_log.addHandler(_ev)
eventos_log.setLevel(logging.INFO)


_vistos: OrderedDict = OrderedDict()

def es_duplicado(msg_id: int) -> bool:
    if not msg_id:
        return False
    if msg_id in _vistos:
        return True
    _vistos[msg_id] = None
    if len(_vistos) > 5000:
        _vistos.popitem(last=False)
    return False

if key := os.getenv("EULER_API_KEY"):
    WebDefaults.tiktok_sign_api_key = key

client = TikTokLiveClient(unique_id=os.getenv("TIKTOK_USER"))

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
_http = httpx.AsyncClient(timeout=3)
_tareas: set = set()   # referencia fuerte para que el GC no mate las tareas

from collections import deque
_buffer: deque = deque(maxlen=1000)   # eventos que no llegaron al backend

async def _post(ev: LiveEvent):
    r = await _http.post(f"{BACKEND_URL}/eventos", content=ev.to_json(),
                         headers={"Content-Type": "application/json"})
    r.raise_for_status()

async def _enviar(ev: LiveEvent):
    try:
        await _post(ev)
    except httpx.HTTPError as exc:
        log.error(f"[BACKEND] no se pudo enviar {ev.msg_id}: {exc!r} (guardado para reintento)")
        _buffer.append(ev)

async def _reenviar():
    while True:
        await asyncio.sleep(5)
        while _buffer:
            ev = _buffer[0]
            try:
                await _post(ev)
            except httpx.HTTPError:
                break                      # backend sigue caído; reintenta en 5 s
            _buffer.popleft()
            log.info(f"[BACKEND] reenviado {ev.msg_id}")

def emit(ev: LiveEvent):
    if es_duplicado(ev.msg_id):
        log.debug(f"[DUP] {ev.msg_id} {ev.user}")
        return
    eventos_log.info(ev.to_json())
    t = asyncio.get_running_loop().create_task(_enviar(ev))
    _tareas.add(t)
    t.add_done_callback(_tareas.discard)

def avisar_conexion(conectado: bool):
    """Le cuenta al backend si hay live: sin live, la voz deja de rellenar el silencio."""
    ev = LiveEvent("conexion", "", "", texto="conectado" if conectado else "desconectado")
    t = asyncio.get_running_loop().create_task(_enviar(ev))
    _tareas.add(t)
    t.add_done_callback(_tareas.discard)

@client.on(ConnectEvent)
async def on_connect(e):
    log.info(f"Conectado a @{e.unique_id}")
    avisar_conexion(True)

@client.on(DisconnectEvent)
async def on_disconnect(e): log.warning("Desconectado")

def con_usuario(manejador):
    """TikTok a veces manda eventos sin datos de quién los hizo (sobre todo entradas al live). Esos se
    descartan aquí; sin esto cada uno deja un error largo en la consola."""
    @functools.wraps(manejador)
    async def envoltura(e):
        usuario = getattr(e, "user", None)
        if usuario is None or not getattr(usuario, "display_id", ""):
            return
        await manejador(e)
    return envoltura


@client.on(CommentEvent)
@con_usuario
async def on_comment(e: CommentEvent):
    identidad = getattr(e, "user_identity", None)
    if e.user.display_id == client.unique_id or (identidad is not None and identidad.is_anchor):
        return                      # lo que escribe la propia cuenta del live no es una consulta
    emit(LiveEvent("comment", e.user.display_id, e.user.nickname,
                   texto=limpiar(e.content), msg_id=e.common.msg_id,
                   seguidor=bool(identidad.is_follower_of_anchor) if identidad is not None else None))

@client.on(GiftEvent)
@con_usuario
async def on_gift(e: GiftEvent):
    log.debug(f"[RACHA] {e.user.display_id} {e.gift.name} x{e.repeat_count} "
              f"streakable={e.gift.streakable} streaking={e.streaking}")
    if e.gift.streakable and e.streaking:
        return
    emit(LiveEvent("gift", e.user.display_id, e.user.nickname,
                   regalo=e.gift.name, valor=e.gift.diamond_count * e.repeat_count, msg_id=e.common.msg_id))

@client.on(LikeEvent)
@con_usuario
async def on_like(e: LikeEvent):
    emit(LiveEvent("like", e.user.display_id, e.user.nickname, valor=e.count, msg_id=e.common.msg_id))

@client.on(JoinEvent)
@con_usuario
async def on_join(e: JoinEvent):
    emit(LiveEvent("join", e.user.display_id, e.user.nickname, msg_id=e.common.msg_id))

@client.on(FollowEvent)
@con_usuario
async def on_follow(e: FollowEvent):
    emit(LiveEvent("follow", e.user.display_id, e.user.nickname, msg_id=e.common.msg_id))
    #pass

async def main():
    asyncio.create_task(_reenviar())
    while True:
        try:
            await client.connect()          # bloquea hasta que el live termina o se cae
            log.warning("[RECONEXION] live terminado, reintento en 30 s")
        except UserOfflineError:
            log.info(f"[RECONEXION] @{client.unique_id} no está en vivo, reintento en 30 s")
        except Exception as exc:
            log.error(f"[RECONEXION] error {exc!r}, reintento en 30 s")
        avisar_conexion(False)              # terminó, no está en vivo o se cayó: el backend deja de rellenar
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())