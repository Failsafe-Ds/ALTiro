"""Servicios del maestro y regla única de publicación, incremento 2 del S3.

RF-05, RF-34, RNF-25, HU-12, HU-20, HU-24, CA-12.1, CA-12.2, CA-20.1, CA-24.1,
CA-24.3, RNF-07; ADR-017 (punto 4 y E-1), ADR-019.

- ``perfil_publico`` nace con ``perfil_maestro`` (invariante) y la migración de
  datos lo crea para los maestros existentes.
- ``licencia_habilitante_de`` es equivalente a la regla anterior (E-1).
- Visibilidad calculada en cada lectura: licencia en revisión, observada o
  vencida oculta el servicio regulado; validada y vigente no. El día del
  vencimiento, en hora de Santiago, ya no es visible (borde de la medianoche UTC).
- **Estado actual:** la comuna base (incremento 3) y la foto (incremento 5)
  todavía no se pueden cargar, así que hoy ningún maestro es elegible y ningún
  servicio es visible. Las pruebas lo verifican y, para probar el resto de la
  regla, simulan esas dos condiciones con el fixture ``elegible``.

Datos ficticios (@example.com, RUT sintéticos). Los documentos se crean sin
archivo: la regla solo lee sus datos.
"""
import datetime
import importlib
import json
import uuid
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.apps import apps as registro_apps
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from autorizacion.middleware import MENSAJE_SIN_ROL
from autorizacion.models import RegistroAccesoDenegado
from catalogo.models import Modalidad, Oficio, Servicio, ServicioModalidad
from comun.api import respuesta_no_encontrado
from expediente import servicios as expedientes
from expediente import vigencia
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, TipoDocumento
from identidad import servicios as servicios_identidad
from identidad.errores import InvarianteVioladaError
from identidad.models import PerfilMaestro, Rol
from perfil import publicacion
from perfil import servicios as servicios_perfil
from perfil import vistas as vistas_perfil
from perfil.models import PerfilPublico, ServicioMaestro
from tests.ayudas import (
    CONTRASENA,
    TEL_A,
    TEL_B,
    crear_cliente,
    crear_maestro,
    iniciar_sesion,
    post_json,
    sin_texto_prohibido,
)
from tests.privacidad import assert_campos_ausentes

pytestmark = pytest.mark.django_db

RUT = "11.111.111-1"
RUT_CANONICO = "111111111"
RUT_OTRO = "22.222.222-2"
URL = "/api/maestros/servicios"
URL_CATALOGO = "/api/catalogo"
NO_ENCONTRADO = respuesta_no_encontrado().content
SANTIAGO = ZoneInfo("America/Santiago")
T, H = Modalidad.POR_TRABAJO, Modalidad.POR_HORA

VALIDADO = EstadoDocumento.VALIDADO
EN_REVISION = EstadoDocumento.EN_REVISION
OBSERVADO = EstadoDocumento.OBSERVADO
REEMPLAZADO = EstadoDocumento.REEMPLAZADO


# --- Ayudas ---


def _sesion(identificador):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


def _expediente(usuario):
    return Expediente.objects.get(perfil_maestro_id=usuario.pk)


def _con_estado(usuario, estado):
    Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(estado=estado)


def _servicio_catalogo(oficio, nombre, modalidades=None):
    servicio = Servicio.objects.create(oficio=Oficio.objects.get(codigo=oficio), nombre=nombre, orden=1)
    for modalidad, precio in (modalidades or {T: 30000}).items():
        ServicioModalidad.objects.create(servicio=servicio, modalidad=modalidad, precio_referencia=precio)
    return servicio


def _licencia(usuario, estado=VALIDADO, vencimiento=None, motivo="", cargado_en=None, oficio="gas"):
    if estado == OBSERVADO and not motivo:
        motivo = "Foto borrosa"
    return Documento.objects.create(
        expediente=_expediente(usuario),
        tipo=TipoDocumento.LICENCIA_SEC,
        oficio=Oficio.objects.get(codigo=oficio),
        fecha_emision=datetime.date(2020, 1, 10),
        fecha_vencimiento=vencimiento,
        estado=estado,
        motivo_observacion=motivo,
        archivo=uuid.uuid4(),
        cargado_en=cargado_en or timezone.now(),
    )


def _ofrecido(usuario, servicio, modalidad=T, monto=35000):
    return ServicioMaestro.objects.create(maestro_id=usuario.pk, servicio=servicio, modalidad=modalidad, monto=monto)


@pytest.fixture
def maestro():
    usuario = crear_maestro(rut=RUT)
    expedientes.declarar_oficios(_expediente(usuario), ["gas", "pintura"])
    return usuario


@pytest.fixture
def sesion(maestro):
    return _sesion(RUT)


@pytest.fixture
def gas():
    return _servicio_catalogo("gas", "Instalación de cocina", {T: 30000, H: 12000})


