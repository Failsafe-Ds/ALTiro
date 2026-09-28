"""Bitácora administrativa de solo inserción (RNF-11, R-10, RF-37, CA-19.3, HU-19; ADR-010).

Sin ``transaction=True``: las filas escritas se revierten con la transacción
de cada prueba (pytest.ini usa --reuse-db).
"""
import inspect
import re
import sys
import uuid

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import Client

from bitacora.models import Bitacora
from bitacora.servicios import SISTEMA, ErrorBitacora, registrar
from comun.solo_insercion import OperacionNoPermitida
from identidad import servicios as servicios_identidad
from identidad.models import Rol, Usuario
from tests.ayudas import CONTRASENA, crear_cliente, iniciar_sesion
from tests.control_terceros import rutas

pytestmark = pytest.mark.django_db


def _sql(sentencia, parametros=()):
    with connection.cursor() as cursor:
        cursor.execute(sentencia, parametros)
        return cursor.fetchone() if cursor.description else None


def _insertar_sql(**cambios):
    datos = {"autor_tipo": "sistema", "autor_id": None, "motivo": "Motivo de prueba"}
    datos.update(cambios)
    (pk,) = _sql(
        "INSERT INTO bitacora (fecha, autor_tipo, autor_id, accion, entidad, entidad_ref, motivo) "
        "VALUES (now(), %s, %s, 'prueba', 'expediente', 'ref-1', %s) RETURNING id",
        [datos["autor_tipo"], datos["autor_id"], datos["motivo"]],
    )
    return pk


def _rechazado_por_trigger(sentencia, parametros=()):
    with pytest.raises(DatabaseError) as error:
        with transaction.atomic():
            _sql(sentencia, parametros)
    assert error.value.__cause__.sqlstate == "42501"


def _entrada(**cambios):
    datos = {
        "autor": SISTEMA,
        "accion": "cambio_estado",
        "entidad": "expediente",
        "entidad_ref": "ref-1",
        "motivo": "Documentos completos",
        "valor_anterior": {"estado": "En revisión"},
        "valor_nuevo": {"estado": "Aprobado"},
    }
    datos.update(cambios)
    return registrar(**datos)


# --- Defensa en profundidad: triggers en SQL directo (RNF-11, R-10) ---


def test_update_en_sql_directo_es_rechazado():
    pk = _insertar_sql()

    _rechazado_por_trigger("UPDATE bitacora SET motivo = 'otro' WHERE id = %s", [pk])
    assert Bitacora.objects.get(pk=pk).motivo == "Motivo de prueba"


def test_delete_en_sql_directo_es_rechazado():
    pk = _insertar_sql()

    _rechazado_por_trigger("DELETE FROM bitacora WHERE id = %s", [pk])
    assert Bitacora.objects.filter(pk=pk).exists()


def test_truncate_en_sql_directo_es_rechazado():
    pk = _insertar_sql()

    _rechazado_por_trigger("TRUNCATE bitacora")
    assert Bitacora.objects.filter(pk=pk).exists()


