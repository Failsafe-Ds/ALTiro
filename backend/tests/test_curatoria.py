"""Curatoría, incremento 4 del S2 (HU-19, RF-32, RF-33, CA-17.2, CA-19.1 a CA-19.4, HU-25, RNF-07, RNF-15).

- Conflicto de interés (ADR-011, E-2; ADR-013, punto 2.5).
- Transiciones del expediente (propuesta del S2, §3), motivo obligatorio,
  RF-33 con la regla de renovación (ADR-017, E-1) y bitácora (CA-19.3).
- Revisión por documento (ADR-017, punto 4; CA-17.2).
- Historial de solo lectura (ADR-010, E-1) y documentos reemplazados (ADR-017, E-3).

Datos ficticios (@example.com, RUT sintéticos) e imágenes sintéticas.
``ALTIRO_DOCUMENTOS_DIR`` apunta a un directorio temporal. Salvo la prueba de
concurrencia, sin ``transaction=True``: la bitácora y ``acceso_denegado`` se
revierten con cada prueba.
"""
import datetime
import io
import json
import threading
import uuid

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import Client
from PIL import Image

from autorizacion import enlaces
from autorizacion.excepciones import ConflictoDeInteres
from autorizacion.middleware import MENSAJE_CONFLICTO, MENSAJE_SIN_ROL
from autorizacion.models import RegistroAccesoDenegado
from autorizacion.politicas import Politica
from bitacora.models import Bitacora
from catalogo.models import Oficio
from comun.api import CABECERA_RECHAZO, respuesta_no_encontrado
from expediente import almacenamiento, servicios, vigencia
from expediente.errores import ErrorEstado
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, TipoDocumento
from identidad import servicios as servicios_identidad
from identidad.models import Rol, Usuario
from identidad.validadores import calcular_digito_verificador
from tests.ayudas import CONTRASENA, TEL_B, crear_cliente, crear_maestro, iniciar_sesion, post_json, sin_texto_prohibido
from tests.privacidad import assert_campos_ausentes

pytestmark = pytest.mark.django_db

RUT_MAESTRO = "11.111.111-1"
RUT_MAESTRO_CANONICO = "111111111"
RUT_OTRO = "22.222.222-2"
CORREO_CURATORIA = "cura@example.com"
NOMBRE_CURATORIA = "Cura Revisora"
NO_ENCONTRADO = respuesta_no_encontrado().content

EN_REVISION = EstadoExpediente.EN_REVISION
OBSERVADO = EstadoExpediente.OBSERVADO
APROBADO = EstadoExpediente.APROBADO
RECHAZADO = EstadoExpediente.RECHAZADO
SUSPENDIDO = EstadoExpediente.SUSPENDIDO

CEDULA = TipoDocumento.CEDULA_IDENTIDAD
ANTECEDENTES = TipoDocumento.CERTIFICADO_ANTECEDENTES
LICENCIA = TipoDocumento.LICENCIA_SEC

TRANSICIONES_VALIDAS = [
    (EN_REVISION, APROBADO),
    (OBSERVADO, APROBADO),
    (EN_REVISION, OBSERVADO),
    (OBSERVADO, EN_REVISION),
    (EN_REVISION, RECHAZADO),
    (OBSERVADO, RECHAZADO),
    (APROBADO, SUSPENDIDO),
    (SUSPENDIDO, APROBADO),
]
TRANSICIONES_INVALIDAS = [
    (de, a) for de in EstadoExpediente.values for a in EstadoExpediente.values if (de, a) not in TRANSICIONES_VALIDAS
]


def _jpeg(color):
    salida = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(salida, format="JPEG")
    return salida.getvalue()


FOTO = _jpeg((10, 120, 200))
FOTO_REVERSO = _jpeg((200, 40, 10))


# --- Fixtures y ayudas ---


@pytest.fixture(autouse=True)
def directorio_documentos(settings, tmp_path):
    directorio = tmp_path / "documentos"
    directorio.mkdir(mode=0o700)
    settings.ALTIRO_DOCUMENTOS_DIR = directorio
    return directorio


def _hoy():
    return vigencia.hoy_negocio()


def _oficio(codigo):
    return Oficio.objects.get(codigo=codigo)


def _expediente(usuario):
    return Expediente.objects.get(perfil_maestro_id=usuario.pk)


def _documento(usuario, tipo, oficio=None, estado=EstadoDocumento.EN_REVISION, vencimiento=None, motivo="",
               emision=None):
    """Documento con archivos cifrados reales en el directorio temporal."""
    ref = uuid.uuid4()
    reverso = almacenamiento.guardar(ref, almacenamiento.REVERSO, FOTO_REVERSO) if tipo == CEDULA else None
    return Documento.objects.create(
        ref=ref,
        expediente=_expediente(usuario),
        tipo=tipo,
        oficio=_oficio(oficio) if oficio else None,
        fecha_emision=emision or datetime.date(2020, 1, 10),
        fecha_vencimiento=vencimiento,
        estado=estado,
        motivo_observacion=motivo,
        archivo=almacenamiento.guardar(ref, almacenamiento.ANVERSO, FOTO),
        archivo_reverso=reverso,
    )


def _reemplazar(anterior, **cambios):
    """Nuevo documento del mismo (tipo, oficio) que deja al anterior ``reemplazado`` (D-11)."""
    Documento.objects.filter(pk=anterior.pk).update(estado=EstadoDocumento.REEMPLAZADO)
    usuario = Usuario.objects.get(pk=anterior.expediente.perfil_maestro_id)
    oficio = anterior.oficio.codigo if anterior.oficio else None
    nuevo = _documento(usuario, anterior.tipo, oficio, **cambios)
    Documento.objects.filter(pk=nuevo.pk).update(reemplaza_a=anterior)
    return nuevo


def _completo(usuario):
    """Cédula y antecedentes validados: sin faltantes si no hay oficios regulados."""
    _documento(usuario, CEDULA, estado=EstadoDocumento.VALIDADO)
    _documento(usuario, ANTECEDENTES, estado=EstadoDocumento.VALIDADO)


def _poner_estado(usuario, estado):
    Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(estado=estado)


def _administrativo(rol, correo, nombre="Admin Prueba"):
    return servicios_identidad.crear_cuenta_administrativa(
        nombre=nombre, correo=correo, roles=[rol], contrasena=CONTRASENA
    )


def _sesion(identificador):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


@pytest.fixture
def maestro():
    usuario = crear_maestro(rut=RUT_MAESTRO)
    servicios.declarar_oficios(_expediente(usuario), ["ejemplo_1"])
    return usuario


@pytest.fixture
def curatoria():
    return _administrativo(Rol.CURATORIA, CORREO_CURATORIA, nombre=NOMBRE_CURATORIA)


@pytest.fixture
def cura(curatoria):
    return _sesion(CORREO_CURATORIA)


def _url_detalle(ref):
    return f"/api/curatoria/expedientes/{ref}"