@pytest.fixture
def pintura():
    return _servicio_catalogo("pintura", "Pintura de habitación", {T: 80000})


@pytest.fixture
def elegible(monkeypatch, maestro):
    """Simula lo que llega en los incrementos 3 (comuna base) y 5 (foto), con el expediente aprobado."""
    monkeypatch.setattr(publicacion, "tiene_comuna_base", lambda maestro_id: True)
    PerfilPublico.objects.filter(perfil_maestro_id=maestro.pk).update(
        foto=uuid.uuid4(), foto_actualizada_en=timezone.now()
    )
    _con_estado(maestro, EstadoExpediente.APROBADO)
    return maestro


def _motivos(servicio_maestro, hoy=None):
    return publicacion.motivos_no_visible(ServicioMaestro.objects.get(pk=servicio_maestro.pk), hoy)


# --- Perfil público (ADR-019; propuesta del S3, §3) ---


def test_el_perfil_publico_nace_con_el_perfil_maestro_con_ref_propia(maestro):
    perfil = PerfilPublico.objects.get(perfil_maestro_id=maestro.pk)
    assert perfil.ref != _expediente(maestro).ref
    assert perfil.foto is None
    assert servicios_identidad.verificar_invariantes(maestro) == []


def test_agregar_perfil_maestro_con_sesion_tambien_crea_el_perfil_publico():
    cliente = crear_cliente()
    servicios_identidad.agregar_perfil_maestro(cliente, rut=RUT_OTRO)

    assert PerfilPublico.objects.filter(perfil_maestro_id=cliente.pk).exists()


def test_perfil_maestro_sin_perfil_publico_viola_el_invariante_y_se_revierte(monkeypatch):
    monkeypatch.setattr(servicios_perfil, "crear_perfil_publico_para", lambda perfil: None)

    with pytest.raises(InvarianteVioladaError) as error:
        crear_maestro(rut=RUT)

    assert "perfil_maestro sin perfil público" in error.value.violaciones
    assert not PerfilMaestro.objects.exists()


def test_la_migracion_crea_el_perfil_publico_de_los_maestros_existentes(maestro):
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    PerfilPublico.objects.filter(perfil_maestro_id__in=[maestro.pk, otro.pk]).delete()
    migracion = importlib.import_module("perfil.migrations.0002_perfiles_publicos_existentes")

    migracion.crear_perfiles_publicos(registro_apps, None)
    migracion.crear_perfiles_publicos(registro_apps, None)

    refs = list(PerfilPublico.objects.values_list("ref", flat=True))
    assert len(refs) == 2 and len(set(refs)) == 2
    assert servicios_identidad.verificar_invariantes(maestro) == []


def test_la_bd_exige_fecha_si_hay_foto(maestro):
    with pytest.raises(IntegrityError), transaction.atomic():
        PerfilPublico.objects.filter(perfil_maestro_id=maestro.pk).update(foto=uuid.uuid4())


# --- Restricciones de servicio_maestro ---


def test_la_bd_exige_modalidad_valida_monto_en_rango_y_un_activo_por_servicio(maestro, gas):
    for datos in ({"modalidad": "por_dia", "monto": 1}, {"modalidad": T, "monto": 0},
                  {"modalidad": T, "monto": 10_000_001}):
        with pytest.raises(IntegrityError), transaction.atomic():
            ServicioMaestro.objects.create(maestro_id=maestro.pk, servicio=gas, **datos)
    primero = _ofrecido(maestro, gas)
    with pytest.raises(IntegrityError), transaction.atomic():
        _ofrecido(maestro, gas)
    ServicioMaestro.objects.filter(pk=primero.pk).update(retirado_en=timezone.now())
    _ofrecido(maestro, gas)
    assert ServicioMaestro.objects.filter(maestro_id=maestro.pk).count() == 2


# --- licencia_habilitante_de (refactor sin cambio de regla, ADR-017 E-1) ---


def _escenarios_de_licencias(maestro):
    """Conjuntos de licencias de gas con distintos estados, fechas y reemplazos."""
    hoy = vigencia.hoy_negocio()
    base = timezone.now() - datetime.timedelta(days=10)
    pasado, futuro = hoy - datetime.timedelta(days=1), hoy + datetime.timedelta(days=30)
    escenarios = [
        [],
        [(VALIDADO, None)],
        [(VALIDADO, futuro)],
        [(VALIDADO, hoy)],
        [(EN_REVISION, None)],
        [(OBSERVADO, None)],
        [(REEMPLAZADO, futuro), (EN_REVISION, futuro)],
        [(REEMPLAZADO, futuro), (OBSERVADO, None)],
        [(REEMPLAZADO, futuro), (VALIDADO, pasado + datetime.timedelta(days=400))],
        [(REEMPLAZADO, hoy), (EN_REVISION, None)],
        [(REEMPLAZADO, None), (REEMPLAZADO, futuro), (VALIDADO, hoy)],
    ]
    for licencias in escenarios:
        Documento.objects.filter(tipo=TipoDocumento.LICENCIA_SEC).delete()
        for indice, (estado, vencimiento) in enumerate(licencias):
            motivo = "Foto borrosa" if estado == OBSERVADO else ""
            _licencia(maestro, estado, vencimiento, motivo, cargado_en=base + datetime.timedelta(days=indice))
        yield hoy


