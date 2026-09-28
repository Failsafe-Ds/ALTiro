"""La aplicación se conecta con su propio rol, sin privilegios de superusuario.

Requiere que la base haya sido inicializada con infra/db/initdb/10-rol-app.sh.
"""
import os

import pytest
from django.conf import settings
from django.db import connection


def test_la_configuracion_usa_el_rol_de_la_app_y_no_el_administrativo():
    usuario = settings.DATABASES["default"]["USER"]

    assert usuario == os.environ["ALTIRO_DB_USER"]
    admin = os.environ.get("POSTGRES_USER")
    if admin:
        assert usuario != admin


@pytest.mark.django_db
def test_la_conexion_usa_el_rol_configurado():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user")
        (usuario_actual,) = cursor.fetchone()

    assert usuario_actual == settings.DATABASES["default"]["USER"]


@pytest.mark.django_db
def test_el_rol_de_la_app_no_tiene_privilegios_administrativos():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolcreaterole, rolreplication, rolbypassrls, rolcreatedb "
            "FROM pg_roles WHERE rolname = current_user"
        )
        superusuario, crea_roles, replicacion, salta_rls, crea_bases = cursor.fetchone()

    assert superusuario is False
    assert crea_roles is False
    assert replicacion is False
    assert salta_rls is False
    # CREATEDB se concede solo para crear la base de pruebas (pytest-django).
    assert crea_bases is True


@pytest.mark.django_db
def test_el_rol_de_la_app_no_puede_conectarse_a_otras_bases():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_database_privilege(current_user, 'postgres', 'CONNECT'), "
            "has_database_privilege(current_user, 'template1', 'CONNECT')"
        )
        postgres, template1 = cursor.fetchone()

    assert postgres is False
    assert template1 is False