def _url_estado(ref):
    return f"/api/curatoria/expedientes/{ref}/estado"


def _url_historial(ref):
    return f"/api/curatoria/expedientes/{ref}/historial"


def _url_revision(ref):
    return f"/api/curatoria/documentos/{ref}/revision"


def _url_enlace_curatoria(ref, cara=None):
    return f"/api/curatoria/documentos/{ref}/enlace" + (f"?cara={cara}" if cara else "")


URL_COLA = "/api/curatoria/expedientes"


def _cambiar(client, expediente, estado_nuevo, estado_actual=None, motivo="Revisión de prueba"):
    datos = {"estado_nuevo": estado_nuevo, "estado_actual": estado_actual or expediente.estado, "motivo": motivo}
    return post_json(client, _url_estado(expediente.ref), datos)


def _revisar(client, documento, resultado, motivo=None, estado_actual=None):
    datos = {"resultado": resultado, "estado_actual": estado_actual or documento.estado}
    if motivo is not None:
        datos["motivo"] = motivo
    return post_json(client, _url_revision(documento.ref), datos)


def _estado(usuario):
    return _expediente(usuario).estado


# --- Conflicto de interés genérico (ADR-011, E-2) ---


def test_la_politica_base_no_declara_conflicto_ni_permite():
    assert Politica().conflicto(object(), object()) is False
    assert Politica().permite(object(), object()) is False


# --- Transiciones (propuesta del S2, §3; RF-32) ---


def test_la_tabla_de_transiciones_es_exactamente_la_de_la_propuesta():
    definidas = {(de, a) for de, destinos in servicios.TRANSICIONES.items() for a in destinos}
    assert definidas == set(TRANSICIONES_VALIDAS)
    assert set(servicios.TRANSICIONES) == set(EstadoExpediente.values)


@pytest.mark.parametrize(("de", "a"), TRANSICIONES_VALIDAS)
def test_transicion_valida_cambia_el_estado_y_deja_una_fila_de_bitacora(maestro, curatoria, cura, de, a):
    _completo(maestro)
    _poner_estado(maestro, de)
    expediente = _expediente(maestro)

    respuesta = _cambiar(cura, expediente, a, motivo="  Documentos revisados.  ")

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta["Cache-Control"] == "no-store"
    assert respuesta.json()["expediente"]["estado"] == a
    expediente.refresh_from_db()
    assert expediente.estado == a
    assert expediente.estado_motivo == "Documentos revisados."
    assert expediente.estado_cambiado_por_id == curatoria.pk
    assert expediente.estado_cambiado_en is not None
    fila = Bitacora.objects.get()  # CA-19.3: exactamente una fila
    assert (fila.autor_tipo, fila.autor_id) == ("usuario", curatoria.pk)
    assert fila.fecha is not None
    assert (fila.accion, fila.entidad, fila.entidad_ref) == ("expediente.cambiar_estado", "expediente", str(expediente.ref))
    assert fila.valor_anterior == {"estado": de}
    assert fila.valor_nuevo == {"estado": a}
    assert fila.motivo == "Documentos revisados."


@pytest.mark.parametrize(("de", "a"), TRANSICIONES_INVALIDAS)
def test_transicion_fuera_de_la_tabla_responde_409_sin_cambios(maestro, cura, de, a):
    _completo(maestro)
    _poner_estado(maestro, de)

    respuesta = _cambiar(cura, _expediente(maestro), a)

    assert respuesta.status_code == 409
    assert respuesta.json() == {"mensaje": servicios.mensaje_transicion(de, a), "errores": {}}
    assert sin_texto_prohibido(respuesta)
    assert _estado(maestro) == de
    assert not Bitacora.objects.exists()


def test_el_mensaje_de_transicion_invalida_usa_palabras_del_oficio():
    assert servicios.mensaje_transicion(APROBADO, OBSERVADO) == (
        "Un expediente «aprobado» no puede pasar a «observado». Elige otro estado."
    )


# --- Motivo obligatorio (CA-19.1, RF-32) ---


@pytest.mark.parametrize("motivo", ["", "   ", "\n\t", None, 123, ["x"]])
def test_sin_motivo_escrito_responde_400_sin_cambios(maestro, cura, motivo):
    expediente = _expediente(maestro)
    datos = {"estado_nuevo": OBSERVADO, "estado_actual": EN_REVISION}
    if motivo is not None:
        datos["motivo"] = motivo

    respuesta = post_json(cura, _url_estado(expediente.ref), datos)

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"motivo": servicios.MENSAJE_MOTIVO_FALTA}
    assert _estado(maestro) == EN_REVISION
    assert not Bitacora.objects.exists()


def test_motivo_demasiado_largo_o_con_caracter_nulo_responde_400(maestro, cura):
    expediente = _expediente(maestro)
    for motivo, mensaje in (("x" * 1001, servicios.MENSAJE_MOTIVO_LARGO), ("a\x00b", servicios.MENSAJE_MOTIVO_INVALIDO)):
        respuesta = _cambiar(cura, expediente, OBSERVADO, motivo=motivo)
        assert respuesta.status_code == 400
        assert respuesta.json()["errores"] == {"motivo": mensaje}
    assert _cambiar(cura, expediente, OBSERVADO, motivo="x" * 1000).status_code == 200


def test_estado_nuevo_o_actual_invalidos_responden_400_en_el_campo(maestro, cura):
    expediente = _expediente(maestro)

    respuesta = post_json(cura, _url_estado(expediente.ref), {"estado_nuevo": "Aprobado", "motivo": "x"})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {
        "estado_nuevo": servicios.MENSAJE_ESTADO_NUEVO,
        "estado_actual": servicios.MENSAJE_RECARGA,
    }
    assert not Bitacora.objects.exists()


def test_clave_desconocida_o_campo_no_permitido_responde_400(maestro, cura):
    expediente = _expediente(maestro)
    base = {"estado_nuevo": OBSERVADO, "estado_actual": EN_REVISION, "motivo": "x"}

    desconocida = post_json(cura, _url_estado(expediente.ref), {**base, "autor": 1})
    no_permitido = post_json(cura, _url_estado(expediente.ref), {**base, "resultado": "validar"})

    assert desconocida.status_code == no_permitido.status_code == 400
    assert "autor" not in desconocida.content.decode()
    assert set(no_permitido.json()["errores"]) == {"resultado"}
    assert _estado(maestro) == EN_REVISION


# --- Estado desactualizado (409) ---


def test_estado_actual_desactualizado_responde_409_sin_cambios(maestro, cura):
    expediente = _expediente(maestro)

    respuesta = _cambiar(cura, expediente, EN_REVISION, estado_actual=OBSERVADO)

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == "El expediente cambió mientras lo revisabas. Recarga la página."
    assert _estado(maestro) == EN_REVISION
    assert not Bitacora.objects.exists()


