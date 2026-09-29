"""Catálogo administrable, incremento 1 del S3 (RF-36, RF-37, HU-20, CA-20.2, RNF-07, RNF-11; ADR-018).

- Migraciones: ``ref`` distinto por fila (trampa de ``AddField`` con
  ``default=uuid4``) y ninguna migración posterior a 0003 recarga el CSV (D-3).
- Restricciones de la base de datos de ``servicio`` y ``servicio_modalidad``.
- Lecturas públicas con lista explícita de campos, ``no-cache`` y ``ETag`` (D-16).
- Casos de uso de comercial: ``regulado`` obligatorio e inmutable (D-2),
  versión (409), motivo y bitácora en la misma transacción (D-4).
- Terceros por ruta (RNF-07): roles no comerciales 403 registrado, anónimo 401,
  referencia inexistente 404 sin registro.
- Comando ``cargar_datos_demo``: idempotente y rotulado.

Datos ficticios (@example.com, RUT sintéticos).
"""
import importlib
import io
import json
import re
import uuid
from pathlib import Path

import pytest
from django.apps import apps as registro_apps
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client

from autorizacion.middleware import MENSAJE_SIN_ROL
from autorizacion.models import RegistroAccesoDenegado
from bitacora import servicios as servicios_bitacora
from bitacora.models import AutorTipo, Bitacora
from catalogo import servicios
from catalogo.errores import ErrorVersion
from catalogo.management.commands.cargar_datos_demo import ROTULO, SERVICIOS_DEMO, cargar_datos_demo
from catalogo.models import Modalidad, Oficio, Servicio, ServicioModalidad
from comun.api import ErroresDeCampo, respuesta_no_encontrado
from identidad import servicios as servicios_identidad
from identidad.models import Rol
from tests.ayudas import CONTRASENA, TEL_B, crear_cliente, crear_maestro, iniciar_sesion, post_json, sin_texto_prohibido
from tests.privacidad import assert_campos_ausentes

pytestmark = pytest.mark.django_db

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
NO_ENCONTRADO = respuesta_no_encontrado().content

URL_CATALOGO = "/api/catalogo"
URL_OFICIOS = "/api/oficios"
URL_COMERCIAL = "/api/comercial/catalogo"
URL_OFICIOS_COMERCIAL = "/api/comercial/oficios"
URL_SERVICIOS_COMERCIAL = "/api/comercial/servicios"
CORREO_COMERCIAL = "comercial@example.com"
T, H = Modalidad.POR_TRABAJO, Modalidad.POR_HORA


# --- Ayudas ---


def _administrativo(rol, correo):
    return servicios_identidad.crear_cuenta_administrativa(
        nombre="Admin Prueba", correo=correo, roles=[rol], contrasena=CONTRASENA
    )


def _sesion(identificador):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


@pytest.fixture
def comercial_usuario():
    return _administrativo(Rol.COMERCIAL, CORREO_COMERCIAL)


@pytest.fixture
def comercial(comercial_usuario):
    return _sesion(CORREO_COMERCIAL)


def _patch(client, url, datos):
    return client.patch(url, data=json.dumps(datos), content_type="application/json")


def _servicio(oficio="pintura", nombre="Pintura de muro", modalidades=None, activo=True, orden=1):
    servicio = Servicio.objects.create(
        oficio=Oficio.objects.get(codigo=oficio), nombre=nombre, activo=activo, orden=orden
    )
    for modalidad, precio in (modalidades or {T: 30000}).items():
        ServicioModalidad.objects.create(servicio=servicio, modalidad=modalidad, precio_referencia=precio)
    return servicio


def _url_oficio(ref):
    return f"{URL_OFICIOS_COMERCIAL}/{ref}"


def _url_servicio(ref):
    return f"{URL_SERVICIOS_COMERCIAL}/{ref}"


# --- Migraciones (ADR-018; propuesta del S3, §3) ---


def test_cada_oficio_tiene_un_ref_distinto_y_no_nulo():
    refs = list(Oficio.objects.values_list("ref", flat=True))
    assert len(refs) == 8
    assert None not in refs
    assert len(set(refs)) == len(refs)


