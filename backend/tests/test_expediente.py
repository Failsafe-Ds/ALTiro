"""Expediente del maestro, incremento 1 del S2 (ADR-017; propuesta del S2, §3 y §4).

- Invariante perfil_maestro <=> expediente (ADR-017, punto 2): se crea en la
  misma transacción del perfil, sin sesión y agregando el perfil con sesión.
- Declaración de oficios (solo en ``en_revision`` u ``observado``).
- GET y POST del propio expediente (patrón "me", ADR-011): sin identificador
  en la ruta, así que la prueba de terceros de RNF-07 no les aplica.
- Faltantes para aprobar (ADR-017, punto 3) y "hoy" de negocio (ADR-016, punto 3).
Datos ficticios: RUT sintéticos, correos @example.com y teléfonos +56 9 1000 000N.
"""
import datetime
import importlib
import uuid

import pytest
from django.apps import apps as registro_de_apps
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from autorizacion.models import RegistroAccesoDenegado
from expediente import servicios as expedientes
from expediente.errores import ErrorEstado
from expediente.models import EstadoExpediente, Expediente, OficioMaestro
from expediente.servicios import declarar_oficios
from expediente.vigencia import (
    ANTECEDENTES,
    CEDULA,
    LICENCIA_SEC,
    faltantes_para_aprobar,
    hoy_negocio,
    vigente,
)
from identidad.errores import ErrorValidacion, InvarianteVioladaError
from identidad.models import PerfilMaestro, Rol, Usuario, UsuarioRol
from identidad.servicios import agregar_perfil_maestro, crear_cuenta_administrativa, verificar_invariantes
from tests.privacidad import assert_campos_ausentes
from tests.ayudas import (
    CONTRASENA,
    TEL_B,
    crear_cliente,
    crear_maestro,
    iniciar_sesion,
    post_json,
    sin_texto_prohibido,
)

URL_EXPEDIENTE = "/api/maestros/expediente"
URL_OFICIOS_EXPEDIENTE = "/api/maestros/expediente/oficios"
RUT_PROPIO = "11.111.111-1"
RUT_OTRO = "22.222.222-2"


@pytest.fixture(autouse=True)
def invariantes_al_final(request):
    """Al terminar cada prueba, todas las cuentas cumplen ADR-013 §9 y perfil_maestro <=> expediente."""
    yield
    if request.node.get_closest_marker("django_db") is None:
        return
    for usuario in Usuario.objects.all():
        assert verificar_invariantes(usuario) == [], f"usuario {usuario.pk}"


def _expediente_de(usuario):
    return Expediente.objects.get(perfil_maestro_id=usuario.pk)


def _codigos(usuario):
    return set(OficioMaestro.objects.filter(maestro_id=usuario.pk).values_list("oficio__codigo", flat=True))


def _con_estado(usuario, estado):
    Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(estado=estado)


@pytest.fixture
def maestro():
    return crear_maestro(rut=RUT_PROPIO)


@pytest.fixture
def navegador_maestro(client, maestro):
    assert iniciar_sesion(client, RUT_PROPIO).status_code == 200
    return client


# --- Creación junto con perfil_maestro (ADR-017, punto 2) ---


@pytest.mark.django_db
def test_postular_sin_sesion_crea_el_expediente_en_revision(client):
    respuesta = post_json(
        client,
        "/api/maestros/postulaciones",
        {"rut": RUT_PROPIO, "nombre": "Maestro Uno", "telefono": "+56 9 1000 0001", "contrasena": CONTRASENA},
    )

    assert respuesta.status_code == 201
    usuario = PerfilMaestro.objects.get(rut="111111111").usuario
    expediente = _expediente_de(usuario)
    assert expediente.estado == EstadoExpediente.EN_REVISION
    assert expediente.estado_motivo == ""
    assert expediente.estado_cambiado_por is None and expediente.estado_cambiado_en is None
    assert isinstance(expediente.ref, uuid.UUID) and expediente.ref.version == 4


@pytest.mark.django_db
def test_agregar_perfil_maestro_con_sesion_crea_el_expediente(client):
    cliente = crear_cliente()
    assert iniciar_sesion(client, "ana.prueba@example.com").status_code == 200

    respuesta = post_json(client, "/api/maestros/postulaciones", {"rut": RUT_PROPIO})

    assert respuesta.status_code == 201
    assert _expediente_de(cliente).estado == EstadoExpediente.EN_REVISION
    assert Expediente.objects.count() == 1