def test_dos_revisiones_con_el_mismo_estado_visto_solo_aplican_la_primera(maestro, cura):
    expediente = _expediente(maestro)
    otra = _administrativo(Rol.CURATORIA, "cura2@example.com")

    primera = _cambiar(cura, expediente, OBSERVADO, estado_actual=EN_REVISION)
    segunda = _cambiar(_sesion("cura2@example.com"), expediente, RECHAZADO, estado_actual=EN_REVISION)

    assert (primera.status_code, segunda.status_code) == (200, 409)
    assert _estado(maestro) == OBSERVADO
    assert Bitacora.objects.count() == 1
    assert not Bitacora.objects.filter(autor_id=otra.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_dos_cambios_simultaneos_no_dejan_estados_inconsistentes(monkeypatch):
    # transaction=True: cada hilo usa su propia conexión. La bitácora no se vacía
    # entre pruebas (ADR-010, punto 4), así que aquí se sustituye registrar() por
    # un registro en memoria; la atomicidad con la bitácora se prueba arriba.
    registradas = []
    candado = threading.Lock()

    def registrar(**datos):
        with candado:
            registradas.append(datos)

    monkeypatch.setattr(servicios.bitacora, "registrar", registrar)
    usuario = crear_maestro(rut=RUT_MAESTRO)
    revisora = _administrativo(Rol.CURATORIA, CORREO_CURATORIA)
    expediente = _expediente(usuario)
    barrera = threading.Barrier(2)
    resultados = []

    def cambiar(estado_nuevo):
        try:
            barrera.wait(timeout=10)
            resultados.append(servicios.cambiar_estado(
                revisora, expediente, {"estado_nuevo": estado_nuevo, "estado_actual": EN_REVISION, "motivo": "x"}
            ).estado)
        except ErrorEstado as error:
            resultados.append(error)
        finally:
            connection.close()

    hilos = [threading.Thread(target=cambiar, args=(estado,)) for estado in (OBSERVADO, RECHAZADO)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    exitos = [r for r in resultados if isinstance(r, str)]
    errores = [r for r in resultados if isinstance(r, ErrorEstado)]
    assert len(exitos) == 1 and len(errores) == 1, resultados
    assert errores[0].mensaje == servicios.MENSAJE_EXPEDIENTE_CAMBIO
    assert _estado(usuario) == exitos[0]
    assert len(registradas) == 1
    assert registradas[0]["valor_nuevo"] == {"estado": exitos[0]}


# --- RF-33 y CA-19.2 (ADR-017, punto 3 y E-1) ---


@pytest.fixture
def maestro_gas(maestro):
    servicios.declarar_oficios(_expediente(maestro), ["gas", "ejemplo_1"])
    _completo(maestro)
    return maestro


def _aprobar(client, usuario):
    return _cambiar(client, _expediente(usuario), APROBADO, motivo="Todo en regla")


def _assert_no_aprueba_por_gas(respuesta, usuario):
    assert respuesta.status_code == 409
    mensaje = respuesta.json()["mensaje"]
    assert mensaje == "No se puede aprobar el expediente: falta la licencia SEC de Gas, validada y vigente."
    assert sin_texto_prohibido(respuesta)
    assert _estado(usuario) != APROBADO
    assert not Bitacora.objects.filter(entidad="expediente").exists()


def test_rf33_sin_licencia_no_aprueba_y_nombra_el_oficio(maestro_gas, cura):
    _assert_no_aprueba_por_gas(_aprobar(cura, maestro_gas), maestro_gas)


@pytest.mark.parametrize(
    ("estado", "motivo"), [(EstadoDocumento.EN_REVISION, ""), (EstadoDocumento.OBSERVADO, "Ilegible")]
)
def test_rf33_licencia_sin_validar_no_aprueba(maestro_gas, cura, estado, motivo):
    _documento(maestro_gas, LICENCIA, "gas", estado=estado, motivo=motivo)

    _assert_no_aprueba_por_gas(_aprobar(cura, maestro_gas), maestro_gas)


def test_rf33_licencia_validada_pero_vencida_no_aprueba(maestro_gas, cura):
    _documento(maestro_gas, LICENCIA, "gas", estado=EstadoDocumento.VALIDADO, vencimiento=_hoy())

    _assert_no_aprueba_por_gas(_aprobar(cura, maestro_gas), maestro_gas)


def test_rf33_licencia_validada_y_vigente_aprueba(maestro_gas, cura):
    _documento(maestro_gas, LICENCIA, "gas", estado=EstadoDocumento.VALIDADO,
               vencimiento=_hoy() + datetime.timedelta(days=1))

    assert _aprobar(cura, maestro_gas).status_code == 200
    assert _estado(maestro_gas) == APROBADO


def test_e1_licencia_renovada_pendiente_con_la_anterior_vigente_aprueba(maestro_gas, cura):
    anterior = _documento(maestro_gas, LICENCIA, "gas", estado=EstadoDocumento.VALIDADO,
                          vencimiento=_hoy() + datetime.timedelta(days=20))
    _reemplazar(anterior, vencimiento=_hoy() + datetime.timedelta(days=2000))

    assert _aprobar(cura, maestro_gas).status_code == 200
    assert _estado(maestro_gas) == APROBADO


def test_e1_licencia_renovada_observada_con_la_anterior_vigente_aprueba(maestro_gas, cura):
    anterior = _documento(maestro_gas, LICENCIA, "gas", estado=EstadoDocumento.VALIDADO)
    _reemplazar(anterior, estado=EstadoDocumento.OBSERVADO, motivo="Foto cortada")

    assert _aprobar(cura, maestro_gas).status_code == 200


def test_e1_licencia_renovada_pendiente_con_la_anterior_vencida_no_aprueba(maestro_gas, cura):
    anterior = _documento(maestro_gas, LICENCIA, "gas", estado=EstadoDocumento.VALIDADO, vencimiento=_hoy())
    _reemplazar(anterior, vencimiento=_hoy() + datetime.timedelta(days=2000))

    _assert_no_aprueba_por_gas(_aprobar(cura, maestro_gas), maestro_gas)


def test_e1_una_licencia_anterior_observada_no_cuenta(maestro_gas, cura):
    anterior = _documento(maestro_gas, LICENCIA, "gas", estado=EstadoDocumento.OBSERVADO, motivo="Ilegible")
    _reemplazar(anterior)

    _assert_no_aprueba_por_gas(_aprobar(cura, maestro_gas), maestro_gas)


def test_e1_validada_la_nueva_cuenta_solo_la_nueva():
    # Unidad sobre la regla única (expediente.vigencia): la anterior vence más tarde que la nueva.
    usuario = crear_maestro(rut=RUT_MAESTRO)
    servicios.declarar_oficios(_expediente(usuario), ["gas"])
    gas = _oficio("gas")
    hoy = datetime.date(2026, 10, 1)
    anterior = _documento(usuario, LICENCIA, "gas", estado=EstadoDocumento.VALIDADO,
                          vencimiento=datetime.date(2031, 1, 1))
    nueva = _reemplazar(anterior, estado=EstadoDocumento.VALIDADO, vencimiento=datetime.date(2027, 1, 1))
    expediente = _expediente(usuario)

    assert vigencia.licencia_habilitante(expediente, gas, hoy) == nueva
    assert vigencia.oficio_habilitado(expediente, gas, datetime.date(2026, 12, 31))
    assert not vigencia.oficio_habilitado(expediente, gas, datetime.date(2027, 1, 1))


def test_oficio_no_regulado_no_exige_licencia(maestro):
    assert vigencia.oficio_habilitado(_expediente(maestro), _oficio("ejemplo_1"))
    assert not vigencia.oficio_habilitado(_expediente(maestro), _oficio("gas"))


def test_rf33_nombra_cada_oficio_y_documento_que_falta(maestro, cura):
    servicios.declarar_oficios(_expediente(maestro), ["gas", "electricidad"])
    _documento(maestro, CEDULA, estado=EstadoDocumento.VALIDADO)

    respuesta = _aprobar(cura, maestro)

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == (
        "No se puede aprobar el expediente: falta el certificado de antecedentes, validado; "
        "la licencia SEC de Gas, validada y vigente; la licencia SEC de Electricidad, validada y vigente."
    )


def test_sin_documentos_validados_no_se_aprueba(maestro, cura):
    _documento(maestro, CEDULA)

    respuesta = _aprobar(cura, maestro)

    assert respuesta.status_code == 409
    assert "la cédula de identidad por ambos lados, validada" in respuesta.json()["mensaje"]
    assert _estado(maestro) == EN_REVISION


def test_de_suspendido_a_aprobado_se_vuelve_a_verificar_rf33(maestro_gas, cura):
    _documento(maestro_gas, LICENCIA, "gas", estado=EstadoDocumento.VALIDADO, vencimiento=_hoy())
    _poner_estado(maestro_gas, SUSPENDIDO)

    respuesta = _cambiar(cura, _expediente(maestro_gas), APROBADO, motivo="Reactivación")

    assert respuesta.status_code == 409
    assert "Gas" in respuesta.json()["mensaje"]
    assert _estado(maestro_gas) == SUSPENDIDO


# --- Revisión de documentos (ADR-017, punto 4; CA-17.2) ---


def test_validar_un_documento_registra_el_motivo_fijo(maestro, curatoria, cura):
    documento = _documento(maestro, ANTECEDENTES)

    respuesta = _revisar(cura, documento, "validar")

    assert respuesta.status_code == 200, respuesta.content
    documento.refresh_from_db()
    assert documento.estado == EstadoDocumento.VALIDADO
    assert documento.motivo_observacion == ""
    assert documento.revisado_por_id == curatoria.pk
    assert documento.revisado_en is not None
    fila = Bitacora.objects.get()
    assert (fila.accion, fila.entidad, fila.entidad_ref) == ("documento.validar", "documento", str(documento.ref))
    assert (fila.valor_anterior, fila.valor_nuevo) == ({"estado": "en_revision"}, {"estado": "validado"})
    assert (fila.autor_tipo, fila.autor_id) == ("usuario", curatoria.pk)
    assert fila.motivo == "Documento revisado y validado"


def test_validar_con_texto_completa_el_motivo_fijo(maestro, cura):
    documento = _documento(maestro, ANTECEDENTES)

    assert _revisar(cura, documento, "validar", motivo=" Coincide con la cédula. ").status_code == 200
    assert Bitacora.objects.get().motivo == "Documento revisado y validado. Coincide con la cédula."


def test_observar_un_documento_guarda_el_motivo(maestro, cura):
    documento = _documento(maestro, CEDULA)

    respuesta = _revisar(cura, documento, "observar", motivo="La foto de atrás está borrosa. Tómala de nuevo.")

    assert respuesta.status_code == 200
    documento.refresh_from_db()
    assert documento.estado == EstadoDocumento.OBSERVADO
    assert documento.motivo_observacion == "La foto de atrás está borrosa. Tómala de nuevo."
    fila = Bitacora.objects.get()
    assert fila.accion == "documento.observar"
    assert fila.valor_nuevo == {"estado": "observado"}
    assert fila.motivo == "La foto de atrás está borrosa. Tómala de nuevo."
    # La revisión de un documento no cambia el estado del expediente.
    assert _estado(maestro) == EN_REVISION


@pytest.mark.parametrize("motivo", [None, "", "   "])
def test_observar_sin_motivo_responde_400_sin_cambios(maestro, cura, motivo):
    documento = _documento(maestro, CEDULA)

    respuesta = _revisar(cura, documento, "observar", motivo=motivo)

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"motivo": servicios.MENSAJE_MOTIVO_OBSERVACION_FALTA}
    documento.refresh_from_db()
    assert documento.estado == EstadoDocumento.EN_REVISION
    assert not Bitacora.objects.exists()


def test_resultado_invalido_responde_400(maestro, cura):
    documento = _documento(maestro, CEDULA)

    respuesta = _revisar(cura, documento, "aprobar", motivo="x")

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"resultado": servicios.MENSAJE_RESULTADO}