def test_licencia_habilitante_de_es_equivalente_a_la_regla_con_consultas(maestro):
    oficio = Oficio.objects.get(codigo="gas")
    expediente = _expediente(maestro)
    for hoy in _escenarios_de_licencias(maestro):
        licencias = list(Documento.objects.filter(tipo=TipoDocumento.LICENCIA_SEC))
        esperada = vigencia.licencia_habilitante(expediente, oficio, hoy)
        # En cualquier orden de entrada.
        assert vigencia.licencia_habilitante_de(licencias, hoy) == esperada
        assert vigencia.licencia_habilitante_de(list(reversed(licencias)), hoy) == esperada


def test_licencia_habilitante_de_no_consulta_la_base(maestro, django_assert_num_queries):
    licencia = _licencia(maestro, VALIDADO, None)
    licencias = list(Documento.objects.filter(pk=licencia.pk))

    with django_assert_num_queries(0):
        assert vigencia.licencia_habilitante_de(licencias, vigencia.hoy_negocio()) == licencias[0]


# --- CA-12.1: sin modalidad o monto no se publica y se señala qué falta ---


@pytest.mark.parametrize(
    ("cuerpo", "campos"),
    [
        ({}, {"servicio", "modalidad", "monto"}),
        ({"modalidad": T}, {"monto"}),
        ({"monto": 35000}, {"modalidad"}),
        ({"modalidad": None, "monto": None}, {"modalidad", "monto"}),
        ({"modalidad": "", "monto": ""}, {"modalidad", "monto"}),
    ],
)
def test_ca12_1_sin_modalidad_o_monto_responde_400_en_el_campo_y_no_crea_nada(sesion, gas, cuerpo, campos):
    if "servicio" not in campos:
        cuerpo = {**cuerpo, "servicio": str(gas.ref)}

    respuesta = post_json(sesion, URL, cuerpo)

    assert respuesta.status_code == 400
    errores = respuesta.json()["errores"]
    assert set(errores) == campos
    if "modalidad" in campos:
        assert errores["modalidad"] == servicios_perfil.MENSAJE_MODALIDAD_FALTA
    if "monto" in campos:
        assert errores["monto"] == servicios_perfil.MENSAJE_MONTO_FALTA
    assert not ServicioMaestro.objects.exists()


@pytest.mark.parametrize("monto", [0, -1, 10_000_001, 1.5, True, "abc", "25.000", "-5", [1]])
def test_el_monto_debe_ser_un_entero_en_pesos_en_rango(sesion, gas, monto):
    respuesta = post_json(sesion, URL, {"servicio": str(gas.ref), "modalidad": T, "monto": monto})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"monto": servicios_perfil.MENSAJE_MONTO_INVALIDO}
    assert not ServicioMaestro.objects.exists()


@pytest.mark.parametrize(("monto", "guardado"), [(10_000_000, 10_000_000), (1, 1), ("25000", 25000)])
def test_montos_validos(sesion, gas, monto, guardado):
    respuesta = post_json(sesion, URL, {"servicio": str(gas.ref), "modalidad": T, "monto": monto})

    assert respuesta.status_code == 201
    assert ServicioMaestro.objects.get().monto == guardado


def test_el_maestro_ofrece_un_servicio_con_modalidad_y_monto(sesion, maestro, gas):
    respuesta = post_json(sesion, URL, {"servicio": str(gas.ref), "modalidad": H, "monto": 15000})

    assert respuesta.status_code == 201
    assert respuesta["Cache-Control"] == "no-store"
    datos = respuesta.json()["servicio"]
    assert set(datos) == {"ref", "servicio", "oficio", "modalidad", "modalidad_texto", "monto", "visible", "motivos"}
    assert datos["servicio"] == {"ref": str(gas.ref), "nombre": "Instalación de cocina"}
    assert datos["oficio"] == {"codigo": "gas", "nombre": "Gas"}
    assert (datos["modalidad"], datos["modalidad_texto"], datos["monto"]) == (H, "Por hora", 15000)
    # Sin licencia y sin ser elegible: no visible, con los dos motivos.
    assert datos["visible"] is False
    assert [m["codigo"] for m in datos["motivos"]] == ["licencia_no_vigente", "maestro_no_elegible"]
    assert_campos_ausentes(respuesta, {"id", "pk", "rut", "telefono", "correo", "maestro", "maestro_id"},
                           valores=[RUT_CANONICO, "+56910000001"])
    servicio = ServicioMaestro.objects.get()
    assert (servicio.maestro_id, servicio.retirado_en) == (maestro.pk, None)


