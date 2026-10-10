from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json, re, unicodedata

@dataclass
class LiveEvent:
    tipo: str            # "gift" | "comment" | "follow"
    user: str            # unique_id
    nickname: str
    texto: str = ""
    regalo: str = ""
    valor: int = 0       # diamantes totales (diamond_count * repeat_count)
    ts: str = ""
    msg_id: int = 0
    
    def __post_init__(self):
        self.ts = self.ts or datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def limpiar(texto: str) -> str:
    t = unicodedata.normalize("NFKC", texto)   # 𝑒𝑛 𝑔𝑒𝑛𝑒𝑟𝑎𝑙 -> en general
    t = re.sub(r"\[[a-zA-Z_]{2,20}\]", "", t)   # emotes de TikTok tipo [thanks]
    t = re.sub(r"(\d)\1{4,}", "", t)            # relleno numérico: 0000000 -> ""
    t = re.sub(r"([^\W\d_])\1{2,}", r"\1", t)   # letras estiradas: hoooola -> hola
    t = re.sub(r"([^\w\s])\1{2,}", r"\1", t)    # signos repetidos: ????? -> ?
    return re.sub(r"\s{2,}", " ", t).strip()