@pytest.mark.parametrize(
    ("estado", "motivo"),
    [(EstadoDocumento.VALIDADO, ""), (EstadoDocumento.OBSERVADO, "Ilegible"), (EstadoDocumento.REEMPLAZADO, "")],
)
def test_solo_se_revisa_un_documento_en_revision(maestro, cura, estado, motivo):
    documento = _documento(maestro, ANTECEDENTES, estado=estado, motivo=motivo)

    respuesta = _revisar(cura, documento, "observar", motivo="Otra vez", estado_actual=estado)

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == servicios.MENSAJE_DOCUMENTO_REVISADO
    documento.refresh_from_db()
    assert (documento.estado, documento.motivo_observacion) == (estado, motivo)
    assert not Bitacora.objects.exists()


def test_documento_que_cambio_mientras_se_revisaba_responde_409(maestro, cura):
    documento = _documento(maestro, ANTECEDENTES)

    respuesta = _revisar(cura, documento, "validar", estado_actual=EstadoDocumento.OBSERVADO)

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == servicios.MENSAJE_DOCUMENTO_CAMBIO
    assert not Bitacora.objects.exists()


def test_la_bd_rechaza_un_documento_validado_con_motivo_de_observacion(maestro):
    documento = _documento(maestro, ANTECEDENTES)
    with pytest.raises(IntegrityError), transaction.atomic():
        Documento.objects.filter(pk=documento.pk).update(estado=EstadoDocumento.VALIDADO, motivo_observacion="x")