def test_el_primer_paso_agrega_ref_sin_valor_por_defecto_y_el_segundo_llena_uno_por_fila():
    paso_1 = importlib.import_module("catalogo.migrations.0004_oficio_ref_activo_version")
    (agregar_ref,) = [op for op in paso_1.Migration.operations if op.name == "ref"]
    assert agregar_ref.field.null is True
    assert not agregar_ref.field.has_default()

    # Paso 2 idempotente: no toca filas que ya tienen ref (la columna ya es NOT NULL).
    paso_2 = importlib.import_module("catalogo.migrations.0005_oficio_llena_ref")
    antes = dict(Oficio.objects.values_list("pk", "ref"))
    paso_2.llenar_ref(registro_apps, None)
    assert dict(Oficio.objects.values_list("pk", "ref")) == antes

    paso_3 = importlib.import_module("catalogo.migrations.0006_oficio_ref_unico")
    (alterar,) = paso_3.Migration.operations
    assert alterar.field.unique and not alterar.field.null


def _migraciones_de_datos():
    for ruta in sorted(RAIZ_BACKEND.glob("*/migrations/[0-9]*.py")):
        yield ruta.parent.parent.name, ruta.name, ruta.read_text(encoding="utf-8")


def test_ninguna_migracion_posterior_a_0003_recarga_el_csv_de_oficios():
    """ADR-018, punto 3 (D-3): el CSV es solo la carga inicial."""
    recargan = []
    for app, nombre, fuente in _migraciones_de_datos():
        if app == "catalogo" and int(nombre[:4]) <= 3:
            continue
        patron = r"catalogo\.carga|from catalogo import carga|oficios\.csv"
        if app == "catalogo":
            patron += r"|leer_filas|cargar\("
        if re.search(patron, fuente):
            recargan.append(f"{app}/{nombre}")
    assert recargan == []
    # Resguardo: la búsqueda sí detecta las que cargan el CSV.
    fuentes = {(app, nombre): fuente for app, nombre, fuente in _migraciones_de_datos()}
    assert "leer_filas" in fuentes[("catalogo", "0002_carga_oficios.py")]


# --- Restricciones de la base de datos ---


def _falla_en_bd(funcion):
    with pytest.raises(IntegrityError), transaction.atomic():
        funcion()


def test_la_bd_rechaza_modalidad_fuera_de_la_lista_y_precio_no_positivo():
    servicio = _servicio()
    _falla_en_bd(lambda: ServicioModalidad.objects.create(servicio=servicio, modalidad="por_dia", precio_referencia=1))
    _falla_en_bd(lambda: ServicioModalidad.objects.create(servicio=servicio, modalidad=H, precio_referencia=0))
    _falla_en_bd(lambda: ServicioModalidad.objects.create(servicio=servicio, modalidad=H, precio_referencia=10_000_001))


def test_la_bd_exige_nombre_unico_por_oficio_y_modalidad_unica_por_servicio():
    servicio = _servicio()
    _falla_en_bd(lambda: _servicio(nombre="Pintura de muro"))
    _falla_en_bd(lambda: ServicioModalidad.objects.create(servicio=servicio, modalidad=T, precio_referencia=5))
    # El mismo nombre en otro oficio sí se permite.
    _servicio(oficio="carpinteria", nombre="Pintura de muro")


def test_no_se_borra_un_oficio_con_servicios_ni_un_servicio_con_modalidades():
    servicio = _servicio()
    _falla_en_bd(lambda: Oficio.objects.filter(codigo="pintura").delete())
    _falla_en_bd(lambda: Servicio.objects.filter(pk=servicio.pk).delete())


# --- Lecturas públicas (CA-20.2; D-16) ---


def test_el_catalogo_publico_muestra_solo_lo_activo_con_lista_explicita_de_campos(client):
    visible = _servicio(modalidades={T: 30000, H: 9000})
    _servicio(nombre="Servicio dado de baja", activo=False, orden=2)
    _servicio(oficio="gas", nombre="Servicio de oficio inactivo")
    Oficio.objects.filter(codigo="gas").update(activo=False)

    respuesta = client.get(URL_CATALOGO)

    assert respuesta.status_code == 200
    oficios = respuesta.json()["oficios"]
    assert "gas" not in [o["codigo"] for o in oficios]
    assert all(set(o) == {"codigo", "nombre", "regulado", "servicios"} for o in oficios)
    (pintura,) = [o for o in oficios if o["codigo"] == "pintura"]
    assert pintura["servicios"] == [
        {
            "ref": str(visible.ref),
            "nombre": "Pintura de muro",
            "modalidades": [
                {"modalidad": H, "precio_referencia": 9000},
                {"modalidad": T, "precio_referencia": 30000},
            ],
        }
    ]
    assert_campos_ausentes(respuesta, {"id", "pk", "version", "activo", "orden", "rut", "telefono", "correo"})


