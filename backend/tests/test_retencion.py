"""Retención de documentos del maestro (RNF-26, RF-37; ADR-026, E-9; S5, incremento 3).

Los archivos son cifrados reales en un directorio temporal. El borrado se
agenda con ``transaction.on_commit``: las pruebas lo ejecutan con
``django_capture_on_commit_callbacks(execute=True)``.
"""
import datetime
import logging
import uuid

import pytest
from django.test import Client

from bitacora.models import AutorTipo, Bitacora
from expediente import almacenamiento, retencion
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, TipoDocumento
from identidad import servicios
from identidad.models import Rol
from tests.ayudas import CONTRASENA, crear_maestro, iniciar_sesion

UTC = datetime.timezone.utc
AHORA = datetime.datetime(2027, 3, 1, 12, 0, tzinfo=UTC)
PLAZO = 30
CEDULA = TipoDocumento.CEDULA_IDENTIDAD
ANTECEDENTES = TipoDocumento.CERTIFICADO_ANTECEDENTES
CORREO_CURATORIA = "cura.retencion@example.com"


@pytest.fixture(autouse=True)
def sin_advertencias_previas():
    retencion._advertido_en.clear()
    yield
    retencion._advertido_en.clear()


@pytest.fixture(autouse=True)
def directorio_documentos(settings, tmp_path):
    directorio = tmp_path / "documentos"
    directorio.mkdir(mode=0o700)
    settings.ALTIRO_DOCUMENTOS_DIR = directorio
    return directorio


@pytest.fixture
def sin_plazos(settings):
    settings.RETENCION_DIAS = {tipo: None for tipo in TipoDocumento.values}


@pytest.fixture
def con_plazos(settings):
    settings.RETENCION_DIAS = {tipo: PLAZO for tipo in TipoDocumento.values}


@pytest.fixture
def maestro():
    return crear_maestro(rut="11.111.111-1")


def _expediente(usuario, estado, hace_dias):
    expediente = Expediente.objects.get(perfil_maestro_id=usuario.pk)
    expediente.estado = estado
    expediente.estado_cambiado_en = AHORA - datetime.timedelta(days=hace_dias)
    expediente.save(update_fields=["estado", "estado_cambiado_en"])
    return expediente


def _documento(usuario, tipo=CEDULA, estado=EstadoDocumento.EN_REVISION):
    ref = uuid.uuid4()
    reverso = almacenamiento.guardar(ref, almacenamiento.REVERSO, b"reverso") if tipo == CEDULA else None
    return Documento.objects.create(
        ref=ref,
        expediente=Expediente.objects.get(perfil_maestro_id=usuario.pk),
        tipo=tipo,
        fecha_emision=datetime.date(2026, 1, 10),
        estado=estado,
        archivo=almacenamiento.guardar(ref, almacenamiento.ANVERSO, b"anverso"),
        archivo_reverso=reverso,
    )


def _existe(directorio, nombre):
    return (directorio / str(nombre)).exists()


def _aplicar(capturar):
    with capturar(execute=True):
        return retencion.aplicar_retencion(AHORA)


def test_hay_un_plazo_configurable_por_cada_tipo_de_documento(settings):
    assert set(settings.RETENCION_DIAS) == set(TipoDocumento.values)


@pytest.mark.regla("O-01")
@pytest.mark.django_db
def test_sin_plazo_no_borra_nada_y_registra_una_advertencia(
    maestro, sin_plazos, directorio_documentos, django_capture_on_commit_callbacks, caplog
):
    _expediente(maestro, EstadoExpediente.RECHAZADO, hace_dias=3650)
    documento = _documento(maestro)

    with caplog.at_level(logging.WARNING, logger="expediente.retencion"):
        assert _aplicar(django_capture_on_commit_callbacks) == 0

    documento.refresh_from_db()
    assert documento.eliminado_en is None and documento.motivo_eliminacion == ""
    assert _existe(directorio_documentos, documento.archivo)
    assert _existe(directorio_documentos, documento.archivo_reverso)
    assert not Bitacora.objects.filter(accion=retencion.ACCION).exists()
    advertencias = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(advertencias) == 1
    assert "cedula_identidad" in advertencias[0].getMessage()
    assert str(documento.ref) not in advertencias[0].getMessage()