@pytest.mark.django_db
def test_cliente_y_administrador_no_tienen_expediente():
    crear_cliente()
    crear_cuenta_administrativa(
        nombre="Admin Prueba", correo="admin@example.com", roles=["curatoria"], contrasena=CONTRASENA
    )

    assert Expediente.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("via", ["sin_sesion", "con_sesion"])
def test_si_falla_la_creacion_del_expediente_se_revierte_todo(monkeypatch, via):
    cliente = crear_cliente() if via == "con_sesion" else None

    def falla(perfil):
        raise RuntimeError("falla forzada")

    monkeypatch.setattr(expedientes, "crear_para", falla)
    with pytest.raises(RuntimeError):
        if via == "sin_sesion":
            crear_maestro(rut=RUT_PROPIO)
        else:
            agregar_perfil_maestro(cliente, rut=RUT_PROPIO)

    assert not PerfilMaestro.objects.exists()
    assert not UsuarioRol.objects.filter(rol=Rol.MAESTRO).exists()
    assert Usuario.objects.count() == (1 if cliente else 0)


@pytest.mark.django_db
@pytest.mark.parametrize("via", ["sin_sesion", "con_sesion"])
def test_perfil_maestro_sin_expediente_viola_el_invariante_y_se_revierte(monkeypatch, via):
    cliente = crear_cliente() if via == "con_sesion" else None
    monkeypatch.setattr(expedientes, "crear_para", lambda perfil: None)

    with pytest.raises(InvarianteVioladaError) as error:
        if via == "sin_sesion":
            crear_maestro(rut=RUT_PROPIO)
        else:
            agregar_perfil_maestro(cliente, rut=RUT_PROPIO)

    assert "perfil_maestro sin expediente" in error.value.violaciones
    assert not PerfilMaestro.objects.exists()


@pytest.mark.django_db
def test_verificar_invariantes_detecta_perfil_maestro_sin_expediente(maestro):
    Expediente.objects.filter(perfil_maestro_id=maestro.pk).delete()

    assert "perfil_maestro sin expediente" in verificar_invariantes(maestro)

    expedientes.crear_para(maestro.perfil_maestro)


@pytest.mark.django_db
def test_un_perfil_tiene_un_solo_expediente(maestro):
    with pytest.raises(IntegrityError), transaction.atomic():
        expedientes.crear_para(maestro.perfil_maestro)

    assert Expediente.objects.filter(perfil_maestro_id=maestro.pk).count() == 1


@pytest.mark.django_db
def test_el_expediente_no_se_borra_en_cascada(maestro):
    with pytest.raises(ProtectedError):
        maestro.perfil_maestro.delete()

    assert Expediente.objects.filter(perfil_maestro_id=maestro.pk).exists()


@pytest.mark.django_db
def test_la_bd_exige_motivo_si_hay_autor_del_cambio(maestro):
    admin = crear_cuenta_administrativa(
        nombre="Admin Prueba", correo="admin@example.com", roles=["curatoria"], contrasena=CONTRASENA
    )
    for motivo in ("", "   "):
        with pytest.raises(IntegrityError), transaction.atomic():
            Expediente.objects.filter(perfil_maestro_id=maestro.pk).update(
                estado_cambiado_por=admin, estado_motivo=motivo
            )


@pytest.mark.django_db
def test_la_bd_rechaza_un_estado_desconocido(maestro):
    with pytest.raises(IntegrityError), transaction.atomic():
        _con_estado(maestro, "borrado")

    assert _expediente_de(maestro).estado == EstadoExpediente.EN_REVISION


# --- Migración de datos para maestros existentes ---


@pytest.mark.django_db
def test_la_migracion_crea_los_expedientes_faltantes_y_es_idempotente():
    migracion = importlib.import_module("expediente.migrations.0002_expedientes_existentes")
    uno = crear_maestro(rut=RUT_PROPIO)
    dos = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    ref_de_uno = _expediente_de(uno).ref
    # Simula maestros registrados antes del S2: sin expediente.
    Expediente.objects.filter(perfil_maestro_id=dos.pk).delete()

    migracion.crear_expedientes(registro_de_apps, None)
    migracion.crear_expedientes(registro_de_apps, None)

    assert Expediente.objects.count() == 2
    assert _expediente_de(dos).estado == EstadoExpediente.EN_REVISION
    assert _expediente_de(uno).ref == ref_de_uno


# --- declarar_oficios (servicio) ---