def test_la_modalidad_debe_estar_admitida_por_el_catalogo(sesion, pintura):
    respuesta = post_json(sesion, URL, {"servicio": str(pintura.ref), "modalidad": H, "monto": 5000})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"modalidad": "Este servicio no se cobra de esa forma. Elige por trabajo."}


@pytest.mark.parametrize("servicio", [None, "no-es-uuid", 5, str(uuid.uuid4())])
def test_el_servicio_debe_ser_del_catalogo(sesion, servicio):
    cuerpo = {"modalidad": T, "monto": 1000}
    if servicio is not None:
        cuerpo["servicio"] = servicio

    respuesta = post_json(sesion, URL, cuerpo)

    assert respuesta.json()["errores"] == {"servicio": servicios_perfil.MENSAJE_SERVICIO_FALTA}


def test_un_servicio_dado_de_baja_en_el_catalogo_no_se_puede_ofrecer(sesion, gas, pintura):
    Servicio.objects.filter(pk=gas.pk).update(activo=False)
    Oficio.objects.filter(codigo="pintura").update(activo=False)

    for servicio in (gas, pintura):
        respuesta = post_json(sesion, URL, {"servicio": str(servicio.ref), "modalidad": T, "monto": 1000})
        assert respuesta.json()["errores"] == {"servicio": servicios_perfil.MENSAJE_SERVICIO_FALTA}


def test_el_servicio_debe_ser_de_un_oficio_declarado(sesion):
    carpinteria = _servicio_catalogo("carpinteria", "Arreglo de puerta")

    respuesta = post_json(sesion, URL, {"servicio": str(carpinteria.ref), "modalidad": T, "monto": 1000})

    assert respuesta.json()["errores"] == {"servicio": servicios_perfil.MENSAJE_SERVICIO_OFICIO_NO_DECLARADO}


def test_no_se_ofrece_dos_veces_el_mismo_servicio_pero_si_despues_de_quitarlo(sesion, gas):
    primero = post_json(sesion, URL, {"servicio": str(gas.ref), "modalidad": T, "monto": 1000})
    repetido = post_json(sesion, URL, {"servicio": str(gas.ref), "modalidad": T, "monto": 2000})
    assert repetido.status_code == 400
    assert repetido.json()["errores"] == {"servicio": servicios_perfil.MENSAJE_SERVICIO_REPETIDO}

    assert sesion.delete(f"{URL}/{primero.json()['servicio']['ref']}").status_code == 204
    assert post_json(sesion, URL, {"servicio": str(gas.ref), "modalidad": T, "monto": 2000}).status_code == 201


# --- D-7: edición en todo estado salvo rechazado ---


@pytest.mark.parametrize(
    "estado", [EstadoExpediente.EN_REVISION, EstadoExpediente.OBSERVADO, EstadoExpediente.APROBADO,
               EstadoExpediente.SUSPENDIDO],
)
def test_d7_el_maestro_edita_sus_servicios_en_todo_estado_salvo_rechazado(sesion, maestro, gas, estado):
    _con_estado(maestro, estado)

    creado = post_json(sesion, URL, {"servicio": str(gas.ref), "modalidad": T, "monto": 1000})
    assert creado.status_code == 201
    url = f"{URL}/{creado.json()['servicio']['ref']}"
    assert sesion.patch(url, data=json.dumps({"monto": 2000}), content_type="application/json").status_code == 200
    assert sesion.delete(url).status_code == 204


def test_d7_expediente_rechazado_responde_409_sin_cambios(sesion, maestro, gas):
    ofrecido = _ofrecido(maestro, gas)
    _con_estado(maestro, EstadoExpediente.RECHAZADO)
    url = f"{URL}/{ofrecido.ref}"

    respuestas = [
        post_json(sesion, URL, {"servicio": str(gas.ref), "modalidad": H, "monto": 1000}),
        sesion.patch(url, data=json.dumps({"monto": 2000}), content_type="application/json"),
        sesion.delete(url),
    ]

    for respuesta in respuestas:
        assert respuesta.status_code == 409
        assert respuesta.json()["mensaje"] == servicios_perfil.MENSAJE_RECHAZADO
    ofrecido.refresh_from_db()
    assert (ofrecido.monto, ofrecido.retirado_en) == (35000, None)
    assert ServicioMaestro.objects.count() == 1
    # Consultar sí puede.
    assert sesion.get(URL).status_code == 200


# --- PATCH y DELETE del dueño ---