@pytest.mark.django_db
def test_la_advertencia_sin_plazo_se_registra_una_vez_por_dia(maestro, sin_plazos, caplog):
    _expediente(maestro, EstadoExpediente.RECHAZADO, hace_dias=3650)
    _documento(maestro)

    with caplog.at_level(logging.WARNING, logger="expediente.retencion"):
        for minutos in (0, 5, 10):
            retencion.aplicar_retencion(AHORA + datetime.timedelta(minutes=minutos))
        assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1
        retencion.aplicar_retencion(AHORA + datetime.timedelta(days=1))

    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2


@pytest.mark.regla("O-02")
@pytest.mark.django_db
@pytest.mark.parametrize("estado", [EstadoExpediente.RECHAZADO, EstadoExpediente.SUSPENDIDO])
def test_con_plazo_cumplido_borra_marca_y_escribe_la_bitacora(
    maestro, con_plazos, directorio_documentos, django_capture_on_commit_callbacks, estado
):
    _expediente(maestro, estado, hace_dias=PLAZO)
    cedula = _documento(maestro)
    antecedentes = _documento(maestro, ANTECEDENTES, estado=EstadoDocumento.VALIDADO)

    assert _aplicar(django_capture_on_commit_callbacks) == 2

    for documento in (cedula, antecedentes):
        documento.refresh_from_db()
        assert documento.eliminado_en == AHORA
        assert f"{PLAZO} días" in documento.motivo_eliminacion
        assert not _existe(directorio_documentos, documento.archivo)
        entrada = Bitacora.objects.get(accion=retencion.ACCION, entidad_ref=str(documento.ref))
        assert entrada.autor_tipo == AutorTipo.SISTEMA and entrada.autor_id is None
        assert entrada.entidad == "documento"
        assert entrada.motivo == documento.motivo_eliminacion
        assert entrada.valor_nuevo == {
            "eliminado": True, "tipo": documento.tipo, "plazo_dias": PLAZO, "estado_expediente": estado
        }
    assert not _existe(directorio_documentos, cedula.archivo_reverso)

    # Idempotente: una segunda corrida no vuelve a eliminar ni a registrar.
    assert _aplicar(django_capture_on_commit_callbacks) == 0
    assert Bitacora.objects.filter(accion=retencion.ACCION).count() == 2


@pytest.mark.regla("O-03")
@pytest.mark.django_db
@pytest.mark.parametrize(
    "estado, hace_dias",
    [
        (EstadoExpediente.APROBADO, 3650),
        (EstadoExpediente.EN_REVISION, 3650),
        (EstadoExpediente.OBSERVADO, 3650),
        (EstadoExpediente.RECHAZADO, PLAZO - 1),
    ],
)
def test_no_toca_expedientes_activos_ni_antes_del_plazo(
    maestro, con_plazos, directorio_documentos, django_capture_on_commit_callbacks, estado, hace_dias
):
    _expediente(maestro, estado, hace_dias=hace_dias)
    documento = _documento(maestro, estado=EstadoDocumento.VALIDADO)

    assert _aplicar(django_capture_on_commit_callbacks) == 0

    documento.refresh_from_db()
    assert documento.eliminado_en is None
    assert _existe(directorio_documentos, documento.archivo)
    assert not Bitacora.objects.filter(accion=retencion.ACCION).exists()


@pytest.mark.django_db
def test_un_plazo_por_tipo_solo_elimina_ese_tipo(
    maestro, settings, directorio_documentos, django_capture_on_commit_callbacks
):
    settings.RETENCION_DIAS = {**{t: None for t in TipoDocumento.values}, ANTECEDENTES: PLAZO}
    _expediente(maestro, EstadoExpediente.RECHAZADO, hace_dias=PLAZO)
    cedula = _documento(maestro)
    antecedentes = _documento(maestro, ANTECEDENTES)

    assert _aplicar(django_capture_on_commit_callbacks) == 1

    cedula.refresh_from_db()
    antecedentes.refresh_from_db()
    assert cedula.eliminado_en is None and antecedentes.eliminado_en is not None