@pytest.mark.parametrize("url", [URL_CATALOGO, URL_OFICIOS])
def test_las_lecturas_publicas_revalidan_con_etag_y_no_cache(client, url):
    primera = client.get(url)
    assert primera["Cache-Control"] == "no-cache"
    etag = primera["ETag"]
    assert re.fullmatch(r'"[0-9a-f]{32}"', etag)

    igual = client.get(url, HTTP_IF_NONE_MATCH=etag)
    assert igual.status_code == 304
    assert igual.content == b""
    assert igual["ETag"] == etag

    Oficio.objects.filter(codigo="pintura").update(nombre="Pintura y barnizado")
    cambiado = client.get(url, HTTP_IF_NONE_MATCH=etag)
    assert cambiado.status_code == 200
    assert cambiado["ETag"] != etag
    assert "Pintura y barnizado" in cambiado.content.decode("utf-8")


def test_oficios_no_lista_un_oficio_dado_de_baja(client):
    Oficio.objects.filter(codigo="jardineria").update(activo=False)

    codigos = [o["codigo"] for o in client.get(URL_OFICIOS).json()["oficios"]]

    assert "jardineria" not in codigos
    assert len(codigos) == 7


@pytest.mark.parametrize("url", [URL_CATALOGO, URL_OFICIOS])
@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_las_lecturas_publicas_son_de_solo_lectura(client, url, metodo):
    assert getattr(client, metodo)(url).status_code == 405


# --- Comercial: oficios ---


def test_comercial_crea_un_oficio_con_bitacora(comercial, comercial_usuario):
    respuesta = post_json(comercial, URL_OFICIOS_COMERCIAL, {"nombre": "  Techumbre  ", "regulado": False})

    assert respuesta.status_code == 201
    datos = respuesta.json()["oficio"]
    assert set(datos) == {"ref", "codigo", "nombre", "regulado", "orden", "activo", "version"}
    assert (datos["codigo"], datos["nombre"], datos["regulado"], datos["orden"]) == ("techumbre", "Techumbre", False, 9)
    assert (datos["activo"], datos["version"]) == (True, 1)
    entrada = Bitacora.objects.get()
    assert (entrada.autor_tipo, entrada.autor_id) == (AutorTipo.USUARIO, comercial_usuario.pk)
    assert (entrada.accion, entrada.entidad, entrada.entidad_ref) == ("catalogo.oficio.crear", "oficio", datos["ref"])
    assert entrada.valor_anterior is None
    assert entrada.valor_nuevo == {
        "codigo": "techumbre", "nombre": "Techumbre", "regulado": False, "orden": 9, "activo": True,
    }
    assert entrada.motivo == servicios.MOTIVO_ALTA_OFICIO


def test_el_motivo_fijo_del_alta_se_puede_completar(comercial):
    post_json(comercial, URL_OFICIOS_COMERCIAL, {"nombre": "Vidriería", "regulado": False, "motivo": "Pedido de la red"})

    assert Bitacora.objects.get().motivo == f"{servicios.MOTIVO_ALTA_OFICIO}. Pedido de la red"
    assert Oficio.objects.get(nombre="Vidriería").codigo == "vidrieria"


@pytest.mark.parametrize("regulado", [None, "si", 1, "true"])
def test_regulado_es_obligatorio_y_booleano_al_crear(comercial, regulado):
    datos = {"nombre": "Techumbre"}
    if regulado is not None:
        datos["regulado"] = regulado

    respuesta = post_json(comercial, URL_OFICIOS_COMERCIAL, datos)

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"regulado": servicios.MENSAJE_REGULADO_FALTA}
    assert Oficio.objects.count() == 8
    assert not Bitacora.objects.exists()