@pytest.mark.django_db
def test_declarar_oficios_guarda_y_reemplaza_la_declaracion(maestro):
    expediente = _expediente_de(maestro)

    declarar_oficios(expediente, ["gas", "ejemplo_1"])
    assert _codigos(maestro) == {"gas", "ejemplo_1"}

    declarar_oficios(expediente, ["ejemplo_1", "electricidad", "ejemplo_1"])
    assert _codigos(maestro) == {"ejemplo_1", "electricidad"}
    assert OficioMaestro.objects.filter(maestro_id=maestro.pk).count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "codigos",
    [None, [], "gas", {"gas": 1}, ["no_existe"], ["gas", "no_existe"], [1], [None], ["GAS"], ["gas\u0000"],
     ["\ud800"], ["x" * 41], ["gas"] * 51],
)
def test_declarar_oficios_invalidos_responde_error_y_no_cambia_nada(maestro, codigos):
    expediente = _expediente_de(maestro)
    declarar_oficios(expediente, ["ejemplo_2"])

    with pytest.raises(ErrorValidacion) as error:
        declarar_oficios(expediente, codigos)

    assert error.value.campo == "oficios"
    assert _codigos(maestro) == {"ejemplo_2"}


@pytest.mark.django_db
@pytest.mark.parametrize("estado", [EstadoExpediente.EN_REVISION, EstadoExpediente.OBSERVADO])
def test_declarar_oficios_se_permite_en_revision_y_observado(maestro, estado):
    _con_estado(maestro, estado)

    declarar_oficios(_expediente_de(maestro), ["gas"])

    assert _codigos(maestro) == {"gas"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "estado", [EstadoExpediente.APROBADO, EstadoExpediente.RECHAZADO, EstadoExpediente.SUSPENDIDO]
)
def test_declarar_oficios_en_otro_estado_es_error_de_estado_sin_cambios(maestro, estado):
    expediente = _expediente_de(maestro)
    declarar_oficios(expediente, ["ejemplo_3"])
    _con_estado(maestro, estado)

    with pytest.raises(ErrorEstado):
        declarar_oficios(expediente, ["gas"])

    assert _codigos(maestro) == {"ejemplo_3"}


# --- GET /api/maestros/expediente ---


@pytest.mark.django_db
def test_el_maestro_ve_su_expediente_sin_cache(navegador_maestro):
    respuesta = navegador_maestro.get(URL_EXPEDIENTE)

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    assert respuesta.json() == {
        "expediente": {
            "estado": "en_revision",
            "motivo": "",
            "oficios": [],
            "documentos": [],
            "faltantes": [{"tipo": "cedula_identidad", "oficio": None}, {"tipo": "certificado_antecedentes", "oficio": None}],
            "avisos": [],
        }
    }


@pytest.mark.django_db
def test_el_maestro_ve_el_motivo_pero_no_quien_cambio_el_estado(navegador_maestro, maestro):
    admin = crear_cuenta_administrativa(
        nombre="Curadora Prueba", correo="curadora@example.com", roles=["curatoria"], contrasena=CONTRASENA
    )
    Expediente.objects.filter(perfil_maestro_id=maestro.pk).update(
        estado=EstadoExpediente.OBSERVADO, estado_motivo="La foto de la cédula está borrosa.", estado_cambiado_por=admin
    )

    respuesta = navegador_maestro.get(URL_EXPEDIENTE)

    datos = respuesta.json()["expediente"]
    assert (datos["estado"], datos["motivo"]) == ("observado", "La foto de la cédula está borrosa.")
    assert_campos_ausentes(
        respuesta,
        {"estado_cambiado_por", "estado_cambiado_por_id", "revisado_por"},
        valores=["Curadora Prueba", "curadora@example.com", str(admin.pk)],
    )


@pytest.mark.django_db
def test_privacidad_sin_rut_ni_identificadores_internos(navegador_maestro, maestro):
    crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    declarar_oficios(_expediente_de(maestro), ["gas"])

    respuesta = navegador_maestro.get(URL_EXPEDIENTE)

    assert respuesta.status_code == 200
    assert_campos_ausentes(
        respuesta,
        {"rut", "id", "pk", "ref", "usuario", "usuario_id", "perfil_maestro", "perfil_maestro_id", "oficio_id",
         "maestro", "estado_cambiado_por", "estado_cambiado_en", "creado_en", "password", "telefono", "correo"},
        valores=["111111111", "222222222", str(_expediente_de(maestro).ref)],
    )


