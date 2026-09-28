"""Señal de rechazo CSRF y único reintento (ADR-006, Enmienda E-1; ADR-011, Enmienda E-1; RNF-07).

- Solo el 403 de CSRF_FAILURE_VIEW lleva ``AlTiro-Rechazo: csrf``.
- Ese 403 no tuvo efectos ni dejó registro en ``acceso_denegado``.
- El 403 por falta de rol no lleva la cabecera y deja exactamente una fila.

Sin ``transaction=True``: las filas de ``acceso_denegado`` se revierten con la
transacción de cada prueba.
"""
import pytest
from django.test import Client

from autorizacion.models import RegistroAccesoDenegado
from comun.api import CABECERA_RECHAZO, RECHAZO_CSRF
from identidad.models import IntentoAutenticacion, Usuario
from tests.ayudas import (
    URL_CLIENTES,
    URL_CSRF,
    URL_CUENTA,
    URL_SESION,
    crear_cliente,
    datos_cliente,
    iniciar_sesion,
    post_json,
    sin_texto_prohibido,
)

pytestmark = pytest.mark.django_db

URL_ACCION_CON_ROL = "/api/prueba/solo-curatoria/accion"
TOKEN_INVALIDO = "a" * 64  # formato válido, valor que no corresponde a la cookie
CORREO = "ana.prueba@example.com"


def _token(client):
    assert client.get(URL_CSRF).status_code == 204
    return client.cookies["csrftoken"].value


def _cabeceras_csrf(client, modo):
    """Cabeceras para un POST sin token o con token inválido."""
    if modo == "sin_token":
        return {}
    _token(client)  # hay cookie, pero el token enviado no corresponde
    return {"HTTP_X_CSRFTOKEN": TOKEN_INVALIDO}


def _es_rechazo_csrf(respuesta):
    return respuesta.status_code == 403 and respuesta.get(CABECERA_RECHAZO) == RECHAZO_CSRF


def _sesion_con_csrf(identificador=CORREO):
    """Cliente con CSRF exigido y sesión iniciada; devuelve también el token vigente."""
    client = Client(enforce_csrf_checks=True)
    respuesta = iniciar_sesion(client, identificador, HTTP_X_CSRFTOKEN=_token(client))
    assert respuesta.status_code == 200
    return client, _token(client)  # login() rota el token (ADR-006)


def test_constantes_de_la_senal():
    assert (CABECERA_RECHAZO, RECHAZO_CSRF) == ("AlTiro-Rechazo", "csrf")


# --- 1. El rechazo CSRF lleva la cabecera, cuerpo común sin motivo, sin efectos ---


@pytest.mark.parametrize("modo", ["sin_token", "token_invalido"])
def test_registro_rechazado_por_csrf_lleva_la_senal_y_no_crea_nada(modo):
    client = Client(enforce_csrf_checks=True)

    respuesta = post_json(client, URL_CLIENTES, datos_cliente(), **_cabeceras_csrf(client, modo))

    assert _es_rechazo_csrf(respuesta)
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "errores"}
    assert cuerpo["errores"] == {}
    assert "reason" not in respuesta.content.decode("utf-8")
    assert "CSRF" not in respuesta.content.decode("utf-8")
    assert sin_texto_prohibido(respuesta)
    assert Usuario.objects.count() == 0


@pytest.mark.parametrize("modo", ["sin_token", "token_invalido"])
def test_inicio_de_sesion_rechazado_por_csrf_lleva_la_senal_y_no_tiene_efectos(modo):
    crear_cliente()
    client = Client(enforce_csrf_checks=True)

    respuesta = iniciar_sesion(client, CORREO, **_cabeceras_csrf(client, modo))

    assert _es_rechazo_csrf(respuesta)
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "errores"}
    assert cuerpo["errores"] == {}
    assert "reason" not in respuesta.content.decode("utf-8")
    assert "sessionid" not in respuesta.cookies
    assert not IntentoAutenticacion.objects.exists()
    assert client.get(URL_CUENTA).status_code == 401


# --- 2. Ninguna otra respuesta lleva la cabecera ---