# --- Vistas ante un documento eliminado ---


def _sesion(identificador):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


@pytest.fixture
def eliminado(maestro, con_plazos, django_capture_on_commit_callbacks):
    """Cédula en revisión de un expediente suspendido, eliminada por retención."""
    _expediente(maestro, EstadoExpediente.SUSPENDIDO, hace_dias=PLAZO)
    documento = _documento(maestro)
    _aplicar(django_capture_on_commit_callbacks)
    documento.refresh_from_db()
    assert documento.eliminado_en is not None
    return documento


@pytest.fixture
def curatoria():
    servicios.crear_cuenta_administrativa(
        nombre="Cura Retencion", correo=CORREO_CURATORIA, roles=[Rol.CURATORIA], contrasena=CONTRASENA
    )
    return _sesion(CORREO_CURATORIA)


@pytest.mark.django_db
def test_el_enlace_de_un_documento_eliminado_responde_409_accionable(eliminado, curatoria):
    dueno = _sesion("11.111.111-1")
    for client, url in (
        (dueno, f"/api/documentos/{eliminado.ref}/enlace"),
        (curatoria, f"/api/curatoria/documentos/{eliminado.ref}/enlace"),
    ):
        respuesta = client.get(url)
        assert respuesta.status_code == 409
        assert "plazo de retención" in respuesta.json()["mensaje"]


@pytest.mark.django_db
def test_un_enlace_emitido_antes_de_eliminar_responde_404_y_no_500(maestro, con_plazos, django_capture_on_commit_callbacks):
    _expediente(maestro, EstadoExpediente.SUSPENDIDO, hace_dias=PLAZO)
    documento = _documento(maestro)
    dueno = _sesion("11.111.111-1")
    url = dueno.get(f"/api/documentos/{documento.ref}/enlace").json()["url"]
    _aplicar(django_capture_on_commit_callbacks)

    assert dueno.get(url).status_code == 404


@pytest.mark.django_db
def test_curatoria_ve_el_documento_eliminado_y_no_lo_puede_revisar(eliminado, curatoria):
    expediente = eliminado.expediente
    detalle = curatoria.get(f"/api/curatoria/expedientes/{expediente.ref}")
    assert detalle.status_code == 200
    (datos,) = [d for d in detalle.json()["expediente"]["documentos"] if d["ref"] == str(eliminado.ref)]
    assert datos["eliminado"] is True

    revision = curatoria.post(
        f"/api/curatoria/documentos/{eliminado.ref}/revision",
        data={"resultado": "validar", "estado_actual": "en_revision", "motivo": ""},
        content_type="application/json",
    )
    assert revision.status_code == 409
    assert "plazo de retención" in revision.json()["mensaje"]

    historial = curatoria.get(f"/api/curatoria/expedientes/{expediente.ref}/historial")
    assert historial.status_code == 200
    assert retencion.ACCION in historial.content.decode()


@pytest.mark.django_db
def test_un_documento_validado_eliminado_no_cuenta_para_aprobar(maestro, con_plazos, django_capture_on_commit_callbacks):
    from expediente import vigencia

    expediente = _expediente(maestro, EstadoExpediente.SUSPENDIDO, hace_dias=PLAZO)
    _documento(maestro, estado=EstadoDocumento.VALIDADO)
    _documento(maestro, ANTECEDENTES, estado=EstadoDocumento.VALIDADO)
    assert vigencia.faltantes_para_aprobar(expediente) == []

    _aplicar(django_capture_on_commit_callbacks)

    assert {tipo for tipo, _ in vigencia.faltantes_para_aprobar(expediente)} == {CEDULA, ANTECEDENTES}