@pytest.mark.django_db
def test_faltantes_incluyen_una_licencia_por_oficio_regulado_declarado(navegador_maestro, maestro):
    declarar_oficios(_expediente_de(maestro), ["ejemplo_1", "electricidad", "gas"])

    faltantes = navegador_maestro.get(URL_EXPEDIENTE).json()["expediente"]["faltantes"]

    assert faltantes == [
        {"tipo": "cedula_identidad", "oficio": None},
        {"tipo": "certificado_antecedentes", "oficio": None},
        {"tipo": "licencia_sec", "oficio": {"codigo": "gas", "nombre": "Gas"}},
        {"tipo": "licencia_sec", "oficio": {"codigo": "electricidad", "nombre": "Electricidad"}},
    ]


@pytest.mark.django_db
def test_faltantes_sin_oficios_regulados_no_piden_licencia(maestro):
    expediente = _expediente_de(maestro)
    declarar_oficios(expediente, ["ejemplo_1", "ejemplo_2"])

    assert faltantes_para_aprobar(expediente) == [(CEDULA, None), (ANTECEDENTES, None)]
    assert LICENCIA_SEC not in {tipo for tipo, _ in faltantes_para_aprobar(expediente)}


@pytest.mark.django_db
def test_cliente_sin_perfil_maestro_recibe_403_registrado(client):
    cliente = crear_cliente()
    assert iniciar_sesion(client, "ana.prueba@example.com").status_code == 200

    for respuesta in (client.get(URL_EXPEDIENTE), post_json(client, URL_OFICIOS_EXPEDIENTE, {"oficios": ["gas"]})):
        assert respuesta.status_code == 403
        assert sin_texto_prohibido(respuesta)
        assert "AlTiro-Rechazo" not in respuesta

    filas = RegistroAccesoDenegado.objects.filter(usuario_id=cliente.pk)
    assert filas.count() == 2
    assert {f.entidad for f in filas} == {"ruta"}
    assert not OficioMaestro.objects.exists()


@pytest.mark.django_db
def test_administrador_sin_perfil_maestro_recibe_403(client):
    crear_cuenta_administrativa(
        nombre="Admin Prueba", correo="admin@example.com", roles=["curatoria"], contrasena=CONTRASENA
    )
    assert iniciar_sesion(client, "admin@example.com").status_code == 200

    assert client.get(URL_EXPEDIENTE).status_code == 403


@pytest.mark.django_db
def test_anonimo_recibe_401(client, maestro):
    assert client.get(URL_EXPEDIENTE).status_code == 401
    assert post_json(client, URL_OFICIOS_EXPEDIENTE, {"oficios": ["gas"]}).status_code == 401
    assert not OficioMaestro.objects.exists()


@pytest.mark.django_db
def test_cliente_que_agrega_perfil_maestro_ve_su_expediente(client):
    cliente = crear_cliente()
    assert iniciar_sesion(client, "ana.prueba@example.com").status_code == 200
    assert post_json(client, "/api/maestros/postulaciones", {"rut": RUT_PROPIO}).status_code == 201

    respuesta = client.get(URL_EXPEDIENTE)

    assert respuesta.status_code == 200
    assert respuesta.json()["expediente"]["estado"] == "en_revision"
    assert _expediente_de(cliente)


# --- POST /api/maestros/expediente/oficios ---


@pytest.mark.django_db
def test_declarar_oficios_por_la_api_devuelve_el_expediente(navegador_maestro, maestro):
    respuesta = post_json(navegador_maestro, URL_OFICIOS_EXPEDIENTE, {"oficios": ["ejemplo_1", "gas"]})

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    datos = respuesta.json()["expediente"]
    assert datos["oficios"] == [
        {"codigo": "gas", "nombre": "Gas", "regulado": True},
        {"codigo": "ejemplo_1", "nombre": "Oficio de ejemplo 1 (por confirmar)", "regulado": False},
    ]
    assert {"tipo": "licencia_sec", "oficio": {"codigo": "gas", "nombre": "Gas"}} in datos["faltantes"]
    assert _codigos(maestro) == {"gas", "ejemplo_1"}


@pytest.mark.django_db
@pytest.mark.parametrize("cuerpo", [{}, {"oficios": []}, {"oficios": ["no_existe"]}, {"oficios": "gas"}])
def test_declarar_oficios_invalidos_por_la_api_responde_400_en_el_campo(navegador_maestro, maestro, cuerpo):
    respuesta = post_json(navegador_maestro, URL_OFICIOS_EXPEDIENTE, cuerpo)

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"oficios"}
    assert sin_texto_prohibido(respuesta)
    assert "no_existe" not in respuesta.content.decode("utf-8")
    assert not OficioMaestro.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("extra", [{"estado": "aprobado"}, {"id": 1}, {"<script>": "x"}])
