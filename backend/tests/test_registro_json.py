"""Registro de aplicación en JSON (RNF-22; ADR-026, E-8; S5, incremento 3).

Se captura la salida real del handler ``consola`` (formatter ``json``): una
línea JSON por evento con los campos exigidos y sin ruta con ``ref``, cuerpo,
parámetros, cookies, cabeceras ni datos personales.
"""
import io
import json
import logging
import uuid
from datetime import datetime

import pytest
from django.test import Client

from tests.ayudas import CONTRASENA, URL_CUENTA, crear_cliente, iniciar_sesion

CAMPOS_PETICION = {"nivel", "marca_tiempo", "usuario", "operacion", "estado", "duracion_ms"}
CORREO = "ana.prueba@example.com"  # el de crear_cliente()


def _consola():
    return next(h for h in logging.getLogger().handlers if h.get_name() == "consola")


def _lineas(accion):
    salida = io.StringIO()
    consola = _consola()
    anterior = consola.setStream(salida)
    try:
        accion()
    finally:
        consola.setStream(anterior)
    return salida.getvalue(), [json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip()]


def _de_peticiones(lineas):
    return [linea for linea in lineas if "estado" in linea]


@pytest.mark.regla("O-04")
@pytest.mark.django_db
def test_cada_peticion_trae_los_campos_y_ningun_dato_personal():
    usuario = crear_cliente()
    cliente = Client()
    ref = uuid.uuid4()

    def peticiones():
        iniciar_sesion(cliente, CORREO)
        cliente.get(URL_CUENTA)
        cliente.get(f"/api/maestros/publicos/{ref}?q=parametro-secreto")

    texto, lineas = _lineas(peticiones)
    registros = _de_peticiones(lineas)
    assert len(registros) == 3
    for registro in registros:
        assert set(registro) == CAMPOS_PETICION
        assert registro["marca_tiempo"].endswith("Z")
        datetime.fromisoformat(registro["marca_tiempo"].replace("Z", "+00:00"))
        assert isinstance(registro["duracion_ms"], (int, float))
    assert registros[0]["operacion"].endswith(" POST")
    assert registros[1] == {**registros[1], "usuario": str(usuario.pk), "operacion": "cuenta GET", "estado": 200}
    assert registros[2]["operacion"] == "perfil_publico GET"
    for ausente in (str(ref), "parametro-secreto", "/api/", CORREO, CONTRASENA, "sessionid", "csrftoken", "Cookie"):
        assert ausente not in texto, ausente


@pytest.mark.regla("O-04")
@pytest.mark.django_db
def test_sin_sesion_el_usuario_es_anonimo_y_django_request_no_escribe_el_404():
    texto, lineas = _lineas(lambda: Client().get(f"/api/no-existe/{uuid.uuid4()}"))
    registros = _de_peticiones(lineas)
    assert len(registros) == 1
    assert registros[0]["usuario"] == "anonimo"
    assert registros[0]["operacion"] == "sin_ruta GET"
    assert registros[0]["nivel"] == "WARNING"
    assert "Not Found" not in texto
    assert logging.getLogger("django.request").level == logging.ERROR


def test_un_evento_fuera_de_una_peticion_lleva_usuario_sistema_y_mensaje():
    _, lineas = _lineas(lambda: logging.getLogger("expediente.planificador").info("Corrida: %s.", 3))
    assert lineas == [{**lineas[0], "nivel": "INFO", "usuario": "sistema",
                       "operacion": "expediente.planificador", "mensaje": "Corrida: 3."}]


@pytest.mark.regla("O-04")
@pytest.mark.django_db
def test_un_evento_dentro_de_una_peticion_lleva_el_usuario_de_la_peticion_no_sistema():
    """DEF-QA-015: el inicio de sesión de una persona no se atribuye al Sistema."""
    usuario = crear_cliente()
    cliente = Client()

    def peticiones():
        iniciar_sesion(cliente, CORREO)
        cliente.get(URL_CUENTA)
        logging.getLogger("expediente.planificador").info("Corrida suelta.")

    _, lineas = _lineas(peticiones)
    eventos = [linea for linea in lineas if "mensaje" in linea]
    inicio = [e for e in eventos if e["mensaje"].startswith("Inicio de sesión correcto")]
    assert len(inicio) == 1
    assert inicio[0]["usuario"] in ("anonimo", str(usuario.pk))
    assert inicio[0]["operacion"] == "identidad.vistas"
    # Fuera de una petición se vuelve a "sistema": el contexto no queda pegado.
    assert [e["usuario"] for e in eventos if e["mensaje"] == "Corrida suelta."] == ["sistema"]