def test_ca17_2_el_dueno_ve_el_motivo_de_la_observacion_sin_saber_quien_reviso(maestro, cura):
    documento = _documento(maestro, CEDULA)
    validado = _documento(maestro, ANTECEDENTES)
    assert _revisar(cura, documento, "observar", motivo="Falta la parte de atrás.").status_code == 200
    assert _revisar(cura, validado, "validar", motivo="Coincide.").status_code == 200
    assert _cambiar(cura, _expediente(maestro), OBSERVADO, motivo="Corrige tu cédula.").status_code == 200

    respuesta = _sesion(RUT_MAESTRO).get("/api/maestros/expediente")

    assert respuesta.status_code == 200
    datos = respuesta.json()["expediente"]
    assert datos["estado"] == OBSERVADO
    assert datos["motivo"] == "Corrige tu cédula."
    (entregado,) = [d for d in datos["documentos"] if d["ref"] == str(documento.ref)]
    assert entregado["estado"] == "observado"
    assert entregado["motivo_observacion"] == "Falta la parte de atrás."
    # Los documentos no observados llevan null (tampoco el texto de la validación).
    (otro,) = [d for d in datos["documentos"] if d["ref"] == str(validado.ref)]
    assert (otro["estado"], otro["motivo_observacion"]) == ("validado", None)
    assert "Coincide" not in respuesta.content.decode()
    assert_campos_ausentes(
        respuesta,
        {"revisado_por", "revisado_por_id", "revisado_en", "estado_cambiado_por", "estado_cambiado_por_id",
         "autor", "historial"},
        valores=[NOMBRE_CURATORIA, CORREO_CURATORIA],
    )


# --- CA-19.4: un maestro no cambia su propio expediente (ADR-011, E-2; ADR-013, punto 2.5) ---


def test_ca19_4_maestro_sin_rol_recibe_403_por_rol_registrado(maestro):
    client = _sesion(RUT_MAESTRO)
    expediente = _expediente(maestro)

    respuesta = _cambiar(client, expediente, APROBADO)

    assert respuesta.status_code == 403
    assert respuesta.json() == {"mensaje": MENSAJE_SIN_ROL, "errores": {}}
    assert CABECERA_RECHAZO not in respuesta
    assert _estado(maestro) == EN_REVISION
    assert not Bitacora.objects.exists()
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (maestro.pk, "ruta", None)


@pytest.fixture
def maestro_con_rol(maestro):
    servicios_identidad.asignar_rol_administrativo(maestro, Rol.CURATORIA)
    _completo(maestro)
    return maestro


def _assert_conflicto(respuesta, usuario, entidad, ref, recurso):
    assert respuesta.status_code == 403
    assert respuesta.json() == {"mensaje": MENSAJE_CONFLICTO, "errores": {}}
    assert CABECERA_RECHAZO not in respuesta
    assert sin_texto_prohibido(respuesta)
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref, fila.recurso) == (usuario.pk, entidad, str(ref), recurso)


def test_ca19_4_con_rol_curatoria_no_cambia_su_propio_expediente(maestro_con_rol):
    expediente = _expediente(maestro_con_rol)

    respuesta = _cambiar(_sesion(RUT_MAESTRO), expediente, APROBADO)

    _assert_conflicto(respuesta, maestro_con_rol, "expediente", expediente.ref,
                      "POST api/curatoria/expedientes/<uuid:ref>/estado")
    assert _estado(maestro_con_rol) == EN_REVISION
    assert not Bitacora.objects.exists()


@pytest.mark.parametrize(
    ("url", "recurso"),
    [
        (_url_detalle, "GET api/curatoria/expedientes/<uuid:ref>"),
        (_url_historial, "GET api/curatoria/expedientes/<uuid:ref>/historial"),
    ],
)
def test_ca19_4_tampoco_lee_su_propio_expediente_desde_curatoria(maestro_con_rol, url, recurso):
    expediente = _expediente(maestro_con_rol)

    respuesta = _sesion(RUT_MAESTRO).get(url(expediente.ref))

    _assert_conflicto(respuesta, maestro_con_rol, "expediente", expediente.ref, recurso)
    assert_campos_ausentes(respuesta, {"rut", "nombre", "documentos"}, valores=[RUT_MAESTRO_CANONICO])


def test_ca19_4_no_revisa_sus_propios_documentos(maestro_con_rol):
    documento = _documento(maestro_con_rol, LICENCIA, "gas")

    respuesta = _revisar(_sesion(RUT_MAESTRO), documento, "validar", estado_actual="en_revision")

    _assert_conflicto(respuesta, maestro_con_rol, "documento", documento.ref,
                      "POST api/curatoria/documentos/<uuid:ref>/revision")
    documento.refresh_from_db()
    assert documento.estado == EstadoDocumento.EN_REVISION
    assert not Bitacora.objects.exists()


def test_ca19_4_su_expediente_no_aparece_en_la_cola(maestro_con_rol):
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)

    respuesta = _sesion(RUT_MAESTRO).get(URL_COLA)

    assert respuesta.status_code == 200
    refs = {e["ref"] for e in respuesta.json()["expedientes"]}
    assert refs == {str(_expediente(otro).ref)}
    assert respuesta.json()["total"] == 1
    assert not RegistroAccesoDenegado.objects.exists()


def test_ca19_4_con_rol_curatoria_si_revisa_expedientes_ajenos(maestro_con_rol):
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)

    respuesta = _cambiar(_sesion(RUT_MAESTRO), _expediente(otro), OBSERVADO, motivo="Faltan documentos")

    assert respuesta.status_code == 200
    assert _estado(otro) == OBSERVADO
    assert Bitacora.objects.get().autor_id == maestro_con_rol.pk


def test_ca19_4_el_servicio_tambien_rechaza_el_conflicto(maestro_con_rol):
    with pytest.raises(ConflictoDeInteres):
        servicios.cambiar_estado(
            maestro_con_rol, _expediente(maestro_con_rol),
            {"estado_nuevo": OBSERVADO, "estado_actual": EN_REVISION, "motivo": "x"},
        )
    assert _estado(maestro_con_rol) == EN_REVISION
    assert not Bitacora.objects.exists()


# --- Terceros por ruta (RNF-07, HU-25) ---


def _terceros():
    return {
        "cliente": (lambda: crear_cliente(), "ana.prueba@example.com"),
        "otro_maestro": (lambda: crear_maestro(rut=RUT_OTRO, telefono=TEL_B), RUT_OTRO),
        "comercial": (lambda: _administrativo(Rol.COMERCIAL, "comercial@example.com"), "comercial@example.com"),
        "moderacion": (lambda: _administrativo(Rol.MODERACION, "moderacion@example.com"), "moderacion@example.com"),
        "control_gestion": (
            lambda: _administrativo(Rol.CONTROL_GESTION, "gestion@example.com"), "gestion@example.com"
        ),
    }


TERCEROS = sorted(_terceros())


