"""Reparto de dueños de la base real (ADR-030, B8).

El rol de la app solo tiene DML: las tablas, secuencias y funciones del
esquema public de la base de AlTiro son del rol migrador, así que la app no
puede desactivar los triggers de solo inserción (ADR-010, punto 8) ni crear
objetos. La base de pruebas de pytest-django (de la que la app sí es dueña) no
sirve para comprobarlo: estas pruebas se conectan a la base REAL
(``ALTIRO_DB_NAME``) y solo leen el catálogo; no escriben nada.

Requieren la pila levantada con ``docker compose up -d`` (servicio roles_db).
"""
import os

import psycopg
import pytest
from django.db import connection


def _consultar_base_real(sql):
    datos = connection.settings_dict
    with psycopg.connect(
        host=datos["HOST"], port=datos["PORT"], dbname=os.environ["ALTIRO_DB_NAME"],
        user=datos["USER"], password=datos["PASSWORD"], connect_timeout=5,
    ) as conexion:
        return conexion.execute(sql).fetchall()


@pytest.mark.django_db
def test_b8_la_app_no_es_duena_de_ningun_objeto_de_la_base_real():
    filas = _consultar_base_real(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relowner = (SELECT oid FROM pg_roles WHERE rolname = current_user) "
        "UNION ALL "
        "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' AND p.proowner = (SELECT oid FROM pg_roles WHERE rolname = current_user)"
    )
    assert filas == [(0,), (0,)]


@pytest.mark.django_db
def test_b8_la_app_no_puede_crear_objetos_en_public_de_la_base_real():
    [(puede_crear, puede_usar)] = _consultar_base_real(
        "SELECT has_schema_privilege(current_user, 'public', 'CREATE'), "
        "has_schema_privilege(current_user, 'public', 'USAGE')"
    )
    assert puede_crear is False
    assert puede_usar is True


@pytest.mark.django_db
@pytest.mark.parametrize("tabla", ["bitacora", "ticket_evento", "acceso_denegado"])
def test_b8_la_app_tiene_dml_pero_no_truncate_ni_trigger_en_tablas_de_solo_insercion(tabla):
    [(dueno, inserta, trunca, trigger)] = _consultar_base_real(
        f"SELECT pg_get_userbyid(relowner) = current_user, "
        f"has_table_privilege(current_user, '{tabla}', 'INSERT'), "
        f"has_table_privilege(current_user, '{tabla}', 'TRUNCATE'), "
        f"has_table_privilege(current_user, '{tabla}', 'TRIGGER') "
        f"FROM pg_class WHERE oid = 'public.{tabla}'::regclass"
    )
    assert dueno is False
    assert inserta is True
    assert trunca is False
    assert trigger is False
