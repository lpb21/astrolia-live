from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta

DURACION = timedelta(seconds=60)
CADA = timedelta(minutes=10)      # pausa entre un boost y el siguiente


@dataclass
class Ganador:
    user: str
    nickname: str
    likes: int


class Boost:
    """Boost de likes: durante una ronda corta se cuentan los toques de cada persona y quien
    más dé gana el pase al primer turno. Arranca sola cada cierto tiempo o a pedido."""

    def __init__(self, duracion: timedelta = DURACION, cada: timedelta | None = CADA):
        self.duracion = duracion
        self.cada = cada                         # None = solo a pedido
        self.pedido = False                      # arranque manual pendiente
        self.inicio: datetime | None = None      # ronda en curso (o terminada sin cerrar)
        self._proximo: datetime | None = None
        self._likes: dict[str, list] = {}        # user -> [nickname, likes, cuándo llegó a esa cifra]
        self.ganadores: set[str] = set()         # quien ya ganó en este live no vuelve a competir ni sale en la lista

    def activo(self, ahora: datetime) -> bool:
        return self.inicio is not None and ahora < self.inicio + self.duracion

    def toca_iniciar(self, ahora: datetime) -> bool:
        if self.inicio is not None:
            return False
        if self._proximo is None and self.cada is not None:
            self._proximo = ahora + self.cada    # el primero, un rato después de arrancar el backend
        return self.pedido or (self._proximo is not None and ahora >= self._proximo)

    def iniciar(self, ahora: datetime) -> None:
        self.inicio, self.pedido, self._likes = ahora, False, {}

    def like(self, user: str, nickname: str, cantidad: int, ts: datetime) -> None:
        if self.inicio is None or not self.inicio <= ts < self.inicio + self.duracion or user in self.ganadores:
            return
        fila = self._likes.setdefault(user, [nickname, 0, ts])
        fila[1] += max(cantidad, 1)
        fila[2] = ts

    def toca_cerrar(self, ahora: datetime) -> bool:
        return self.inicio is not None and ahora >= self.inicio + self.duracion

    def cerrar(self, ahora: datetime) -> Ganador | None:
        """Termina la ronda. Gana quien más likes dio; en empate, quien llegó primero a la cifra."""
        ganador = None
        if self._likes:
            user, (nickname, likes, _) = min(self._likes.items(), key=lambda kv: (-kv[1][1], kv[1][2]))
            ganador = Ganador(user, nickname, likes)
            self.ganadores.add(user)
        self.inicio, self._likes = None, {}
        self._proximo = ahora + self.cada if self.cada is not None else None
        return ganador

    def vista(self, ahora: datetime) -> dict | None:
        """Lo que muestra el overlay mientras corre la ronda: segundos que quedan y los tres primeros."""
        if not self.activo(ahora):
            return None
        primeros = sorted(self._likes.values(), key=lambda f: (-f[1], f[2]))[:3]
        return {"restante": round((self.inicio + self.duracion - ahora).total_seconds()),
                "top": [{"nickname": n, "likes": k} for n, k, _ in primeros]}