def _peticiones(maestro):
    """Cada ruta de curatoría con referencia: (método, url, cuerpo)."""
    expediente = _expediente(maestro)
    documento = Documento.objects.filter(expediente=expediente).first()
    return {
        "curatoria_detalle": ("get", _url_detalle(expediente.ref), None),
        "curatoria_historial": ("get", _url_historial(expediente.ref), None),
        "curatoria_cambiar_estado": (
            "post", _url_estado(expediente.ref), {"estado_nuevo": APROBADO, "estado_actual": EN_REVISION, "motivo": "x"}
        ),
        "curatoria_revisar_documento": (
            "post", _url_revision(documento.ref), {"resultado": "validar", "estado_actual": "en_revision"}
        ),
        "curatoria_documento_enlace": ("get", _url_enlace_curatoria(documento.ref), None),
    }


def _pedir(client, metodo, url, cuerpo):
    if metodo == "get":
        return client.get(url)
    return post_json(client, url, cuerpo)


RUTAS_CON_REF = [
    "curatoria_detalle", "curatoria_historial", "curatoria_cambiar_estado", "curatoria_revisar_documento",
    "curatoria_documento_enlace",
]


@pytest.mark.terceros("curatoria_detalle")
@pytest.mark.terceros("curatoria_historial")
@pytest.mark.terceros("curatoria_cambiar_estado")
@pytest.mark.terceros("curatoria_revisar_documento")
@pytest.mark.terceros("curatoria_documento_enlace")
@pytest.mark.parametrize("ruta", RUTAS_CON_REF)
@pytest.mark.parametrize("nombre", TERCEROS)
def test_un_tercero_sin_rol_curatoria_recibe_403_registrado_sin_efectos(maestro, ruta, nombre):
    _documento(maestro, ANTECEDENTES)
    crear, identificador = _terceros()[nombre]
    tercero = crear()
    metodo, url, cuerpo = _peticiones(maestro)[ruta]

    respuesta = _pedir(_sesion(identificador), metodo, url, cuerpo)

    assert respuesta.status_code == 403
    assert respuesta.json() == {"mensaje": MENSAJE_SIN_ROL, "errores": {}}
    assert_campos_ausentes(respuesta, {"rut", "nombre", "url"}, valores=[RUT_MAESTRO_CANONICO, "Maestro Uno"])
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "ruta", None)
    assert _estado(maestro) == EN_REVISION
    assert Documento.objects.get(tipo=ANTECEDENTES).estado == EstadoDocumento.EN_REVISION
    assert not Bitacora.objects.exists()


@pytest.mark.terceros("curatoria_detalle")
@pytest.mark.terceros("curatoria_historial")
@pytest.mark.terceros("curatoria_cambiar_estado")
@pytest.mark.terceros("curatoria_revisar_documento")
@pytest.mark.terceros("curatoria_documento_enlace")
@pytest.mark.parametrize("ruta", RUTAS_CON_REF)
def test_una_referencia_inexistente_responde_404_neutro_sin_registro(maestro, cura, ruta):
    _documento(maestro, ANTECEDENTES)
    metodo, url, cuerpo = _peticiones(maestro)[ruta]
    ref_real = url.split("/")[4]
    url = url.replace(ref_real, str(uuid.uuid4()))

    respuesta = _pedir(cura, metodo, url, cuerpo)

    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("curatoria_detalle")
@pytest.mark.terceros("curatoria_historial")
@pytest.mark.terceros("curatoria_cambiar_estado")
@pytest.mark.terceros("curatoria_revisar_documento")
@pytest.mark.terceros("curatoria_documento_enlace")
@pytest.mark.parametrize("ruta", RUTAS_CON_REF)
def test_anonimo_recibe_401_sin_registro(maestro, ruta):
    _documento(maestro, ANTECEDENTES)
    metodo, url, cuerpo = _peticiones(maestro)[ruta]

    respuesta = _pedir(Client(), metodo, url, cuerpo)

    assert respuesta.status_code == 401
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.parametrize("nombre", TERCEROS)
def test_la_cola_exige_el_rol_curatoria(maestro, nombre):
    crear, identificador = _terceros()[nombre]
    tercero = crear()

    respuesta = _sesion(identificador).get(URL_COLA)

    assert respuesta.status_code == 403
    assert respuesta.json()["mensaje"] == MENSAJE_SIN_ROL
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.recurso) == (tercero.pk, "ruta", "GET api/curatoria/expedientes")


@pytest.mark.parametrize(
    ("metodo", "url"),
    [("post", URL_COLA), ("post", "detalle"), ("get", "estado"), ("put", "estado"), ("get", "revision"),
     ("delete", "detalle"), ("post", "enlace")],
)
def test_metodos_no_permitidos_responden_405(maestro, cura, metodo, url):
    documento = _documento(maestro, ANTECEDENTES)
    expediente = _expediente(maestro)
    urls = {
        URL_COLA: URL_COLA,
        "detalle": _url_detalle(expediente.ref),
        "estado": _url_estado(expediente.ref),
        "revision": _url_revision(documento.ref),
        "enlace": _url_enlace_curatoria(documento.ref),
    }

    assert getattr(cura, metodo)(urls[url]).status_code == 405
    assert not Bitacora.objects.exists()


# --- Cola ---


def test_la_cola_lista_expedientes_sin_rut_ni_contacto(maestro, cura):
    servicios.declarar_oficios(_expediente(maestro), ["gas"])
    _documento(maestro, CEDULA)
    _documento(maestro, ANTECEDENTES, estado=EstadoDocumento.VALIDADO)

    respuesta = cura.get(URL_COLA)

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    datos = respuesta.json()
    assert set(datos) == {"expedientes", "pagina", "tamano_pagina", "total"}
    (fila,) = datos["expedientes"]
    expediente = _expediente(maestro)
    assert fila == {
        "ref": str(expediente.ref),
        "nombre": "Maestro Uno",
        "estado": "en_revision",
        "creado_en": expediente.creado_en.isoformat(),
        "oficios": [{"codigo": "gas", "nombre": "Gas", "regulado": True}],
        "faltantes_para_aprobar": 2,
        "documentos_en_revision": 1,
    }
    assert_campos_ausentes(
        respuesta, {"rut", "telefono", "correo", "id", "pk", "perfil_maestro", "perfil_maestro_id"},
        valores=[RUT_MAESTRO_CANONICO, RUT_MAESTRO, "11111111-1", "1000 0001", "10000001"],
    )


def _rut(numero):
    cuerpo = str(30000000 + numero)
    return f"{cuerpo}-{calcular_digito_verificador(cuerpo)}"


def test_la_cola_filtra_por_estado_y_pagina(cura):
    usuarios = [crear_maestro(rut=_rut(numero)) for numero in range(3)]
    _poner_estado(usuarios[1], OBSERVADO)

    observados = cura.get(URL_COLA + "?estado=observado").json()
    todos = cura.get(URL_COLA).json()
    pagina_2 = cura.get(URL_COLA + "?pagina=2").json()

    assert [e["ref"] for e in observados["expedientes"]] == [str(_expediente(usuarios[1]).ref)]
    assert observados["total"] == 1
    # Orden de llegada: el más antiguo primero.
    assert [e["ref"] for e in todos["expedientes"]] == [str(_expediente(u).ref) for u in usuarios]
    assert (pagina_2["expedientes"], pagina_2["pagina"], pagina_2["total"]) == ([], 2, 3)


