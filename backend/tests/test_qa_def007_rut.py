"""QA de DEF-QA-007 (ADR-003, Enmienda E-2): el RUT no llega a los registros.

Hueco cubierto: las pruebas del backend verifican el CHECK de teléfono y la
unicidad del correo, pero no una violación de ``perfil_maestro_rut_unico``, cuyo
``DETAIL`` de PostgreSQL es ``Key (rut)=(<RUT>) already exists``.

Datos ficticios: RUT sintético 12.345.678-5 (forma canónica ``123456785``).
Sin ``transaction=True``: todo se revierte con la transacción de cada prueba.
"""
import io
import logging

import pytest
from django.db import IntegrityError, transaction

from comun.registros import FiltroTrazasSeguras
from identidad.models import PerfilMaestro, Usuario
from tests.ayudas import CONTRASENA, crear_maestro

pytestmark = pytest.mark.django_db

RUT_FORMATEADO = "12.345.678-5"
RUT_CANONICO = "123456785"
NOMBRE = "Maestro Ficticio Qa"
CORREO = "qa.rut.def007@example.com"


def _consola():
    return next(h for h in logging.getLogger().handlers if h.get_name() == "consola")


def _violar_rut_unico():
    crear_maestro(rut=RUT_FORMATEADO)
    otro = Usuario(nombre=NOMBRE, telefono="+56910000002", correo=CORREO)
    otro.set_password(CONTRASENA)
    otro.save(force_insert=True)
    with pytest.raises(IntegrityError) as error:
        with transaction.atomic():
            PerfilMaestro(usuario=otro, rut=RUT_CANONICO).save(force_insert=True)
    return error.value


def _escribir(nombre_logger, exc):
    """Registra ``exc`` con el handler y el formatter reales y devuelve (texto, registro)."""
    salida = io.StringIO()
    consola = _consola()
    capturados = []

    class Espia(logging.Handler):
        def emit(self, record):
            capturados.append(record)

    espia = Espia()
    logger = logging.getLogger(nombre_logger)
    logger.addHandler(espia)
    anterior = consola.setStream(salida)
    try:
        logger.error("Error de prueba QA", exc_info=(type(exc), exc, exc.__traceback__))
    finally:
        consola.setStream(anterior)
        logger.removeHandler(espia)
    return salida.getvalue(), capturados[0]


def test_la_excepcion_original_si_contiene_el_rut():
    """Control: sin el filtro, el mensaje de psycopg trae el RUT (el riesgo es real)."""
    exc = _violar_rut_unico()
    assert RUT_CANONICO in str(exc.__cause__)


@pytest.mark.parametrize("nombre_logger", ["django.request", "qa.otro_logger"])
def test_unicidad_de_rut_no_escribe_el_rut(nombre_logger):
    exc = _violar_rut_unico()

    texto, registro = _escribir(nombre_logger, exc)

    for presente in (
        # ADR-026, E-8: una línea JSON por evento.
        '"nivel": "ERROR"', f'"operacion": "{nombre_logger}", "mensaje": "Error de prueba QA"', "Traceback (most recent call last):",
        "psycopg.errors.UniqueViolation", "django.db.utils.IntegrityError", "sqlstate=23505",
        "restriccion=perfil_maestro_rut_unico", "tabla=perfil_maestro",
    ):
        assert presente in texto, presente
    for ausente in ("DETAIL", "Key (rut)", RUT_CANONICO, "12345678", RUT_FORMATEADO, NOMBRE, CORREO, "argon2"):
        assert ausente not in texto, ausente
    # El valor original no queda en ninguna propiedad del LogRecord.
    assert registro.exc_info is None
    for valor in vars(registro).values():
        assert RUT_CANONICO not in str(valor)
        assert "DETAIL" not in str(valor)


def test_django_request_filtra_antes_de_cualquier_handler():
    """Un handler agregado directamente a django.request (sin el filtro) no ve la traza original."""
    exc = _violar_rut_unico()

    _, registro = _escribir("django.request", exc)

    assert any(isinstance(f, FiltroTrazasSeguras) for f in logging.getLogger("django.request").filters)
    assert registro.exc_info is None
    assert RUT_CANONICO not in (registro.exc_text or "")