def test_el_dueno_cambia_modalidad_y_monto(sesion, maestro, gas):
    ofrecido = _ofrecido(maestro, gas)

    respuesta = sesion.patch(
        f"{URL}/{ofrecido.ref}", data=json.dumps({"modalidad": H, "monto": 14000}), content_type="application/json"
    )

    assert respuesta.status_code == 200
    ofrecido.refresh_from_db()
    assert (ofrecido.modalidad, ofrecido.monto) == (H, 14000)
    assert ofrecido.actualizado_en >= ofrecido.creado_en


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [({}, "monto"), ({"monto": 0}, "monto"), ({"modalidad": "por_dia"}, "modalidad"), ({"modalidad": None}, "modalidad")],
)
def test_cambiar_valida_los_datos(sesion, maestro, gas, cuerpo, campo):
    ofrecido = _ofrecido(maestro, gas)

    respuesta = sesion.patch(f"{URL}/{ofrecido.ref}", data=json.dumps(cuerpo), content_type="application/json")

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {campo}
    ofrecido.refresh_from_db()
    assert (ofrecido.modalidad, ofrecido.monto) == (T, 35000)


def test_no_se_cambia_el_servicio_del_catalogo_al_editar(sesion, maestro, gas, pintura):
    ofrecido = _ofrecido(maestro, gas)

    respuesta = sesion.patch(
        f"{URL}/{ofrecido.ref}", data=json.dumps({"servicio": str(pintura.ref)}), content_type="application/json"
    )

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"servicio"}


def test_quitar_es_baja_logica_y_desaparece_de_la_lista(sesion, maestro, gas):
    ofrecido = _ofrecido(maestro, gas)

    assert sesion.delete(f"{URL}/{ofrecido.ref}").status_code == 204

    ofrecido.refresh_from_db()
    assert ofrecido.retirado_en is not None
    assert sesion.get(URL).json()["servicios"] == []
    assert _motivos(ofrecido)[0] == publicacion.RETIRADO
    otra_vez = sesion.delete(f"{URL}/{ofrecido.ref}")
    assert otra_vez.status_code == 409
    assert otra_vez.json()["mensaje"] == servicios_perfil.MENSAJE_RETIRADO


# --- Estado actual de la elegibilidad (incrementos 3 y 5 pendientes) ---


def test_hoy_ningun_maestro_es_elegible_porque_faltan_comuna_base_y_foto(sesion, maestro, pintura):
    _con_estado(maestro, EstadoExpediente.APROBADO)
    ofrecido = _ofrecido(maestro, pintura, monto=80000)

    assert publicacion.tiene_comuna_base(maestro.pk) is False
    assert publicacion.pendientes_del_maestro(maestro.pk) == [publicacion.SIN_COMUNA_BASE, publicacion.SIN_FOTO]
    assert _motivos(ofrecido) == [publicacion.MAESTRO_NO_ELEGIBLE]
    assert publicacion.maestro_publicado(maestro.pk) is False
    datos = sesion.get(URL).json()
    assert [p["codigo"] for p in datos["pendientes"]] == ["sin_comuna_base", "sin_foto"]
    assert datos["servicios"][0]["visible"] is False


@pytest.mark.parametrize(
    ("estado", "mensaje"),
    [
        (EstadoExpediente.EN_REVISION, "Tu postulación todavía no está aprobada."),
        (EstadoExpediente.SUSPENDIDO, "Tu cuenta de maestro está suspendida."),
        (EstadoExpediente.RECHAZADO, "Tu postulación no fue aprobada."),
    ],
)
def test_solo_el_expediente_aprobado_publica(sesion, maestro, elegible, pintura, estado, mensaje):
    ofrecido = _ofrecido(maestro, pintura)
    assert publicacion.visible(ofrecido)
    _con_estado(maestro, estado)

    assert _motivos(ofrecido) == [publicacion.MAESTRO_NO_ELEGIBLE]
    assert sesion.get(URL).json()["pendientes"] == [{"codigo": "postulacion_no_aprobada", "mensaje": mensaje}]


def test_sin_foto_no_es_elegible(maestro, elegible, pintura):
    ofrecido = _ofrecido(maestro, pintura)
    PerfilPublico.objects.filter(perfil_maestro_id=maestro.pk).update(foto=None, foto_actualizada_en=None)

    assert publicacion.pendientes_del_maestro(maestro.pk) == [publicacion.SIN_FOTO]
    assert not publicacion.visible(ofrecido)


# --- RNF-25 / CA-12.2: sin licencia vigente, el servicio regulado no es visible ---


@pytest.mark.parametrize(
    "licencia",
    [
        None,
        {"estado": EN_REVISION},
        {"estado": OBSERVADO},
        {"estado": VALIDADO, "vencimiento": datetime.date(2025, 1, 1)},
    ],
    ids=["sin_licencia", "en_revision", "observada", "vencida"],
)
def test_ca12_2_rnf25_servicio_de_gas_sin_licencia_vigente_no_es_visible(sesion, maestro, elegible, gas, licencia):
    if licencia:
        _licencia(maestro, licencia["estado"], licencia.get("vencimiento"))
    ofrecido = _ofrecido(maestro, gas)

    assert _motivos(ofrecido) == [publicacion.LICENCIA_NO_VIGENTE]
    assert not publicacion.visible(ofrecido)
    (datos,) = sesion.get(URL).json()["servicios"]
    assert datos["visible"] is False
    assert datos["motivos"] == [
        {"codigo": "licencia_no_vigente",
         "mensaje": vistas_perfil.MENSAJES_MOTIVO[publicacion.LICENCIA_NO_VIGENTE].format(oficio="Gas")}
    ]


