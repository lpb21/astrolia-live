import asyncio, json, logging
from datetime import timedelta
import pytest
from backend import bitacora, revision
from backend.cola import Cola
from backend.worker import Worker
from tests.test_worker import GenFijo, T0

NOMBRE = "2026-10-11_03-46-53_bitacora.jsonl"


@pytest.fixture
def bita(tmp_path):
    manejador = bitacora.abrir(tmp_path / NOMBRE)
    yield tmp_path
    bitacora.cerrar(manejador)


def t(seg):
    return T0 + timedelta(seconds=seg)

def ev(c, tipo, user, seg, **k):
    c.procesar({"tipo": tipo, "user": user, "nickname": user.capitalize(), "ts": t(seg).isoformat(), **k})
    if tipo == "comment":
        bitacora.anotar("comentario", user, user.capitalize(), t(seg), texto=k["texto"], situacion=c.situacion(user))
    else:
        bitacora.anotar("regalo", user, user.capitalize(), t(seg), texto=k["regalo"], valor=k["valor"])


def test_sin_abrir_no_escribe_nada(tmp_path):
    bitacora.anotar("comentario", "u", "U", texto="hola")
    assert list(tmp_path.iterdir()) == [] and not bitacora._abiertas

def test_resumen_por_persona(bita):
    c = Cola(espera_gratis=timedelta(0))
    w = Worker(c, GenFijo(), palabras_por_seg=0)
    paso = lambda seg: asyncio.run(w.paso(t(seg)))
    ev(c, "comment", "migdalia", 0, texto="Soy Migdalia 12 9 75 Quiero saber si robin termina la relacion")
    paso(1)                                                     # se le lee gratis
    for seg in (60, 120, 180):
        ev(c, "comment", "migdalia", seg, texto="Soy Migdalia 12 9 75 Quiero saber si robin termina la relacion")
    ev(c, "comment", "shirley", 200, texto="me irá bien en esta relación con bryan?")
    paso(201)                                                   # se le pide la fecha
    c.pendientes(t(300))                                        # no la da: sale de la fila
    ev(c, "gift", "muda", 310, regalo="Rose", valor=5)          # regala y nunca escribe
    ev(c, "gift", "nueva", 315, regalo="Rose", valor=5)
    bitacora.anotar("comentario", "nueva", "Nueva", t(316), texto="hola", situacion=c.situacion("nueva"))
    ev(c, "comment", "rica", 320, texto="soy Ana 05/05/90 me va a buscar Juan?")
    ev(c, "gift", "rica", 321, regalo="Doughnut", valor=30)
    paso(322)

    assert revision.sesiones(bita) == [NOMBRE]
    r = revision.resumen(revision.leer(NOMBRE, bita))
    p = {x["user"]: x for x in r["personas"]}
    assert p["migdalia"]["estado"] == "Leída" and p["migdalia"]["lecturas"] == 1 and not p["migdalia"]["alerta"]
    repetido = p["migdalia"]["eventos"][-1]
    assert repetido["veces"] == 3 and repetido["situacion"] == "Esa pregunta ya se le respondió: se lee de nuevo solo si regala"
    assert p["shirley"]["estado"] == "Salió de la fila sin dar la fecha"
    assert [e["tipo"] for e in p["shirley"]["eventos"]] == ["comentario", "pide_fecha", "sin_fecha"]
    assert p["muda"]["alerta"] == "Regaló y no se le leyó con su regalo" and p["muda"]["monedas"] == 5
    lectura = next(e for e in p["rica"]["eventos"] if e["tipo"] == "lectura")
    assert lectura["nivel"] == "Lectura doble" and lectura["signo"] == "Tauro" and len(lectura["cartas"]) == 4
    assert not p["rica"]["alerta"] and r["personas"][0]["user"] == "muda"       # las alertas van primero
    assert p["nueva"]["estado"].startswith("En la fila") and not p["nueva"]["alerta"]   # sigue esperando: no es alerta
    assert r["totales"] == {"personas": 5, "con_regalo": 3, "monedas": 40, "lecturas": 2, "alertas": 1}

def test_solo_se_leen_archivos_de_bitacora(bita):
    (bita / "secreto.txt").write_text("x")
    (bita / NOMBRE).write_text('{"ts": "2026-10-11T08:00:00+00:00", "tipo": "regalo", "user": "a", "valor": 1}\n{a medias')
    assert revision.sesiones(bita) == [NOMBRE] and len(revision.leer(NOMBRE, bita)) == 1
    for malo in ("secreto.txt", "../.env", "2026-10-11_03-46-53_backend.log"):
        with pytest.raises(ValueError):
            revision.leer(malo, bita)

def test_la_app_sirve_la_pagina_de_revision():
    from fastapi.testclient import TestClient
    from backend.app import app
    cliente = TestClient(app)
    assert "Revisión por persona" in cliente.get("/revision/").text
    assert isinstance(cliente.get("/revision/sesiones").json(), list)
    assert cliente.get("/revision/datos", params={"sesion": "../.env"}).json()["personas"] == []