def test_no_se_crea_un_oficio_con_nombre_repetido(comercial):
    respuesta = post_json(comercial, URL_OFICIOS_COMERCIAL, {"nombre": "gas", "regulado": True})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"nombre": servicios.MENSAJE_OFICIO_REPETIDO}
    assert not Bitacora.objects.exists()


def test_el_codigo_derivado_no_se_repite():
    usuario = _administrativo(Rol.COMERCIAL, CORREO_COMERCIAL)
    Oficio.objects.filter(codigo="pintura").update(nombre="Pintura antigua")

    oficio = servicios.crear_oficio(usuario, {"nombre": "Pintura", "regulado": False})

    assert oficio.codigo == "pintura_2"


def test_comercial_modifica_un_oficio_con_version_motivo_y_bitacora(comercial, comercial_usuario):
    oficio = Oficio.objects.get(codigo="pintura")

    respuesta = _patch(
        comercial, _url_oficio(oficio.ref), {"version": 1, "motivo": "Nombre más claro", "nombre": "Pintura y barniz"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["oficio"]["version"] == 2
    oficio.refresh_from_db()
    assert (oficio.nombre, oficio.version) == ("Pintura y barniz", 2)
    entrada = Bitacora.objects.get()
    assert (entrada.autor_id, entrada.accion, entrada.entidad, entrada.entidad_ref) == (
        comercial_usuario.pk, "catalogo.oficio.modificar", "oficio", str(oficio.ref),
    )
    assert entrada.valor_anterior["nombre"] == "Pintura"
    assert entrada.valor_nuevo["nombre"] == "Pintura y barniz"
    assert set(entrada.valor_nuevo) == {"codigo", "nombre", "regulado", "orden", "activo"}
    assert entrada.motivo == "Nombre más claro"


def test_dar_de_baja_un_oficio_es_logico_y_exige_motivo(comercial):
    oficio = Oficio.objects.get(codigo="jardineria")

    sin_motivo = _patch(comercial, _url_oficio(oficio.ref), {"version": 1, "activo": False})
    assert sin_motivo.status_code == 400
    assert sin_motivo.json()["errores"] == {"motivo": servicios.MENSAJE_MOTIVO_FALTA}

    baja = _patch(comercial, _url_oficio(oficio.ref), {"version": 1, "activo": False, "motivo": "Sin maestros"})
    assert baja.status_code == 200
    oficio.refresh_from_db()
    assert oficio.activo is False
    assert Bitacora.objects.get().valor_nuevo["activo"] is False


@pytest.mark.parametrize("regulado", [True, False])
def test_d2_regulado_no_se_cambia_desde_la_aplicacion(comercial, regulado):
    oficio = Oficio.objects.get(codigo="gas")

    respuesta = _patch(comercial, _url_oficio(oficio.ref), {"version": 1, "motivo": "x", "regulado": regulado})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"regulado": servicios.MENSAJE_REGULADO_INMUTABLE}
    oficio.refresh_from_db()
    assert (oficio.regulado, oficio.version) == (True, 1)
    assert not Bitacora.objects.exists()


def test_d4_version_distinta_responde_409_sin_cambios_ni_bitacora(comercial):
    oficio = Oficio.objects.get(codigo="pintura")
    Oficio.objects.filter(pk=oficio.pk).update(version=3)

    respuesta = _patch(comercial, _url_oficio(oficio.ref), {"version": 2, "motivo": "x", "nombre": "Otro"})

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == servicios.MENSAJE_VERSION
    oficio.refresh_from_db()
    assert (oficio.nombre, oficio.version) == ("Pintura", 3)
    assert not Bitacora.objects.exists()


@pytest.mark.parametrize("version", [None, "1", 0, True])
def test_la_version_es_obligatoria_al_modificar(comercial, version):
    oficio = Oficio.objects.get(codigo="pintura")
    datos = {"motivo": "x", "nombre": "Otro"}
    if version is not None:
        datos["version"] = version

    respuesta = _patch(comercial, _url_oficio(oficio.ref), datos)

    assert respuesta.status_code == 400
    assert "version" in respuesta.json()["errores"]
    assert not Bitacora.objects.exists()


def test_modificar_sin_cambios_responde_400_general_sin_bitacora(comercial):
    oficio = Oficio.objects.get(codigo="pintura")

    for datos in ({"version": 1, "motivo": "x"}, {"version": 1, "motivo": "x", "nombre": "Pintura"}):
        respuesta = _patch(comercial, _url_oficio(oficio.ref), datos)
        assert respuesta.status_code == 400
        assert respuesta.json() == {"mensaje": servicios.MENSAJE_SIN_CAMBIOS, "errores": {}}
    assert Oficio.objects.get(pk=oficio.pk).version == 1
    assert not Bitacora.objects.exists()


def test_d4_si_la_bitacora_falla_no_queda_el_cambio_ni_la_fila(monkeypatch, comercial_usuario):
    oficio = Oficio.objects.get(codigo="pintura")

    def fallar(**kwargs):
        raise servicios_bitacora.ErrorBitacora("forzado")

    monkeypatch.setattr(servicios_bitacora, "registrar", fallar)
    with pytest.raises(servicios_bitacora.ErrorBitacora):
        servicios.modificar_oficio(comercial_usuario, oficio, {"version": 1, "motivo": "x", "nombre": "Otro"})
    with pytest.raises(servicios_bitacora.ErrorBitacora):
        servicios.crear_servicio(
            comercial_usuario,
            {"oficio": "pintura", "nombre": "Nuevo", "modalidades": [{"modalidad": T, "precio_referencia": 1}]},
        )

    oficio.refresh_from_db()
    assert (oficio.nombre, oficio.version) == ("Pintura", 1)
    assert not Servicio.objects.exists()
    assert not ServicioModalidad.objects.exists()
    assert not Bitacora.objects.exists()


# --- Comercial: servicios (CA-20.2) ---


def _crear_servicio(comercial, **cambios):
    datos = {
        "oficio": "pintura",
        "nombre": "Pintura de reja",
        "modalidades": [{"modalidad": T, "precio_referencia": 40000}],
    }
    datos.update(cambios)
    return post_json(comercial, URL_SERVICIOS_COMERCIAL, datos)


def test_comercial_crea_un_servicio_con_modalidades_y_bitacora(comercial, comercial_usuario):
    respuesta = _crear_servicio(
        comercial,
        modalidades=[{"modalidad": T, "precio_referencia": 40000}, {"modalidad": H, "precio_referencia": 12000}],
    )

    assert respuesta.status_code == 201
    datos = respuesta.json()["servicio"]
    assert set(datos) == {"ref", "oficio", "nombre", "orden", "activo", "version", "modalidades"}
    assert datos["modalidades"] == [
        {"modalidad": H, "precio_referencia": 12000}, {"modalidad": T, "precio_referencia": 40000},
    ]
    entrada = Bitacora.objects.get()
    assert (entrada.autor_id, entrada.accion, entrada.entidad, entrada.entidad_ref) == (
        comercial_usuario.pk, "catalogo.servicio.crear", "servicio", datos["ref"],
    )
    assert entrada.valor_nuevo == {
        "oficio": "pintura", "nombre": "Pintura de reja", "orden": 1, "activo": True,
        "modalidades": datos["modalidades"],
    }


@pytest.mark.parametrize(
    "modalidades",
    [
        None,
        [],
        [{"modalidad": "por_dia", "precio_referencia": 1}],
        [{"modalidad": T, "precio_referencia": 0}],
        [{"modalidad": T, "precio_referencia": -5}],
        [{"modalidad": T, "precio_referencia": 10_000_001}],
        [{"modalidad": T, "precio_referencia": "1000"}],
        [{"modalidad": T, "precio_referencia": 1.5}],
        [{"modalidad": T, "precio_referencia": True}],
        [{"modalidad": T, "precio_referencia": 1}, {"modalidad": T, "precio_referencia": 2}],
        [{"modalidad": T}],
        [{"modalidad": T, "precio_referencia": 1, "extra": 1}],
        ["por_trabajo"],
        {"modalidad": T, "precio_referencia": 1},
    ],
)
def test_un_servicio_exige_al_menos_una_modalidad_valida(comercial, modalidades):
    datos = {"oficio": "pintura", "nombre": "Pintura de reja"}
    if modalidades is not None:
        datos["modalidades"] = modalidades

    respuesta = post_json(comercial, URL_SERVICIOS_COMERCIAL, datos)

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"modalidades": servicios.MENSAJE_MODALIDADES}
    assert not Servicio.objects.exists()
    assert not Bitacora.objects.exists()