def test_ca12_2_con_licencia_validada_y_vigente_el_servicio_de_gas_es_visible(sesion, maestro, elegible, gas):
    _licencia(maestro, VALIDADO, vigencia.hoy_negocio() + datetime.timedelta(days=90))
    ofrecido = _ofrecido(maestro, gas)

    assert _motivos(ofrecido) == []
    assert publicacion.maestro_publicado(maestro.pk) is True
    (datos,) = sesion.get(URL).json()["servicios"]
    assert (datos["visible"], datos["motivos"]) == (True, [])


def test_e1_renovacion_la_licencia_anterior_validada_sigue_habilitando(maestro, elegible, gas):
    antes = timezone.now() - datetime.timedelta(days=5)
    _licencia(maestro, REEMPLAZADO, vigencia.hoy_negocio() + datetime.timedelta(days=10), cargado_en=antes)
    nueva = _licencia(maestro, EN_REVISION, None)
    ofrecido = _ofrecido(maestro, gas)

    assert publicacion.visible(ofrecido)
    # Si curatoría observa la nueva, la anterior sigue contando hasta que venza.
    Documento.objects.filter(pk=nueva.pk).update(estado=OBSERVADO, motivo_observacion="Ilegible")
    assert publicacion.visible(ofrecido)
    hoy_vencida = vigencia.hoy_negocio() + datetime.timedelta(days=10)
    assert _motivos(ofrecido, hoy_vencida) == [publicacion.LICENCIA_NO_VIGENTE]


def test_la_licencia_de_otro_oficio_regulado_no_habilita_gas(maestro, elegible, gas):
    _con_estado(maestro, EstadoExpediente.EN_REVISION)
    expedientes.declarar_oficios(_expediente(maestro), ["gas", "electricidad", "pintura"])
    _con_estado(maestro, EstadoExpediente.APROBADO)
    _licencia(maestro, VALIDADO, None, oficio="electricidad")
    ofrecido = _ofrecido(maestro, gas)

    assert _motivos(ofrecido) == [publicacion.LICENCIA_NO_VIGENTE]


# --- CA-24.1: el día del vencimiento, en hora de Santiago, deja de ser visible ---


VENCE = datetime.date(2026, 11, 15)  # horario de verano en Chile: UTC-3


def _en_santiago(fecha, hora, minuto=0, segundo=0):
    return datetime.datetime(fecha.year, fecha.month, fecha.day, hora, minuto, segundo, tzinfo=SANTIAGO)


@pytest.mark.parametrize(
    ("instante", "visible"),
    [
        (_en_santiago(VENCE - datetime.timedelta(days=1), 12), True),
        # Medianoche UTC del día del vencimiento: en Santiago sigue siendo el día anterior.
        (datetime.datetime(2026, 11, 15, 0, 30, tzinfo=datetime.timezone.utc), True),
        (_en_santiago(VENCE - datetime.timedelta(days=1), 23, 59, 59), True),
        (_en_santiago(VENCE, 0, 0, 1), False),
        (_en_santiago(VENCE, 15), False),
        (_en_santiago(VENCE + datetime.timedelta(days=1), 9), False),
    ],
    ids=["dia_anterior", "medianoche_utc", "ultimo_segundo_del_dia_anterior", "inicio_del_dia", "dia_mismo",
         "dia_siguiente"],
)
def test_ca24_1_el_dia_del_vencimiento_el_servicio_regulado_queda_inactivo(
    maestro, elegible, gas, instante, visible
):
    _licencia(maestro, VALIDADO, VENCE)
    ofrecido = _ofrecido(maestro, gas)

    with time_machine.travel(instante, tick=False):
        assert publicacion.visible(ofrecido) is visible
        # La sesión se abre en el instante simulado (la inactividad la cerraría).
        (datos,) = _sesion(RUT).get(URL).json()["servicios"]
    assert datos["visible"] is visible
    assert ("licencia_no_vigente" in [m["codigo"] for m in datos["motivos"]]) is not visible


def test_ca24_1_la_reactivacion_ocurre_sola_al_validar_una_licencia_nueva(maestro, elegible, gas):
    vencida = _licencia(maestro, VALIDADO, datetime.date(2025, 1, 1),
                        cargado_en=timezone.now() - datetime.timedelta(days=30))
    ofrecido = _ofrecido(maestro, gas)
    assert not publicacion.visible(ofrecido)

    Documento.objects.filter(pk=vencida.pk).update(estado=REEMPLAZADO)
    nueva = _licencia(maestro, EN_REVISION, None)
    assert not publicacion.visible(ofrecido)
    Documento.objects.filter(pk=nueva.pk).update(estado=VALIDADO)

    assert publicacion.visible(ofrecido)


