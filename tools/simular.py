import sys
from datetime import datetime, timezone
import httpx

URL = "http://127.0.0.1:8000"

CASOS = [
    ("prueba1", "quedaré embarazada pronto", 1),
    ("prueba2", "axel ama a otra o a mi", 5),
    ("prueba3", "Hola q le pasa a mi hija se desmaya y le late muy rapido su corazón", 1),
    ("prueba4", "Mi papa me obligará a terminar con mi novio?", 2),
]

def enviar(ev):
    httpx.post(f"{URL}/eventos", json=ev).raise_for_status()

def main():
    ts = datetime.now(timezone.utc).isoformat()
    for user, texto, valor in CASOS:
        base = {"user": user, "nickname": user, "ts": ts}
        enviar({**base, "tipo": "comment", "texto": texto})
        enviar({**base, "tipo": "gift", "regalo": "Rose", "valor": valor})
    print(f"{len(CASOS)} casos enviados")

if __name__ == "__main__":
    sys.exit(main())