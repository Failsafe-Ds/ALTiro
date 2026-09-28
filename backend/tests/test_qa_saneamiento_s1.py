"""QA del saneamiento del Sprint 1 (docs/testing/saneamiento-sprint-1.md).

DEF-QA-007: un ``IntegrityError`` que el servicio no traduce (por ejemplo, la
violación de un CHECK por un error de programación) produce un 500 genérico
hacia el cliente, pero el logger ``django.request`` escribe la traza completa,
y el mensaje de psycopg incluye ``DETAIL: Failing row contains (...)`` con los
valores de la fila: nombre, teléfono, correo y el hash de la contraseña.
Contradice CLAUDE.md §8 (sin secretos ni datos personales en los registros) y
la minimización de ADR-003, Enmienda E-1, del lado de la aplicación.

Se provoca en proceso, con datos ficticios, haciendo que la normalización del
teléfono devuelva un valor que viola ``usuario_telefono_formato``. No usa
``transaction=True``: la transacción de la prueba se revierte.

Corregido por ADR-003, Enmienda E-2 (``comun.registros.FiltroTrazasSeguras``):
la traza se conserva, sin el mensaje de la base de datos ni la fila.
"""
import logging

import pytest
from django.test import Client

from identidad import servicios
from tests.ayudas import URL_CLIENTES, datos_cliente, post_json, sin_texto_prohibido

pytestmark = pytest.mark.django_db

NOMBRE = "Nombre Ficticio Qa"
CORREO = "qa.def007@example.com"
TELEFONO_INVALIDO = "+00910000077"  # 12 caracteres, viola usuario_telefono_formato


def _provocar_500(monkeypatch):
    monkeypatch.setattr(servicios, "normalizar_telefono", lambda telefono: TELEFONO_INVALIDO)
    client = Client(raise_request_exception=False)
    return post_json(client, URL_CLIENTES, datos_cliente(nombre=NOMBRE, correo=CORREO))


def _texto_registrado(caplog):
    formateador = logging.Formatter("%(levelname)s %(name)s %(message)s")
    return "\n".join(formateador.format(registro) for registro in caplog.records)


def test_integrity_error_no_traducido_responde_500_generico(monkeypatch):
    respuesta = _provocar_500(monkeypatch)

    assert respuesta.status_code == 500
    cuerpo = respuesta.content.decode("utf-8")
    for dato in (NOMBRE, CORREO, "argon2", "Failing row", "usuario_telefono_formato"):
        assert dato not in cuerpo
    assert sin_texto_prohibido(respuesta)


def test_integrity_error_no_traducido_no_escribe_datos_personales_en_los_registros(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    datos = datos_cliente(nombre=NOMBRE, correo=CORREO)

    _provocar_500(monkeypatch)

    texto = _texto_registrado(caplog)
    # El error sí se registra, con la traza estructural y la restricción.
    for presente in (
        "Traceback", "CheckViolation", "IntegrityError", "23514", "usuario_telefono_formato", "servicios.py",
    ):
        assert presente in texto, presente
    for ausente in (
        "DETAIL", "Failing row contains", NOMBRE, CORREO, datos["telefono"], TELEFONO_INVALIDO, "argon2",
    ):
        assert ausente not in texto, ausente