def test_clave_desconocida_responde_400_general_sin_repetirla(navegador_maestro, maestro, extra):
    respuesta = post_json(navegador_maestro, URL_OFICIOS_EXPEDIENTE, {"oficios": ["gas"], **extra})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {}
    for clave in extra:
        assert clave not in respuesta.content.decode("utf-8")
    assert not OficioMaestro.objects.exists()
    assert _expediente_de(maestro).estado == EstadoExpediente.EN_REVISION


@pytest.mark.django_db
def test_campo_conocido_no_permitido_responde_400_en_ese_campo(navegador_maestro, maestro):
    respuesta = post_json(navegador_maestro, URL_OFICIOS_EXPEDIENTE, {"oficios": ["gas"], "rut": RUT_OTRO})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"rut"}
    assert not OficioMaestro.objects.exists()


@pytest.mark.django_db
def test_oficios_en_registro_es_campo_no_permitido(client):
    """``oficios`` pasa a ser campo conocido (E-2): en otro formulario se informa por campo."""
    respuesta = post_json(
        client,
        "/api/maestros/postulaciones",
        {"rut": RUT_PROPIO, "nombre": "Maestro Uno", "telefono": "+56 9 1000 0001", "contrasena": CONTRASENA,
         "oficios": ["gas"]},
    )

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"oficios"}
    assert not Usuario.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "estado", [EstadoExpediente.APROBADO, EstadoExpediente.RECHAZADO, EstadoExpediente.SUSPENDIDO]
)
def test_declarar_oficios_en_estado_no_editable_responde_409(navegador_maestro, maestro, estado):
    declarar_oficios(_expediente_de(maestro), ["ejemplo_4"])
    _con_estado(maestro, estado)

    respuesta = post_json(navegador_maestro, URL_OFICIOS_EXPEDIENTE, {"oficios": ["gas"]})

    assert respuesta.status_code == 409
    assert "oficios" in respuesta.json()["mensaje"]
    assert sin_texto_prohibido(respuesta)
    assert "_" not in respuesta.json()["mensaje"]
    assert _codigos(maestro) == {"ejemplo_4"}
    assert not RegistroAccesoDenegado.objects.exists()  # Regla de negocio: no se registra (ADR-011, punto 3).


@pytest.mark.django_db
def test_get_de_oficios_del_expediente_no_esta_disponible(navegador_maestro):
    respuesta = navegador_maestro.get(URL_OFICIOS_EXPEDIENTE)

    assert respuesta.status_code == 405


@pytest.mark.django_db
def test_el_maestro_solo_modifica_su_propio_expediente(navegador_maestro, maestro):
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    declarar_oficios(_expediente_de(otro), ["ejemplo_5"])

    post_json(navegador_maestro, URL_OFICIOS_EXPEDIENTE, {"oficios": ["gas"]})

    assert _codigos(otro) == {"ejemplo_5"}
    assert _codigos(maestro) == {"gas"}


# --- Fechas de negocio (ADR-016, punto 3) ---


def test_hoy_negocio_usa_la_hora_de_santiago():
    # 02:00 UTC del 1 de marzo es aún 28 de febrero en Santiago (UTC-3 en verano).
    ahora = datetime.datetime(2026, 3, 1, 2, 0, tzinfo=datetime.timezone.utc)
    assert hoy_negocio(ahora) == datetime.date(2026, 2, 28)
    # 05:00 UTC ya es 1 de marzo en Santiago.
    assert hoy_negocio(ahora + datetime.timedelta(hours=3)) == datetime.date(2026, 3, 1)
    # En invierno (UTC-4): 03:30 UTC del 1 de julio es 30 de junio.
    assert hoy_negocio(datetime.datetime(2026, 7, 1, 3, 30, tzinfo=datetime.timezone.utc)) == datetime.date(2026, 6, 30)


def test_vigente_sin_vencimiento_o_antes_del_vencimiento():
    hoy = datetime.date(2026, 9, 28)

    assert vigente(None, hoy) is True
    assert vigente(datetime.date(2026, 9, 29), hoy) is True
    assert vigente(datetime.date(2026, 9, 28), hoy) is False
    assert vigente(datetime.date(2026, 9, 27), hoy) is False