# --- CA-24.3: una licencia sin vencimiento nunca oculta el servicio ---


def test_ca24_3_licencia_sin_vencimiento_nunca_desactiva_el_servicio(maestro, elegible, gas):
    _licencia(maestro, VALIDADO, None)
    ofrecido = _ofrecido(maestro, gas)

    for anos in (0, 5, 30):
        with time_machine.travel(timezone.now() + datetime.timedelta(days=365 * anos), tick=False):
            assert _motivos(ofrecido) == []


# --- RF-34 / HU-24: el mismo maestro sigue visible en sus oficios no regulados ---


def test_rf34_gas_oculto_y_pintura_visible_en_el_mismo_maestro(sesion, maestro, elegible, gas, pintura):
    _licencia(maestro, VALIDADO, datetime.date(2025, 6, 1))
    ofrecido_gas = _ofrecido(maestro, gas)
    ofrecido_pintura = _ofrecido(maestro, pintura, monto=80000)

    assert not publicacion.visible(ofrecido_gas)
    assert publicacion.visible(ofrecido_pintura)
    assert publicacion.maestro_publicado(maestro.pk) is True
    lista = {s["oficio"]["codigo"]: s for s in sesion.get(URL).json()["servicios"]}
    assert (lista["gas"]["visible"], lista["pintura"]["visible"]) == (False, True)


# --- Otros motivos de la regla única ---


def test_catalogo_inactivo_oficio_no_declarado_y_modalidad_no_admitida(maestro, elegible, gas, pintura):
    ofrecido = _ofrecido(maestro, pintura)
    assert publicacion.visible(ofrecido)

    Servicio.objects.filter(pk=pintura.pk).update(activo=False)
    assert _motivos(ofrecido) == [publicacion.CATALOGO_INACTIVO]
    Servicio.objects.filter(pk=pintura.pk).update(activo=True)
    Oficio.objects.filter(codigo="pintura").update(activo=False)
    assert _motivos(ofrecido) == [publicacion.CATALOGO_INACTIVO]
    Oficio.objects.filter(codigo="pintura").update(activo=True)

    ServicioModalidad.objects.filter(servicio=pintura).update(modalidad=H)
    assert _motivos(ofrecido) == [publicacion.MODALIDAD_NO_ADMITIDA]
    ServicioModalidad.objects.filter(servicio=pintura).update(modalidad=T)

    _con_estado(maestro, EstadoExpediente.EN_REVISION)
    expedientes.declarar_oficios(_expediente(maestro), ["gas"])
    _con_estado(maestro, EstadoExpediente.APROBADO)
    assert _motivos(ofrecido) == [publicacion.OFICIO_NO_DECLARADO]


def test_los_motivos_salen_en_orden_fijo(maestro, gas):
    ofrecido = _ofrecido(maestro, gas)
    ServicioMaestro.objects.filter(pk=ofrecido.pk).update(retirado_en=timezone.now(), modalidad=H)
    Servicio.objects.filter(pk=gas.pk).update(activo=False)
    ServicioModalidad.objects.filter(servicio=gas, modalidad=H).delete()
    expedientes.declarar_oficios(_expediente(maestro), ["pintura"])

    assert _motivos(ofrecido) == list(publicacion.MOTIVOS)


# --- CA-20.1: un servicio nuevo del catálogo queda disponible sin cambios de código ---


def test_ca20_1_servicio_creado_por_comercial_disponible_para_el_maestro(maestro, sesion):
    servicios_identidad.crear_cuenta_administrativa(
        nombre="Comercial Prueba", correo="comercial@example.com", roles=[Rol.COMERCIAL], contrasena=CONTRASENA
    )
    comercial = _sesion("comercial@example.com")
    creado = post_json(
        comercial,
        "/api/comercial/servicios",
        {"oficio": "pintura", "nombre": "Pintura de fachada",
         "modalidades": [{"modalidad": T, "precio_referencia": 150000}]},
    )
    assert creado.status_code == 201
    ref = creado.json()["servicio"]["ref"]

    # El visitante lo ve en el catálogo público y el maestro lo puede ofrecer.
    catalogo = Client().get(URL_CATALOGO).json()
    (pintura,) = [o for o in catalogo["oficios"] if o["codigo"] == "pintura"]
    assert ref in [s["ref"] for s in pintura["servicios"]]
    respuesta = post_json(sesion, URL, {"servicio": ref, "modalidad": T, "monto": 140000})
    assert respuesta.status_code == 201
    assert sesion.get(URL).json()["servicios"][0]["servicio"]["nombre"] == "Pintura de fachada"


# --- Terceros por ruta (RNF-07, HU-25, CA-25.1) ---


def _administrativo(rol, correo):
    return servicios_identidad.crear_cuenta_administrativa(
        nombre="Admin Prueba", correo=correo, roles=[rol], contrasena=CONTRASENA
    )