def test_el_precio_de_referencia_acepta_el_tope(comercial):
    respuesta = _crear_servicio(comercial, modalidades=[{"modalidad": H, "precio_referencia": 10_000_000}])

    assert respuesta.status_code == 201


def test_crear_servicio_valida_oficio_y_nombre(comercial):
    for datos, campo in (({"oficio": "no_existe"}, "oficio"), ({"oficio": 5}, "oficio"), ({"nombre": "   "}, "nombre")):
        respuesta = _crear_servicio(comercial, **datos)
        assert respuesta.status_code == 400
        assert set(respuesta.json()["errores"]) == {campo}
    _servicio(nombre="Pintura de reja")
    repetido = _crear_servicio(comercial, nombre="PINTURA DE REJA")
    assert repetido.json()["errores"] == {"nombre": servicios.MENSAJE_SERVICIO_REPETIDO}


def test_ca20_2_comercial_cambia_un_precio_y_el_visitante_ve_el_valor_actualizado(comercial, comercial_usuario):
    servicio = _servicio(modalidades={T: 30000})
    visitante = Client()
    antes = visitante.get(URL_CATALOGO)
    etag = antes["ETag"]

    respuesta = _patch(
        comercial,
        _url_servicio(servicio.ref),
        {"version": 1, "motivo": "Ajuste de mercado", "modalidades": [{"modalidad": T, "precio_referencia": 35000}]},
    )

    assert respuesta.status_code == 200
    # La caché no lo impide: con el ETag anterior, el navegador recibe el nuevo contenido.
    despues = visitante.get(URL_CATALOGO, HTTP_IF_NONE_MATCH=etag)
    assert despues.status_code == 200
    (pintura,) = [o for o in despues.json()["oficios"] if o["codigo"] == "pintura"]
    assert pintura["servicios"][0]["modalidades"] == [{"modalidad": T, "precio_referencia": 35000}]
    entrada = Bitacora.objects.get()
    assert (entrada.accion, entrada.entidad, entrada.entidad_ref, entrada.autor_id) == (
        "catalogo.servicio.modificar", "servicio", str(servicio.ref), comercial_usuario.pk,
    )
    assert entrada.valor_anterior["modalidades"] == [{"modalidad": T, "precio_referencia": 30000}]
    assert entrada.valor_nuevo["modalidades"] == [{"modalidad": T, "precio_referencia": 35000}]
    assert entrada.motivo == "Ajuste de mercado"