def _r401():
    return Client().get(URL_CUENTA)


def _r404():
    return Client().get("/api/no-existe")


def _r400():
    return Client().post(URL_CLIENTES, data="no es json", content_type="application/json")


def _r405():
    return Client().get(URL_CLIENTES)


def _r429():
    crear_cliente()
    origen = {"HTTP_X_REAL_IP": "203.0.113.20", "REMOTE_ADDR": "203.0.113.20"}
    for _ in range(5):
        assert iniciar_sesion(Client(), CORREO, "contraseña equivocada", **origen).status_code == 401
    return iniciar_sesion(Client(), CORREO, **origen)


def _r403_sin_rol():
    crear_cliente()
    client, token = _sesion_con_csrf()
    return post_json(client, URL_ACCION_CON_ROL, {}, HTTP_X_CSRFTOKEN=token)


@pytest.mark.parametrize(
    ("obtener", "estado"),
    [(_r401, 401), (_r404, 404), (_r400, 400), (_r405, 405), (_r429, 429), (_r403_sin_rol, 403)],
    ids=["401", "404", "400", "405", "429", "403_sin_rol"],
)
def test_ninguna_otra_respuesta_lleva_la_senal(obtener, estado):
    respuesta = obtener()

    assert respuesta.status_code == estado
    assert CABECERA_RECHAZO not in respuesta


def test_una_respuesta_exitosa_no_lleva_la_senal():
    client = Client(enforce_csrf_checks=True)

    respuesta = post_json(client, URL_CLIENTES, datos_cliente(), HTTP_X_CSRFTOKEN=_token(client))

    assert respuesta.status_code == 201
    assert CABECERA_RECHAZO not in respuesta


# --- 3. Falta de rol con CSRF válido: 403 sin cabecera y una fila ---


def test_falta_de_rol_con_csrf_valido_no_lleva_la_senal_y_deja_una_fila():
    usuario = crear_cliente()
    client, token = _sesion_con_csrf()

    respuesta = post_json(client, URL_ACCION_CON_ROL, {}, HTTP_X_CSRFTOKEN=token)

    assert respuesta.status_code == 403
    assert CABECERA_RECHAZO not in respuesta
    fila = RegistroAccesoDenegado.objects.get()
    assert fila.usuario_id == usuario.pk
    assert fila.recurso == "POST api/prueba/solo-curatoria/accion"


# --- 4. Secuencia del cliente: un único reintento, una única fila ---


def test_secuencia_rechazo_csrf_renovacion_y_reintento_deja_una_sola_fila():
    crear_cliente()
    client, _ = _sesion_con_csrf()

    primera = post_json(client, URL_ACCION_CON_ROL, {}, HTTP_X_CSRFTOKEN=TOKEN_INVALIDO)
    assert _es_rechazo_csrf(primera)
    assert RegistroAccesoDenegado.objects.count() == 0  # el rechazo CSRF no ejecutó la vista

    token_nuevo = _token(client)
    reintento = post_json(client, URL_ACCION_CON_ROL, {}, HTTP_X_CSRFTOKEN=token_nuevo)

    assert reintento.status_code == 403
    assert CABECERA_RECHAZO not in reintento  # el cliente no vuelve a reintentar
    assert RegistroAccesoDenegado.objects.count() == 1


# --- 5. Registro: rechazo CSRF, renovación y reintento crean una sola cuenta ---


def test_registro_tras_rechazo_csrf_y_reintento_crea_exactamente_una_cuenta():
    client = Client(enforce_csrf_checks=True)
    _token(client)

    primera = post_json(client, URL_CLIENTES, datos_cliente(), HTTP_X_CSRFTOKEN=TOKEN_INVALIDO)
    assert _es_rechazo_csrf(primera)
    assert Usuario.objects.count() == 0

    reintento = post_json(client, URL_CLIENTES, datos_cliente(), HTTP_X_CSRFTOKEN=_token(client))

    assert reintento.status_code == 201
    assert CABECERA_RECHAZO not in reintento
    assert Usuario.objects.count() == 1
