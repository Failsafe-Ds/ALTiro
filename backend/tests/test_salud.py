"""Pruebas de la verificación de salud GET /api/health/."""
import pytest
from django.db import OperationalError

URL = "/api/health/"


@pytest.mark.django_db
def test_salud_responde_200_con_base_de_datos(client):
    respuesta = client.get(URL)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "base_datos": "ok"}
    assert respuesta["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_salud_no_emite_hsts(client):
    respuesta = client.get(URL)

    assert "Strict-Transport-Security" not in respuesta.headers


class _ConexionCaida:
    def cursor(self):
        raise OperationalError('connection to server at "db" failed: password=detalle-interno')


def test_salud_responde_503_sin_detalles_si_la_base_no_responde(client, monkeypatch):
    monkeypatch.setattr("altiro.salud.connection", _ConexionCaida())

    respuesta = client.get(URL)

    assert respuesta.status_code == 503
    assert respuesta.json() == {"estado": "con_problemas", "base_datos": "no_disponible"}
    contenido = respuesta.content.decode()
    assert "detalle-interno" not in contenido
    assert "OperationalError" not in contenido


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_salud_solo_acepta_get(client, metodo):
    respuesta = getattr(client, metodo)(URL)

    assert respuesta.status_code == 405