def test_las_modalidades_se_reemplazan_completas(comercial):
    servicio = _servicio(modalidades={T: 30000, H: 9000})

    _patch(
        comercial,
        _url_servicio(servicio.ref),
        {"version": 1, "motivo": "Solo por hora", "modalidades": [{"modalidad": H, "precio_referencia": 9500}]},
    )

    assert list(ServicioModalidad.objects.filter(servicio=servicio).values_list("modalidad", "precio_referencia")) == [
        (H, 9500)
    ]


def test_el_oficio_de_un_servicio_no_se_cambia(comercial):
    servicio = _servicio()

    respuesta = _patch(comercial, _url_servicio(servicio.ref), {"version": 1, "motivo": "x", "oficio": "gas"})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"oficio": servicios.MENSAJE_OFICIO_INMUTABLE}
    assert Servicio.objects.get(pk=servicio.pk).oficio.codigo == "pintura"
    assert not Bitacora.objects.exists()


def test_baja_de_servicio_con_version_y_motivo(comercial):
    servicio = _servicio()

    conflicto = _patch(comercial, _url_servicio(servicio.ref), {"version": 7, "motivo": "x", "activo": False})
    assert conflicto.status_code == 409
    baja = _patch(comercial, _url_servicio(servicio.ref), {"version": 1, "motivo": "Ya no se ofrece", "activo": False})
    assert baja.status_code == 200
    servicio.refresh_from_db()
    assert (servicio.activo, servicio.version) == (False, 2)
    assert Servicio.objects.filter(pk=servicio.pk).exists()
    assert Bitacora.objects.count() == 1