def _terceros_sin_rol():
    return {
        "cliente": (lambda: crear_cliente(telefono=TEL_A), "ana.prueba@example.com"),
        "comercial": (lambda: _administrativo(Rol.COMERCIAL, "comercial@example.com"), "comercial@example.com"),
        "curatoria": (lambda: _administrativo(Rol.CURATORIA, "cura@example.com"), "cura@example.com"),
        "moderacion": (lambda: _administrativo(Rol.MODERACION, "moderacion@example.com"), "moderacion@example.com"),
        "control_gestion": (
            lambda: _administrativo(Rol.CONTROL_GESTION, "gestion@example.com"), "gestion@example.com"
        ),
    }


PETICIONES = {
    "patch": lambda client, url: client.patch(url, data=json.dumps({"monto": 1}), content_type="application/json"),
    "delete": lambda client, url: client.delete(url),
}


def _sin_cambios(ofrecido):
    ofrecido.refresh_from_db()
    assert (ofrecido.monto, ofrecido.retirado_en) == (35000, None)


@pytest.mark.terceros("mi_servicio")
@pytest.mark.parametrize("metodo", sorted(PETICIONES))
def test_otro_maestro_recibe_el_404_identico_y_queda_registrado(maestro, gas, metodo):
    ofrecido = _ofrecido(maestro, gas)
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    url = f"{URL}/{ofrecido.ref}"

    respuesta = PETICIONES[metodo](_sesion(RUT_OTRO), url)

    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (otro.pk, "servicio_maestro", str(ofrecido.ref))
    assert fila.recurso == f"{metodo.upper()} api/maestros/servicios/<uuid:ref>"
    _sin_cambios(ofrecido)


@pytest.mark.terceros("mi_servicio")
@pytest.mark.parametrize("metodo", sorted(PETICIONES))
@pytest.mark.parametrize("nombre", sorted(_terceros_sin_rol()))
def test_los_roles_sin_maestro_reciben_403_registrado(maestro, gas, metodo, nombre):
    ofrecido = _ofrecido(maestro, gas)
    crear, identificador = _terceros_sin_rol()[nombre]
    tercero = crear()

    respuesta = PETICIONES[metodo](_sesion(identificador), f"{URL}/{ofrecido.ref}")

    assert respuesta.status_code == 403
    assert respuesta.json() == {"mensaje": MENSAJE_SIN_ROL, "errores": {}}
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "ruta", None)
    _sin_cambios(ofrecido)


@pytest.mark.terceros("mi_servicio")
@pytest.mark.parametrize("metodo", sorted(PETICIONES))
def test_anonimo_recibe_401_sin_registro(maestro, gas, metodo):
    ofrecido = _ofrecido(maestro, gas)

    respuesta = PETICIONES[metodo](Client(), f"{URL}/{ofrecido.ref}")

    assert respuesta.status_code == 401
    assert not RegistroAccesoDenegado.objects.exists()
    _sin_cambios(ofrecido)


@pytest.mark.terceros("mi_servicio")
@pytest.mark.parametrize("metodo", sorted(PETICIONES))
def test_referencia_inexistente_responde_404_sin_registro(sesion, metodo):
    respuesta = PETICIONES[metodo](sesion, f"{URL}/{uuid.uuid4()}")

    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.parametrize("nombre", sorted(_terceros_sin_rol()))
def test_la_lista_exige_el_rol_maestro(nombre):
    crear, identificador = _terceros_sin_rol()[nombre]
    crear()

    respuesta = _sesion(identificador).get(URL)

    assert respuesta.status_code == 403
    assert RegistroAccesoDenegado.objects.get().entidad == "ruta"


def test_la_lista_es_solo_del_maestro_de_la_sesion(sesion, maestro, gas):
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    expedientes.declarar_oficios(_expediente(otro), ["gas"])
    _ofrecido(otro, gas)

    respuesta = sesion.get(URL)

    assert respuesta.json()["servicios"] == []
    assert_campos_ausentes(respuesta, {"id", "rut", "telefono", "correo"}, valores=["222222222"])


@pytest.mark.parametrize(("metodo", "url"), [("put", URL), ("delete", URL), ("get", "ref"), ("post", "ref")])
def test_metodos_no_permitidos_responden_405(sesion, maestro, gas, metodo, url):
    ofrecido = _ofrecido(maestro, gas)
    destino = f"{URL}/{ofrecido.ref}" if url == "ref" else url

    assert getattr(sesion, metodo)(destino).status_code == 405


def test_los_errores_del_maestro_no_tienen_texto_de_programador(sesion, gas):
    respuestas = [
        post_json(sesion, URL, {}),
        post_json(sesion, URL, {"servicio": str(gas.ref), "modalidad": "x", "monto": "x"}),
        post_json(sesion, URL, {"otro": 1}),
    ]
    assert all(r.status_code == 400 for r in respuestas)
    assert all(sin_texto_prohibido(r) for r in respuestas)
