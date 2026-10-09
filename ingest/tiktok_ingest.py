import os, logging
import dataclasses
from dotenv import load_dotenv
from TikTokLive import TikTokLiveClient
from TikTokLive.client.web.web_settings import WebDefaults
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent, GiftEvent, FollowEvent
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
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                    handlers=[logging.StreamHandler(), logging.FileHandler("ingest.log")])
log = logging.getLogger("ingest")


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

def emit(ev: LiveEvent):
    if es_duplicado(ev.msg_id):
        log.debug(f"[DUP] {ev.msg_id} {ev.user}")
        return
    log.info(ev.to_json())

@client.on(ConnectEvent)
async def on_connect(e): log.info(f"Conectado a @{e.unique_id}")

@client.on(DisconnectEvent)
async def on_disconnect(e): log.warning("Desconectado")

@client.on(CommentEvent)
async def on_comment(e: CommentEvent):
    emit(LiveEvent("comment", e.user.display_id, e.user.nickname,
                   texto=limpiar(e.content), msg_id=e.common.msg_id))

@client.on(GiftEvent)
async def on_gift(e: GiftEvent):
    log.debug(f"[RACHA] {e.user.display_id} {e.gift.name} x{e.repeat_count} "
              f"streakable={e.gift.streakable} streaking={e.streaking}")
    if e.gift.streakable and e.streaking:
        return
    emit(LiveEvent("gift", e.user.display_id, e.user.nickname,
                   regalo=e.gift.name, valor=e.gift.diamond_count * e.repeat_count, msg_id=e.common.msg_id))

@client.on(FollowEvent)
async def on_follow(e: FollowEvent):
    emit(LiveEvent("follow", e.user.display_id, e.user.nickname, msg_id=e.common.msg_id))
    #pass

if __name__ == "__main__":
    client.run()