def test_el_catalogo_comercial_incluye_inactivos_y_version(comercial):
    _servicio(nombre="Dado de baja", activo=False)
    Oficio.objects.filter(codigo="gas").update(activo=False)

    respuesta = comercial.get(URL_COMERCIAL)

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    oficios = {o["codigo"]: o for o in respuesta.json()["oficios"]}
    assert len(oficios) == 8
    assert oficios["gas"]["activo"] is False
    assert oficios["pintura"]["servicios"][0]["nombre"] == "Dado de baja"
    assert oficios["pintura"]["servicios"][0]["version"] == 1
    assert_campos_ausentes(respuesta, {"id", "pk", "rut", "telefono", "correo"})


@pytest.mark.parametrize("cuerpo", [{"nombre": "X", "regulado": False, "otro": 1}, {"nombre": "X", "regulado": False, "activo": True}])
def test_campos_no_permitidos_al_crear_oficio(comercial, cuerpo):
    respuesta = post_json(comercial, URL_OFICIOS_COMERCIAL, cuerpo)

    assert respuesta.status_code == 400
    assert Oficio.objects.count() == 8


def test_los_mensajes_de_comercial_no_tienen_texto_de_programador(comercial):
    oficio = Oficio.objects.get(codigo="pintura")
    respuestas = [
        post_json(comercial, URL_OFICIOS_COMERCIAL, {}),
        post_json(comercial, URL_SERVICIOS_COMERCIAL, {}),
        _patch(comercial, _url_oficio(oficio.ref), {"version": 9, "motivo": "x", "nombre": "Y"}),
        _patch(comercial, _url_oficio(oficio.ref), {"regulado": True}),
    ]
    assert all(r.status_code in (400, 409) for r in respuestas)
    assert all(sin_texto_prohibido(r) for r in respuestas)


# --- Terceros por ruta (RNF-07, HU-25) ---


def _terceros():
    return {
        "cliente": (lambda: crear_cliente(), "ana.prueba@example.com"),
        "maestro": (lambda: crear_maestro(rut="22.222.222-2", telefono=TEL_B), "22.222.222-2"),
        "curatoria": (lambda: _administrativo(Rol.CURATORIA, "cura@example.com"), "cura@example.com"),
        "moderacion": (lambda: _administrativo(Rol.MODERACION, "moderacion@example.com"), "moderacion@example.com"),
        "control_gestion": (
            lambda: _administrativo(Rol.CONTROL_GESTION, "gestion@example.com"), "gestion@example.com"
        ),
    }


TERCEROS = sorted(_terceros())
RUTAS_CON_REF = ["comercial_modificar_oficio", "comercial_modificar_servicio"]


def _peticion(ruta):
    if ruta == "comercial_modificar_oficio":
        return _url_oficio(Oficio.objects.get(codigo="pintura").ref), {"version": 1, "motivo": "x", "nombre": "Y"}
    servicio = Servicio.objects.get() if Servicio.objects.exists() else _servicio()
    return _url_servicio(servicio.ref), {"version": 1, "motivo": "x", "nombre": "Y"}


def _sin_cambios():
    assert Oficio.objects.get(codigo="pintura").nombre == "Pintura"
    assert not Servicio.objects.exclude(nombre="Pintura de muro").exists()
    assert not Bitacora.objects.exists()


@pytest.mark.terceros("comercial_modificar_oficio")
@pytest.mark.terceros("comercial_modificar_servicio")
@pytest.mark.parametrize("ruta", RUTAS_CON_REF)
@pytest.mark.parametrize("nombre", TERCEROS)
def test_un_rol_no_comercial_recibe_403_registrado_sin_efectos(ruta, nombre):
    crear, identificador = _terceros()[nombre]
    tercero = crear()
    url, cuerpo = _peticion(ruta)

    respuesta = _patch(_sesion(identificador), url, cuerpo)

    assert respuesta.status_code == 403
    assert respuesta.json() == {"mensaje": MENSAJE_SIN_ROL, "errores": {}}
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "ruta", None)
    _sin_cambios()


