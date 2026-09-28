"""Registro de accesos denegados: solo inserción y retención de 90 días (CA-25.3, M-08, RNF-22; ADR-010, «Decisión»).

Las filas antiguas se insertan con SQL y fecha explícita; no se mueve el reloj
de la base de datos. Sin ``transaction=True``.
"""
import ast
import datetime
import io
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from autorizacion import acceso_denegado
from autorizacion.acceso_denegado import RETENCION_DIAS, purgar_vencidos
from autorizacion.models import RegistroAccesoDenegado
from comun.solo_insercion import OperacionNoPermitida
from tests.ayudas import crear_cliente

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parent.parent
LOGGER = "autorizacion.acceso_denegado"


def _sql(sentencia, parametros=()):
    with connection.cursor() as cursor:
        cursor.execute(sentencia, parametros)
        return cursor.rowcount


def _insertar(antiguedad):
    """Inserta una fila con fecha explícita = ahora (Python) - antiguedad."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO acceso_denegado (fecha, usuario_id, recurso, entidad) "
            "VALUES (%s, 1, 'GET api/prueba', 'recurso_prueba') RETURNING id",
            [timezone.now() - antiguedad],
        )
        return cursor.fetchone()[0]


def _rechazado(sentencia, parametros=()):
    with pytest.raises(DatabaseError) as error:
        with transaction.atomic():
            _sql(sentencia, parametros)
    assert error.value.__cause__.sqlstate == "42501"


def _existe(pk):
    return RegistroAccesoDenegado.objects.filter(pk=pk).exists()


DIAS = datetime.timedelta(days=1)


# --- Trigger ---


@pytest.mark.parametrize("antiguedad", [DIAS, 91 * DIAS])
def test_update_rechazado_aunque_la_fila_sea_antigua(antiguedad):
    pk = _insertar(antiguedad)

    _rechazado("UPDATE acceso_denegado SET recurso = 'otro' WHERE id = %s", [pk])


def test_delete_de_una_fila_reciente_rechazado():
    pk = _insertar(DIAS)

    _rechazado("DELETE FROM acceso_denegado WHERE id = %s", [pk])
    assert _existe(pk)


def test_delete_de_una_fila_de_91_dias_permitido():
    pk = _insertar(91 * DIAS)

    assert _sql("DELETE FROM acceso_denegado WHERE id = %s", [pk]) == 1
    assert not _existe(pk)


def test_truncate_rechazado():
    pk = _insertar(91 * DIAS)

    _rechazado("TRUNCATE acceso_denegado")
    assert _existe(pk)


def test_retencion_dias_coincide_con_el_literal_del_trigger():
    # Prueba de comportamiento: el borde del trigger está en RETENCION_DIAS.
    margen = datetime.timedelta(hours=1)
    vencida = _insertar(RETENCION_DIAS * DIAS + margen)
    vigente = _insertar(RETENCION_DIAS * DIAS - margen)

    assert _sql("DELETE FROM acceso_denegado WHERE id = %s", [vencida]) == 1
    _rechazado("DELETE FROM acceso_denegado WHERE id = %s", [vigente])
    assert RETENCION_DIAS == 90


# --- Purga (M-08, ADR-010 punto 3) ---


def test_purgar_vencidos_borra_solo_las_vencidas_y_devuelve_el_conteo(caplog):
    caplog.set_level("INFO", logger=LOGGER)
    vencidas = [_insertar(91 * DIAS), _insertar(200 * DIAS)]
    vigentes = [_insertar(datetime.timedelta(0)), _insertar(89 * DIAS)]

    assert purgar_vencidos() == 2

    assert not any(_existe(pk) for pk in vencidas)
    assert all(_existe(pk) for pk in vigentes)
    mensajes = [r.getMessage() for r in caplog.records if r.name == LOGGER]
    assert mensajes == ["Purga automática por retención de accesos denegados: 2 filas eliminadas."]


def test_purgar_sin_vencidas_devuelve_cero_y_no_registra_evento(caplog):
    caplog.set_level("INFO", logger=LOGGER)
    _insertar(DIAS)

    assert purgar_vencidos() == 0
    assert not [r for r in caplog.records if r.name == LOGGER]


def test_registrar_purga_las_vencidas_antes_de_insertar():
    usuario = crear_cliente()
    vencida = _insertar(91 * DIAS)

    fila = acceso_denegado.registrar(usuario, "GET api/prueba", "recurso_prueba", "ref-1")

    assert not _existe(vencida)
    assert fila.usuario_id == usuario.pk and fila.entidad_ref == "ref-1"


def test_comando_purgar_accesos_denegados():
    vencida = _insertar(91 * DIAS)
    vigente = _insertar(DIAS)
    salida = io.StringIO()

    call_command("purgar_accesos_denegados", stdout=salida)

    assert not _existe(vencida) and _existe(vigente)
    assert "1" in salida.getvalue()


# --- Solo inserción desde el ORM ---


def test_el_orm_no_permite_modificar_ni_borrar():
    fila = acceso_denegado.registrar(crear_cliente(), "GET api/prueba", "recurso_prueba")
    fila.recurso = "otro"

    with pytest.raises(OperacionNoPermitida):
        fila.save()
    with pytest.raises(OperacionNoPermitida):
        fila.delete()
    with pytest.raises(OperacionNoPermitida):
        RegistroAccesoDenegado.objects.filter(pk=fila.pk).update(recurso="otro")
    with pytest.raises(OperacionNoPermitida):
        RegistroAccesoDenegado.objects.all().delete()


# --- Nadie fuera de autorizacion/ usa el registro (M-08) ---

_MODULOS_PROHIBIDOS = {"autorizacion.models", "autorizacion.acceso_denegado"}


def _archivos_fuera_de_autorizacion():
    for archivo in sorted(RAIZ.rglob("*.py")):
        relativo = archivo.relative_to(RAIZ)
        if relativo.parts[0] in ("autorizacion", "tests"):
            continue
        yield relativo, archivo


def _usos_del_registro(arbol):
    """Importaciones del modelo o del servicio, y SQL (textos que no son docstrings) sobre la tabla."""
    docstrings = {
        id(nodo.value)
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Constant)
    }
    usos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            usos += [a.name for a in nodo.names if a.name in _MODULOS_PROHIBIDOS]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            if nodo.module in _MODULOS_PROHIBIDOS:
                usos.append(nodo.module)
            elif nodo.module == "autorizacion":
                usos += [a.name for a in nodo.names if f"autorizacion.{a.name}" in _MODULOS_PROHIBIDOS]
        elif (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and id(nodo) not in docstrings
            and ("acceso_denegado" in nodo.value or "RegistroAccesoDenegado" in nodo.value)
        ):
            usos.append("texto con acceso_denegado")
        elif isinstance(nodo, ast.Name) and nodo.id == "RegistroAccesoDenegado":
            usos.append(nodo.id)
    return usos


def test_ningun_modulo_fuera_de_autorizacion_usa_el_registro_de_accesos_denegados():
    revisados = set()
    hallazgos = {}
    for relativo, archivo in _archivos_fuera_de_autorizacion():
        revisados.add(relativo.as_posix())
        usos = _usos_del_registro(ast.parse(archivo.read_text(encoding="utf-8")))
        if usos:
            hallazgos[relativo.as_posix()] = usos

    assert "identidad/limitador.py" in revisados
    assert hallazgos == {}


def test_el_analisis_detecta_un_uso_del_registro():
    codigo = (
        "from autorizacion.models import RegistroAccesoDenegado\n"
        "from autorizacion import acceso_denegado\n"
        "SQL = 'SELECT count(*) FROM acceso_denegado'\n"
    )

    assert len(_usos_del_registro(ast.parse(codigo))) >= 3
