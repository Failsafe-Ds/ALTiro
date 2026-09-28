"""Registros del servidor PostgreSQL sin datos personales (ADR-003, Enmienda E-1; DEF-QA-004).

Requiere que el servicio ``db`` corra con el ``command:`` de docker-compose.yml.
"""
import pytest
from django.db import connection

from identidad import servicios
from identidad.errores import ErrorValidacion
from tests.ayudas import CONTRASENA, TEL_B, crear_cliente, crear_maestro

pytestmark = pytest.mark.django_db


def _mostrar(parametro):
    with connection.cursor() as cursor:
        cursor.execute(f"SHOW {parametro}")
        return cursor.fetchone()[0]


@pytest.mark.parametrize(
    ("parametro", "esperado"),
    [
        # Cambian con E-1: sin sentencia ni DETAIL/HINT/CONTEXT/QUERY en el log.
        ("log_min_error_statement", "panic"),
        ("log_error_verbosity", "terse"),
        # No cambian con E-1.
        ("log_statement", "none"),
        ("log_min_duration_statement", "-1"),
    ],
)
def test_parametros_de_registro_del_servidor(parametro, esperado):
    assert _mostrar(parametro) == esperado


def test_colision_de_correo_en_la_bd_sigue_siendo_error_de_campo(monkeypatch):
    # Con TERSE en el servidor, el cliente sigue recibiendo el nombre de la
    # restricción (diag.constraint_name): la traducción de _guardar no cambia.
    crear_cliente()
    monkeypatch.setattr(servicios, "_correo_libre", lambda correo: None)

    with pytest.raises(ErrorValidacion) as error:
        servicios.crear_cuenta_cliente(
            nombre="Otra Prueba", telefono=TEL_B, correo="ana.prueba@example.com",
            contrasena=CONTRASENA, comuna="8101",
        )

    assert error.value.campo == "correo"


def test_colision_de_rut_en_la_bd_sigue_siendo_error_de_campo(monkeypatch):
    crear_maestro()
    monkeypatch.setattr(servicios, "_rut_libre", lambda rut: None)

    with pytest.raises(ErrorValidacion) as error:
        servicios.crear_cuenta_maestro(
            nombre="Maestro Dos", telefono=TEL_B, rut="11.111.111-1", contrasena=CONTRASENA
        )

    assert error.value.campo == "rut"