@pytest.mark.terceros("comercial_modificar_oficio")
@pytest.mark.terceros("comercial_modificar_servicio")
@pytest.mark.parametrize("ruta", RUTAS_CON_REF)
def test_anonimo_recibe_401_sin_registro(ruta):
    url, cuerpo = _peticion(ruta)

    respuesta = _patch(Client(), url, cuerpo)

    assert respuesta.status_code == 401
    assert not RegistroAccesoDenegado.objects.exists()
    _sin_cambios()


@pytest.mark.terceros("comercial_modificar_oficio")
@pytest.mark.terceros("comercial_modificar_servicio")
@pytest.mark.parametrize("ruta", RUTAS_CON_REF)
def test_referencia_inexistente_responde_404_neutro_sin_registro(comercial, ruta):
    url, cuerpo = _peticion(ruta)
    url = url.rsplit("/", 1)[0] + f"/{uuid.uuid4()}"

    respuesta = _patch(comercial, url, cuerpo)

    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()
    _sin_cambios()


@pytest.mark.parametrize(
    ("metodo", "url"),
    [("get", URL_COMERCIAL), ("post", URL_OFICIOS_COMERCIAL), ("post", URL_SERVICIOS_COMERCIAL)],
)
@pytest.mark.parametrize("nombre", TERCEROS)
def test_las_rutas_sin_ref_de_comercial_exigen_el_rol(metodo, url, nombre):
    crear, identificador = _terceros()[nombre]
    crear()

    client = _sesion(identificador)
    respuesta = client.get(url) if metodo == "get" else post_json(client, url, {})

    assert respuesta.status_code == 403
    assert RegistroAccesoDenegado.objects.get().entidad == "ruta"


@pytest.mark.parametrize(
    ("metodo", "url"),
    [("post", URL_COMERCIAL), ("get", URL_OFICIOS_COMERCIAL), ("put", URL_SERVICIOS_COMERCIAL), ("get", "oficio"),
     ("delete", "oficio"), ("post", "servicio"), ("delete", "servicio")],
)
def test_metodos_no_permitidos_responden_405(comercial, metodo, url):
    urls = {"oficio": _url_oficio(uuid.uuid4()), "servicio": _url_servicio(uuid.uuid4())}

    assert getattr(comercial, metodo)(urls.get(url, url)).status_code == 405
    assert not Bitacora.objects.exists()


# --- Comando de datos de demostración ---


def test_el_comando_de_demo_es_idempotente_rotulado_y_no_pisa_cambios():
    creados = cargar_datos_demo()
    assert creados == len(SERVICIOS_DEMO)
    assert all(nombre.endswith(ROTULO) for nombre in Servicio.objects.values_list("nombre", flat=True))
    assert all(Servicio.objects.get(nombre=n + ROTULO).modalidades.exists() for _, n, _ in SERVICIOS_DEMO)
    ServicioModalidad.objects.filter(servicio__nombre="Pintura de habitación" + ROTULO).update(precio_referencia=1)

    salida = io.StringIO()
    call_command("cargar_datos_demo", stdout=salida)

    assert "0" in salida.getvalue()

    assert Servicio.objects.count() == len(SERVICIOS_DEMO)
    assert ServicioModalidad.objects.get(servicio__nombre="Pintura de habitación" + ROTULO).precio_referencia == 1
    assert not Bitacora.objects.exists()


def test_ninguna_migracion_llama_al_comando_de_demo():
    for app, nombre, fuente in _migraciones_de_datos():
        assert "cargar_datos_demo" not in fuente, f"{app}/{nombre}"


def test_las_vistas_de_comercial_no_escriben_la_bitacora_directamente():
    """RNF-11: la bitácora se escribe solo con ``bitacora.servicios.registrar`` desde el servicio de dominio."""
    fuente = (RAIZ_BACKEND / "catalogo" / "vistas_comercial.py").read_text(encoding="utf-8")
    assert "Bitacora" not in fuente
    assert "registrar" not in fuente


def test_errores_de_campo_y_version_son_excepciones_sin_efectos(comercial_usuario):
    with pytest.raises(ErroresDeCampo):
        servicios.crear_oficio(comercial_usuario, {"nombre": ""})
    oficio = Oficio.objects.get(codigo="pintura")
    with pytest.raises(ErrorVersion):
        servicios.modificar_oficio(comercial_usuario, oficio, {"version": 2, "motivo": "x", "orden": 3})
    assert not Bitacora.objects.exists()