def test_la_cola_pagina_de_a_20(cura):
    for numero in range(21):
        crear_maestro(rut=_rut(numero))

    primera = cura.get(URL_COLA).json()
    segunda = cura.get(URL_COLA + "?pagina=2").json()

    assert (len(primera["expedientes"]), len(segunda["expedientes"]), primera["total"]) == (20, 1, 21)


@pytest.mark.parametrize(
    "consulta", ["?estado=otro", "?pagina=0", "?pagina=-1", "?pagina=x", "?pagina=%C2%B2", "?por_vencer=30",
                 "?estado=observado&estado=aprobado", "?rut=1"]
)
def test_filtro_invalido_responde_400_accionable(cura, consulta):
    respuesta = cura.get(URL_COLA + consulta)

    assert respuesta.status_code == 400
    assert respuesta.json() == {"mensaje": "Uno de los filtros no es válido. Recarga la página e inténtalo de nuevo.",
                                "errores": {}}


# --- Detalle ---


def test_el_detalle_entrega_lo_necesario_para_revisar(maestro, cura, directorio_documentos):
    servicios.declarar_oficios(_expediente(maestro), ["gas", "ejemplo_1"])
    cedula = _documento(maestro, CEDULA, estado=EstadoDocumento.VALIDADO)
    licencia = _documento(maestro, LICENCIA, "gas", vencimiento=_hoy() + datetime.timedelta(days=40))
    viejo = _documento(maestro, ANTECEDENTES, estado=EstadoDocumento.OBSERVADO, motivo="Vencido")
    nuevo_antecedentes = _reemplazar(viejo)
    expediente = _expediente(maestro)

    respuesta = cura.get(_url_detalle(expediente.ref))

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    datos = respuesta.json()["expediente"]
    assert set(datos) == {"ref", "nombre", "rut", "estado", "motivo", "estado_cambiado_en", "creado_en", "oficios",
                          "documentos", "faltantes_para_aprobar", "estados_siguientes"}
    assert (datos["nombre"], datos["rut"]) == ("Maestro Uno", RUT_MAESTRO_CANONICO)
    assert datos["oficios"] == [
        {"codigo": "gas", "nombre": "Gas", "regulado": True, "habilitado": False},
        {"codigo": "ejemplo_1", "nombre": "Oficio de ejemplo 1 (por confirmar)", "regulado": False, "habilitado": True},
    ]
    # Solo documentos actuales: el reemplazado se abre desde el historial (ADR-017, E-3).
    assert {d["ref"] for d in datos["documentos"]} == {str(cedula.ref), str(licencia.ref), str(nuevo_antecedentes.ref)}
    (dato_licencia,) = [d for d in datos["documentos"] if d["ref"] == str(licencia.ref)]
    assert dato_licencia == {
        "ref": str(licencia.ref),
        "tipo": "licencia_sec",
        "oficio": {"codigo": "gas", "nombre": "Gas"},
        "estado": "en_revision",
        "fecha_emision": "2020-01-10",
        "fecha_vencimiento": licencia.fecha_vencimiento.isoformat(),
        "vigente": True,
        "dias_restantes": (licencia.fecha_vencimiento - _hoy()).days,
        "motivo_observacion": "",
        "tiene_reverso": False,
        "cargado_en": licencia.cargado_en.isoformat(),
        "revisado_en": None,
    }
    assert datos["faltantes_para_aprobar"] == [
        {"tipo": "certificado_antecedentes", "oficio": None},
        {"tipo": "licencia_sec", "oficio": {"codigo": "gas", "nombre": "Gas"}},
    ]
    assert datos["estados_siguientes"] == ["aprobado", "observado", "rechazado"]
    # Minimización: sin contacto, ids internos, archivos ni revisor.
    assert_campos_ausentes(
        respuesta,
        {"telefono", "correo", "id", "pk", "archivo", "archivo_reverso", "revisado_por", "revisado_por_id",
         "estado_cambiado_por", "estado_cambiado_por_id", "reemplaza_a", "reemplaza_a_id", "perfil_maestro_id"},
        valores=["1000 0001", "10000001", str(cedula.archivo), str(directorio_documentos), str(viejo.ref)],
    )


# --- Historial (CA-19.3; ADR-010, E-1) ---


def test_el_historial_muestra_autor_fecha_anterior_nuevo_y_motivo(maestro, curatoria, cura):
    documento = _documento(maestro, ANTECEDENTES)
    assert _revisar(cura, documento, "observar", motivo="Está vencido").status_code == 200
    assert _cambiar(cura, _expediente(maestro), OBSERVADO, motivo="Sube un certificado vigente").status_code == 200
    # Un expediente ajeno no se mezcla.
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    assert _cambiar(cura, _expediente(otro), RECHAZADO, motivo="Otro expediente").status_code == 200

    respuesta = cura.get(_url_historial(_expediente(maestro).ref))

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    historial = respuesta.json()["historial"]
    assert len(historial) == 2
    cambio, revision = historial  # del más reciente al más antiguo
    assert set(cambio) == {"fecha", "autor", "accion", "estado_anterior", "estado_nuevo", "motivo", "documento"}
    assert cambio["autor"] == NOMBRE_CURATORIA
    assert cambio["fecha"]
    assert (cambio["accion"], cambio["estado_anterior"], cambio["estado_nuevo"], cambio["motivo"]) == (
        "expediente.cambiar_estado", "en_revision", "observado", "Sube un certificado vigente"
    )
    assert cambio["documento"] is None
    assert (revision["accion"], revision["estado_anterior"], revision["estado_nuevo"]) == (
        "documento.observar", "en_revision", "observado"
    )
    assert revision["documento"] == {
        "ref": str(documento.ref), "tipo": "certificado_antecedentes", "oficio": None, "estado": "observado",
        "tiene_reverso": False,
    }
    assert_campos_ausentes(respuesta, {"autor_id", "id", "rut", "telefono", "correo", "valor_anterior"},
                           valores=[RUT_MAESTRO_CANONICO, CORREO_CURATORIA])


def test_el_historial_referencia_documentos_reemplazados(maestro, cura):
    viejo = _documento(maestro, ANTECEDENTES)
    assert _revisar(cura, viejo, "validar").status_code == 200
    viejo.refresh_from_db()
    _reemplazar(viejo)

    (entrada,) = cura.get(_url_historial(_expediente(maestro).ref)).json()["historial"]

    assert entrada["documento"]["ref"] == str(viejo.ref)
    assert entrada["documento"]["estado"] == "reemplazado"


def test_el_historial_de_un_expediente_sin_cambios_esta_vacio(maestro, cura):
    assert cura.get(_url_historial(_expediente(maestro).ref)).json() == {"historial": []}