def test_la_bd_exige_coherencia_entre_autor_tipo_y_autor_id():
    with pytest.raises(IntegrityError), transaction.atomic():
        _insertar_sql(autor_tipo="usuario", autor_id=None)
    with pytest.raises(IntegrityError), transaction.atomic():
        _insertar_sql(autor_tipo="sistema", autor_id=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        _insertar_sql(autor_tipo="otro", autor_id=None)


@pytest.mark.parametrize("motivo", ["", "   "])
def test_la_bd_rechaza_motivo_vacio(motivo):
    with pytest.raises(IntegrityError), transaction.atomic():
        _insertar_sql(motivo=motivo)


def test_la_tabla_no_tiene_fk_hacia_usuario():
    # ADR-010, «Decisión», punto 4.
    with connection.cursor() as cursor:
        restricciones = connection.introspection.get_constraints(cursor, "bitacora")
    assert not [nombre for nombre, datos in restricciones.items() if datos["foreign_key"]]


# --- Barrera 1: la aplicación no ofrece edición ni borrado (RNF-11) ---


def test_el_orm_no_permite_modificar_una_entrada_existente():
    entrada = _entrada()
    entrada.motivo = "Otro motivo"

    with pytest.raises(OperacionNoPermitida):
        entrada.save()
    with pytest.raises(OperacionNoPermitida):
        Bitacora.objects.filter(pk=entrada.pk).update(motivo="Otro motivo")
    # bulk_update abre un atomic sin punto de guardado: se aísla en uno propio.
    with pytest.raises(OperacionNoPermitida), transaction.atomic():
        Bitacora.objects.bulk_update([entrada], ["motivo"])
    assert Bitacora.objects.get(pk=entrada.pk).motivo == "Documentos completos"


def test_el_orm_no_permite_borrar():
    entrada = _entrada()

    with pytest.raises(OperacionNoPermitida):
        entrada.delete()
    with pytest.raises(OperacionNoPermitida):
        Bitacora.objects.filter(pk=entrada.pk).delete()
    with pytest.raises(OperacionNoPermitida):
        Bitacora.objects.all().delete()
    assert Bitacora.objects.filter(pk=entrada.pk).exists()


# Reescrita según ADR-010, E-1 (antes: "ninguna ruta expone la bitácora"). Verifica
# tres cosas: no hay escritura sobre la bitácora desde la API, la única lectura es
# el historial de un expediente (solo GET) y ninguna ruta lee ``acceso_denegado``.

RUTA_HISTORIAL = "api/curatoria/expedientes/<uuid:ref>/historial"


def _fuente_de_la_vista(ruta):
    return inspect.getsource(sys.modules[ruta.vista.__module__])


def _vista_original(vista):
    while hasattr(vista, "__wrapped__"):
        vista = vista.__wrapped__
    return vista


def test_ninguna_ruta_edita_ni_borra_la_bitacora():
    for ruta in rutas():
        assert "bitacora" not in ruta.patron and "acceso" not in ruta.patron, ruta
        modulo = getattr(ruta.vista, "__module__", "")
        assert not modulo.startswith(("bitacora", "autorizacion")), ruta
        fuente = _fuente_de_la_vista(ruta)
        # Las vistas no escriben la bitácora: solo el servicio registrar() inserta
        # entradas nuevas, y el modelo y los triggers rechazan editar o borrar (pruebas de arriba).
        assert "Bitacora.objects.create" not in fuente, ruta
        assert not re.search(r"Bitacora\.objects\.[^\n]*\.(update|delete|bulk_update)\(", fuente), ruta


def test_la_unica_ruta_que_lee_la_bitacora_es_el_historial_y_solo_acepta_get():
    lectoras = {
        ruta.patron
        for ruta in rutas()
        if "Bitacora" in inspect.getsource(_vista_original(ruta.vista))
    }
    assert lectoras == {RUTA_HISTORIAL}

    (historial,) = [ruta for ruta in rutas() if ruta.patron == RUTA_HISTORIAL]
    fuente = inspect.getsource(_vista_original(historial.vista))
    assert "Bitacora.objects.filter(" in fuente
    assert "registrar" not in fuente
    assert historial.vista.roles_requeridos == ("curatoria",)


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_el_historial_no_acepta_metodos_de_escritura(metodo):
    servicios_identidad.crear_cuenta_administrativa(
        nombre="Cura Prueba", correo="cura@example.com", roles=[Rol.CURATORIA], contrasena=CONTRASENA
    )
    client = Client()
    assert iniciar_sesion(client, "cura@example.com").status_code == 200
    antes = Bitacora.objects.count()

    respuesta = getattr(client, metodo)(f"/api/curatoria/expedientes/{uuid.uuid4()}/historial")

    assert respuesta.status_code == 405
    assert respuesta["Allow"] == "GET"
    assert Bitacora.objects.count() == antes


def test_ninguna_ruta_lee_los_accesos_denegados():
    for ruta in rutas():
        fuente = _fuente_de_la_vista(ruta)
        assert "RegistroAccesoDenegado" not in fuente, ruta
        assert "acceso_denegado" not in fuente, ruta


# --- Servicio registrar (RF-37, CA-19.3) ---


def test_registrar_por_un_usuario_guarda_todos_los_campos():
    usuario = crear_cliente()

    entrada = _entrada(autor=usuario)

    entrada = Bitacora.objects.get(pk=entrada.pk)
    assert (entrada.autor_tipo, entrada.autor_id) == ("usuario", usuario.pk)
    assert entrada.accion == "cambio_estado"
    assert (entrada.entidad, entrada.entidad_ref) == ("expediente", "ref-1")
    assert entrada.valor_anterior == {"estado": "En revisión"}
    assert entrada.valor_nuevo == {"estado": "Aprobado"}
    assert entrada.motivo == "Documentos completos"
    assert entrada.fecha is not None


def test_registrar_por_el_sistema_no_tiene_autor_id():
    entrada = _entrada(autor=SISTEMA)

    assert (entrada.autor_tipo, entrada.autor_id) == ("sistema", None)


@pytest.mark.parametrize("motivo", ["", "   ", None])
def test_registrar_rechaza_motivo_vacio(motivo):
    with pytest.raises(ErrorBitacora):
        _entrada(motivo=motivo)
    assert not Bitacora.objects.exists()


@pytest.mark.parametrize("autor", [None, 5, "sistema", Usuario(nombre="Sin guardar")])
def test_registrar_rechaza_un_autor_incoherente(autor):
    with pytest.raises(ErrorBitacora):
        _entrada(autor=autor)
    assert not Bitacora.objects.exists()


@pytest.mark.parametrize(
    "valores",
    [
        {"valor_nuevo": {"password": "x"}},
        {"valor_anterior": {"Contrasena": "x"}},
        {"valor_nuevo": {"datos": [{"hash_de_la_clave": "x"}]}},
        {"valor_nuevo": {"sesion": {"Token": "x"}}},
    ],
)
def test_registrar_rechaza_claves_prohibidas_a_cualquier_profundidad(valores):
    with pytest.raises(ErrorBitacora):
        _entrada(**valores)
    assert not Bitacora.objects.exists()


def test_registrar_exige_estar_dentro_de_una_transaccion(monkeypatch):
    # Se registra en el mismo atomic() que el cambio (ADR-010).
    monkeypatch.setattr(connection, "in_atomic_block", False)

    with pytest.raises(ErrorBitacora):
        _entrada()
    monkeypatch.undo()
    assert not Bitacora.objects.exists()


def test_si_el_cambio_se_revierte_la_entrada_tambien():
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            _entrada()
            raise RuntimeError("falla el cambio")

    assert not Bitacora.objects.exists()