# --- Bitácora sin datos personales (ADR-010) ---


def test_la_bitacora_no_guarda_datos_personales(maestro, cura):
    documento = _documento(maestro, ANTECEDENTES)
    _revisar(cura, documento, "validar")
    _cambiar(cura, _expediente(maestro), OBSERVADO, motivo="Faltan documentos")

    for fila in Bitacora.objects.all():
        valores = json.dumps([fila.valor_anterior, fila.valor_nuevo, fila.entidad_ref, fila.accion])
        assert set(fila.valor_anterior) == set(fila.valor_nuevo) == {"estado"}
        for dato in (RUT_MAESTRO_CANONICO, "Maestro Uno", "1000 0001", NOMBRE_CURATORIA, CORREO_CURATORIA):
            assert dato not in valores


# --- Documentos reemplazados (ADR-017, E-3) ---


@pytest.fixture
def reemplazado(maestro):
    viejo = _documento(maestro, CEDULA, estado=EstadoDocumento.VALIDADO)
    _reemplazar(viejo)
    viejo.refresh_from_db()
    return viejo


@pytest.mark.terceros("curatoria_documento_enlace")
@pytest.mark.parametrize(("cara", "foto"), [("anverso", FOTO), ("reverso", FOTO_REVERSO)])
def test_e3_curatoria_abre_un_documento_reemplazado(reemplazado, cura, cara, foto):
    respuesta = cura.get(_url_enlace_curatoria(reemplazado.ref, cara))

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    assert set(respuesta.json()) == {"url", "caduca_en"}
    archivo = cura.get(respuesta.json()["url"])
    assert archivo.status_code == 200
    assert archivo.content == foto
    assert not RegistroAccesoDenegado.objects.exists()


def test_e3_curatoria_no_lo_abre_por_la_ruta_general(reemplazado, cura):
    # La ruta general solo entrega documentos actuales (incremento 3).
    assert cura.get(f"/api/documentos/{reemplazado.ref}/enlace").content == NO_ENCONTRADO


@pytest.mark.terceros("documento_archivo")
def test_e3_el_dueno_no_abre_un_documento_reemplazado(maestro, reemplazado):
    dueno = _sesion(RUT_MAESTRO)
    token = enlaces.firmar(reemplazado.ref, maestro.pk, "anverso")

    enlace = dueno.get(f"/api/documentos/{reemplazado.ref}/enlace")
    archivo = dueno.get(f"/api/documentos/{reemplazado.ref}/archivo?cara=anverso&t={token}")
    curatoria = dueno.get(_url_enlace_curatoria(reemplazado.ref))

    assert enlace.content == archivo.content == NO_ENCONTRADO
    assert curatoria.status_code == 403  # sin rol curatoria
    assert RegistroAccesoDenegado.objects.get().entidad == "ruta"


@pytest.mark.terceros("curatoria_documento_enlace")
@pytest.mark.terceros("documento_archivo")
def test_e3_el_dueno_con_rol_curatoria_no_abre_su_documento_reemplazado(maestro, reemplazado):
    servicios_identidad.asignar_rol_administrativo(maestro, Rol.CURATORIA)
    dueno = _sesion(RUT_MAESTRO)
    token = enlaces.firmar(reemplazado.ref, maestro.pk, "anverso")

    respuesta = dueno.get(_url_enlace_curatoria(reemplazado.ref))
    archivo = dueno.get(f"/api/documentos/{reemplazado.ref}/archivo?cara=anverso&t={token}")

    _assert_conflicto(respuesta, maestro, "documento", reemplazado.ref, "GET api/curatoria/documentos/<uuid:ref>/enlace")
    assert archivo.content == NO_ENCONTRADO
    assert RegistroAccesoDenegado.objects.count() == 1


@pytest.mark.terceros("documento_archivo")
@pytest.mark.parametrize("nombre", TERCEROS)
def test_e3_un_tercero_recibe_404_registrado_aun_con_un_token_propio(reemplazado, nombre):
    crear, identificador = _terceros()[nombre]
    tercero = crear()
    token = enlaces.firmar(reemplazado.ref, tercero.pk, "anverso")

    respuesta = _sesion(identificador).get(f"/api/documentos/{reemplazado.ref}/archivo?cara=anverso&t={token}")

    assert respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "documento", str(reemplazado.ref))


def test_e3_curatoria_tambien_obtiene_el_enlace_de_documentos_actuales(maestro, cura):
    actual = _documento(maestro, ANTECEDENTES)

    respuesta = cura.get(_url_enlace_curatoria(actual.ref))

    assert cura.get(respuesta.json()["url"]).content == FOTO


def test_e3_el_enlace_de_curatoria_valida_la_cara(maestro, cura):
    actual = _documento(maestro, ANTECEDENTES)

    respuesta = cura.get(_url_enlace_curatoria(actual.ref, "reverso"))

    assert respuesta.status_code == 400
    assert sin_texto_prohibido(respuesta)


# --- RNF-17: textos que ve el maestro, sin siglas ni unidades técnicas ---


def test_rnf17_mensajes_del_maestro_sin_jerga():
    from expediente import imagenes
    from expediente.vistas import MENSAJE_SUBIDA_GRANDE

    for mensaje in (imagenes.MENSAJE_FORMATO, imagenes.MENSAJE_PESO, MENSAJE_SUBIDA_GRANDE):
        for termino in ("MB", "JPG", "PNG", "JPEG"):
            assert termino not in mensaje
    # La sigla SEC, si aparece, va explicada.
    assert "Superintendencia de Electricidad y Combustibles (SEC)" in servicios.MENSAJE_OFICIO_NO_REGULADO


# --- RNF-15: mensajes sin texto de programador ---


def test_rnf15_los_mensajes_de_curatoria_no_tienen_texto_de_programador(maestro, cura):
    expediente = _expediente(maestro)
    documento = _documento(maestro, CEDULA)
    respuestas = [
        _cambiar(cura, expediente, APROBADO),
        _cambiar(cura, expediente, SUSPENDIDO),
        _cambiar(cura, expediente, OBSERVADO, estado_actual=APROBADO),
        post_json(cura, _url_estado(expediente.ref), {"estado_nuevo": "x"}),
        _revisar(cura, documento, "observar"),
        _revisar(cura, documento, "validar", estado_actual="validado"),
        cura.get(URL_COLA + "?estado=x"),
        cura.post(_url_estado(expediente.ref), data="no es json", content_type="application/json"),
    ]
    for respuesta in respuestas:
        assert respuesta.status_code in (400, 409), respuesta.content
        assert sin_texto_prohibido(respuesta), respuesta.content
        texto = respuesta.content.decode()
        for interno in ("en_revision", "estado_actual", "select_for_update", "ErrorEstado", "TRANSICIONES"):
            assert interno not in json.loads(texto)["mensaje"]
