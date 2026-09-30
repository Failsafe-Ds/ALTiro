"""Foto, perfil del maestro y perfil público, incremento 5 del S3.

RF-06 ("no aparece"), RF-13 (dato foto) y RF-14 parciales, RF-34, RNF-25,
CA-12.2, CA-24.1, RNF-07; ADR-019 (puntos 3, 5 y 6), ADR-021, ADR-015 (patrón).

- Foto: EXIF/GPS eliminado, políglota neutralizado, tamaño, variantes de 160 y
  480 px, permisos 0600, reemplazo con borrado al confirmar.
- Publicación: un maestro no publicado responde el mismo 404 que una ref
  inexistente, sin fila en ``acceso_denegado``.
- RNF-25: barrido de todas las rutas públicas (incluida la búsqueda del S4) con combinaciones generadas de
  licencias: ningún servicio de gas o electricidad visible sin licencia habilitante.
- Privacidad: lista explícita de campos, sin la comuna base como tal.

Datos ficticios (@example.com, RUT sintéticos); imágenes sintéticas.
``ALTIRO_FOTOS_DIR`` apunta a un temporal (``tests/conftest.py``).
"""
import datetime
import io
import itertools
import os
import stat
import uuid
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone
from PIL import Image

from autorizacion.models import RegistroAccesoDenegado
from catalogo.models import Modalidad, Oficio, Servicio, ServicioModalidad
from comun.api import respuesta_no_encontrado
from expediente import imagenes
from expediente import servicios as expedientes
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, TipoDocumento
from expediente.vigencia import hoy_negocio
from identidad import servicios as servicios_identidad
from identidad.models import Rol
from perfil import agenda, cobertura, fotos, publicacion
from perfil.models import Cobertura, PerfilPublico, ServicioMaestro
from perfil.vistas_maestro import MAXIMO_CUERPO_FOTO, MENSAJE_FOTO_GRANDE, MENSAJES_PENDIENTE
from perfil.vistas_publicas import CABECERAS_FOTO
from tests.ayudas import CONTRASENA, TEL_A, TEL_B, crear_cliente, crear_maestro, iniciar_sesion
from tests.conftest import directorios_de_datos
from tests.control_terceros import rutas
from tests.privacidad import assert_campos_ausentes

pytestmark = pytest.mark.django_db

RUT = "11.111.111-1"
RUT_CANONICO = "111111111"
RUT_OTRO = "22.222.222-2"
URL_FOTO = "/api/maestros/perfil/foto"
URL_PERFIL = "/api/maestros/perfil"
NO_ENCONTRADO = respuesta_no_encontrado().content
T = Modalidad.POR_TRABAJO
# Monto que solo tiene el servicio regulado del maestro: si aparece en una
# respuesta pública, el servicio es visible.
MONTO_MARCA = 7_373_737
MONTO_PINTURA = 64_000


# --- Ayudas ---


def _imagen(tamano=(1200, 800), formato="JPEG", exif=None):
    salida = io.BytesIO()
    argumentos = {"exif": exif} if exif is not None else {}
    Image.new("RGB", tamano, (180, 90, 40)).save(salida, format=formato, **argumentos)
    return salida.getvalue()


def _archivo(contenido, nombre="foto.jpg"):
    return SimpleUploadedFile(nombre, contenido, content_type="image/jpeg")


def _sesion(identificador=RUT):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


def _servicio_catalogo(oficio, nombre):
    servicio = Servicio.objects.create(oficio=Oficio.objects.get(codigo=oficio), nombre=nombre, orden=1)
    ServicioModalidad.objects.create(servicio=servicio, modalidad=T, precio_referencia=30000)
    return servicio


def _licencia(usuario, oficio, estado=EstadoDocumento.VALIDADO, vencimiento=None, cargado_en=None):
    return Documento.objects.create(
        expediente=Expediente.objects.get(perfil_maestro_id=usuario.pk),
        tipo=TipoDocumento.LICENCIA_SEC,
        oficio=Oficio.objects.get(codigo=oficio),
        fecha_emision=datetime.date(2020, 1, 10),
        fecha_vencimiento=vencimiento,
        estado=estado,
        motivo_observacion="Foto borrosa" if estado == EstadoDocumento.OBSERVADO else "",
        archivo=uuid.uuid4(),
        cargado_en=cargado_en or timezone.now(),
    )


def _preparar(usuario, oficios=("gas", "pintura")):
    """Expediente aprobado, oficios, comuna base (Talcahuano) más Concepción y foto real."""
    expedientes.declarar_oficios(Expediente.objects.get(perfil_maestro_id=usuario.pk), list(oficios))
    Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(estado=EstadoExpediente.APROBADO)
    cobertura.reemplazar_cobertura(
        usuario, [{"comuna": "8110", "es_base": True}, {"comuna": "8101", "es_base": False}]
    )
    fotos.subir_foto(usuario, _archivo(_imagen()))


def _ref(usuario):
    return PerfilPublico.objects.get(perfil_maestro_id=usuario.pk).ref


def _url(usuario):
    return f"/api/maestros/publicos/{_ref(usuario)}"


@pytest.fixture
def catalogo():
    return {
        "gas": _servicio_catalogo("gas", "Instalación de cocina"),
        "electricidad": _servicio_catalogo("electricidad", "Cambio de enchufe"),
        "pintura": _servicio_catalogo("pintura", "Pintura de habitación"),
    }


@pytest.fixture
def maestro():
    return crear_maestro(rut=RUT, correo="maestro.uno@example.com")


@pytest.fixture
def publicado(maestro, catalogo):
    """Maestro publicado con gas (licencia validada y vigente) y pintura, dos bloques."""
    _preparar(maestro)
    _licencia(maestro, "gas", vencimiento=hoy_negocio() + datetime.timedelta(days=200))
    ServicioMaestro.objects.create(maestro_id=maestro.pk, servicio=catalogo["gas"], modalidad=T, monto=MONTO_MARCA)
    ServicioMaestro.objects.create(maestro_id=maestro.pk, servicio=catalogo["pintura"], modalidad=T, monto=MONTO_PINTURA)
    agenda.agregar_bloque(maestro, {"dia_semana": 1, "inicio": "08:00", "fin": "12:00"})
    agenda.agregar_bloque(maestro, {"dia_semana": 6, "inicio": "14:30", "fin": "24:00"})
    assert publicacion.maestro_publicado(maestro.pk)
    return maestro


# --- Aislamiento del directorio de fotos (DEF-QA-008) ---


def test_el_directorio_de_fotos_queda_aislado_en_el_temporal_de_pytest(tmp_path_factory):
    assert "ALTIRO_FOTOS_DIR" in directorios_de_datos()
    base = tmp_path_factory.getbasetemp().resolve()
    assert Path(settings.ALTIRO_FOTOS_DIR).resolve().is_relative_to(base)
    real = os.environ.get("ALTIRO_FOTOS_DIR")
    if real:
        assert Path(settings.ALTIRO_FOTOS_DIR).resolve() != Path(real).resolve()


# --- Foto (ADR-021) ---


def test_la_foto_se_guarda_en_dos_variantes_sin_exif_ni_gps(maestro):
    exif = Image.Exif()
    exif[0x010F] = "MarcaFicticiaDeCamara"
    gps = exif.get_ifd(0x8825)
    gps[1] = "S"
    gps[2] = (36.0, 49.0, 30.0)
    original = _imagen((2000, 1000), exif=exif)
    assert b"MarcaFicticiaDeCamara" in original

    respuesta = _sesion().post(URL_FOTO, data={"archivo": _archivo(original)})

    assert respuesta.status_code == 201
    perfil = PerfilPublico.objects.get(perfil_maestro_id=maestro.pk)
    assert perfil.foto is not None and perfil.foto_actualizada_en is not None
    for tamano, esperado in ((160, (160, 80)), (480, (480, 240))):
        ruta = Path(settings.ALTIRO_FOTOS_DIR) / f"{perfil.foto}-{tamano}.jpg"
        contenido = ruta.read_bytes()
        assert b"MarcaFicticiaDeCamara" not in contenido and b"Exif" not in contenido
        with Image.open(io.BytesIO(contenido)) as imagen:
            assert imagen.format == "JPEG" and imagen.size == esperado
            assert len(imagen.getexif()) == 0 and not imagen.getexif().get_ifd(0x8825)
            assert "icc_profile" not in imagen.info
        assert stat.S_IMODE(ruta.stat().st_mode) == 0o600
    assert sorted(p.name for p in Path(settings.ALTIRO_FOTOS_DIR).iterdir()) == sorted(
        [f"{perfil.foto}-160.jpg", f"{perfil.foto}-480.jpg"]
    )


def test_una_foto_pequena_no_se_agranda(maestro):
    fotos.subir_foto(maestro, _archivo(_imagen((100, 60), formato="PNG"), "foto.png"))
    nombre = PerfilPublico.objects.get(perfil_maestro_id=maestro.pk).foto
    for tamano in fotos.TAMANOS:
        with Image.open(io.BytesIO(fotos.leer(nombre, tamano))) as imagen:
            assert imagen.size == (100, 60)


def test_un_poliglota_se_neutraliza(maestro):
    poliglota = _imagen((300, 300)) + b"<html><script>alert('x')</script></html>"

    respuesta = _sesion().post(URL_FOTO, data={"archivo": _archivo(poliglota)})

    assert respuesta.status_code == 201
    nombre = PerfilPublico.objects.get(perfil_maestro_id=maestro.pk).foto
    for tamano in fotos.TAMANOS:
        assert b"<script" not in fotos.leer(nombre, tamano)


@pytest.mark.parametrize(
    ("contenido", "mensaje"),
    [
        (b"<html>no es una foto</html>", imagenes.MENSAJE_FORMATO),
        (b"", imagenes.MENSAJE_VACIA),
        (b"GIF89a" + b"\x00" * 100, imagenes.MENSAJE_FORMATO),
    ],
)
def test_archivos_que_no_son_foto_responden_400_sin_escribir(maestro, contenido, mensaje):
    respuesta = _sesion().post(URL_FOTO, data={"archivo": _archivo(contenido)})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"archivo": mensaje}
    assert PerfilPublico.objects.get(perfil_maestro_id=maestro.pk).foto is None
    assert list(Path(settings.ALTIRO_FOTOS_DIR).iterdir()) == []


def test_foto_con_demasiados_pixeles_se_rechaza(maestro):
    salida = io.BytesIO()
    Image.new("L", (6000, 6000)).save(salida, format="PNG")

    respuesta = _sesion().post(URL_FOTO, data={"archivo": _archivo(salida.getvalue(), "foto.png")})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"archivo": imagenes.MENSAJE_PIXELES}


def test_foto_sobre_el_maximo_por_archivo_se_rechaza(maestro):
    pesada = _imagen((50, 50)) + b"\x00" * settings.ALTIRO_DOCUMENTO_MAXIMO_BYTES

    respuesta = _sesion().post(URL_FOTO, data={"archivo": _archivo(pesada)})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"archivo": imagenes.MENSAJE_PESO}


def test_cuerpo_sobre_el_maximo_de_la_ruta_responde_413(maestro):
    pesada = b"\x00" * (MAXIMO_CUERPO_FOTO + 1)

    respuesta = _sesion().post(URL_FOTO, data={"archivo": _archivo(pesada)})

    assert respuesta.status_code == 413
    assert respuesta.json() == {"mensaje": MENSAJE_FOTO_GRANDE, "errores": {}}


@pytest.mark.parametrize(
    "datos",
    [{}, {"archivo": "texto"}, {"otro": "x"}, {"archivo_reverso": None}],
    ids=["sin_archivo", "texto", "clave_desconocida", "campo_no_permitido"],
)
def test_formularios_invalidos_responden_400(maestro, datos):
    if "archivo_reverso" in datos:
        datos = {"archivo_reverso": _archivo(_imagen())}
    respuesta = _sesion().post(URL_FOTO, data=datos)
    assert respuesta.status_code == 400


def test_json_en_vez_de_multipart_responde_400(maestro):
    respuesta = _sesion().post(URL_FOTO, data="{}", content_type="application/json")
    assert respuesta.status_code == 400


def test_reemplazar_la_foto_borra_la_anterior_al_confirmar(maestro, django_capture_on_commit_callbacks):
    fotos.subir_foto(maestro, _archivo(_imagen()))
    anterior = PerfilPublico.objects.get(perfil_maestro_id=maestro.pk).foto

    with django_capture_on_commit_callbacks(execute=True):
        fotos.subir_foto(maestro, _archivo(_imagen((640, 640))))

    nueva = PerfilPublico.objects.get(perfil_maestro_id=maestro.pk).foto
    assert nueva != anterior
    nombres = sorted(p.name for p in Path(settings.ALTIRO_FOTOS_DIR).iterdir())
    assert nombres == sorted([f"{nueva}-160.jpg", f"{nueva}-480.jpg"])


def test_si_la_transaccion_falla_no_quedan_variantes_nuevas(maestro, monkeypatch):
    fotos.subir_foto(maestro, _archivo(_imagen()))
    anterior = PerfilPublico.objects.get(perfil_maestro_id=maestro.pk).foto

    def falla(*args, **kwargs):
        raise RuntimeError("simulada")

    monkeypatch.setattr(PerfilPublico, "save", falla)
    with pytest.raises(RuntimeError):
        fotos.subir_foto(maestro, _archivo(_imagen((500, 500))))

    assert PerfilPublico.objects.get(perfil_maestro_id=maestro.pk).foto == anterior
    nombres = sorted(p.name for p in Path(settings.ALTIRO_FOTOS_DIR).iterdir())
    assert nombres == sorted([f"{anterior}-160.jpg", f"{anterior}-480.jpg"])


def test_expediente_rechazado_no_cambia_la_foto(maestro):
    Expediente.objects.filter(perfil_maestro_id=maestro.pk).update(estado=EstadoExpediente.RECHAZADO)

    respuesta = _sesion().post(URL_FOTO, data={"archivo": _archivo(_imagen())})

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == fotos.MENSAJE_RECHAZADO
    assert list(Path(settings.ALTIRO_FOTOS_DIR).iterdir()) == []


# --- Perfil del maestro: qué le falta para publicarse ---


def test_el_maestro_ve_lo_que_le_falta_en_su_lenguaje(maestro, catalogo):
    client = _sesion()

    datos = client.get(URL_PERFIL).json()["perfil"]
    assert datos["publicado"] is False and datos["tiene_foto"] is False
    assert datos["ref"] == str(_ref(maestro))
    assert [p["codigo"] for p in datos["pendientes"]] == [
        "postulacion_no_aprobada", "sin_comuna_base", "sin_foto", "sin_servicio_visible",
    ]
    assert datos["pendientes"][1]["mensaje"] == MENSAJES_PENDIENTE[publicacion.SIN_COMUNA_BASE]
    assert "comuna principal" in datos["pendientes"][1]["mensaje"]

    _preparar(maestro)
    datos = client.get(URL_PERFIL).json()["perfil"]
    assert [p["codigo"] for p in datos["pendientes"]] == ["sin_servicio_visible"]
    assert datos["tiene_foto"] is True

    ServicioMaestro.objects.create(maestro_id=maestro.pk, servicio=catalogo["pintura"], modalidad=T, monto=1000)
    respuesta = client.get(URL_PERFIL)
    assert respuesta.json()["perfil"]["publicado"] is True
    assert respuesta.json()["perfil"]["pendientes"] == []
    assert respuesta["Cache-Control"] == "no-store"
    assert_campos_ausentes(respuesta, {"rut", "telefono", "correo", "foto", "id"}, valores=[RUT_CANONICO])


def test_el_expediente_suspendido_se_explica(maestro):
    Expediente.objects.filter(perfil_maestro_id=maestro.pk).update(estado=EstadoExpediente.SUSPENDIDO)
    pendientes = _sesion().get(URL_PERFIL).json()["perfil"]["pendientes"]
    assert pendientes[0] == {"codigo": "postulacion_no_aprobada", "mensaje": "Tu cuenta de maestro está suspendida."}


# --- Perfil público ---


def test_el_perfil_publico_muestra_solo_la_lista_explicita(publicado):
    respuesta = Client().get(_url(publicado))

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    datos = respuesta.json()["maestro"]
    assert set(datos) == {"ref", "nombre", "foto", "servicios", "comunas", "agenda", "bloques",
                          "calificacion", "calificacion_texto", "comentarios"}
    assert datos["nombre"] == "Maestro Uno"
    ref = _ref(publicado)
    assert datos["foto"] == {
        "160": f"/api/maestros/publicos/{ref}/foto?tam=160",
        "480": f"/api/maestros/publicos/{ref}/foto?tam=480",
    }
    assert {(s["oficio"]["codigo"], s["servicio"], s["monto"]) for s in datos["servicios"]} == {
        ("gas", "Instalación de cocina", MONTO_MARCA), ("pintura", "Pintura de habitación", MONTO_PINTURA),
    }
    assert set(datos["servicios"][0]) == {"ref", "oficio", "servicio", "modalidad", "modalidad_texto", "monto"}
    assert datos["agenda"] == [
        {"dia_semana": 1, "dia": "lunes", "inicio": "08:00", "fin": "12:00"},
        {"dia_semana": 6, "dia": "sábado", "inicio": "14:30", "fin": "24:00"},
    ]


def test_d14_las_comunas_no_indican_cual_es_la_base(publicado):
    respuesta = Client().get(_url(publicado))

    comunas = respuesta.json()["maestro"]["comunas"]
    # Talcahuano es la base y aparece al final: el orden es por nombre, no por base.
    assert comunas == [{"codigo": "8101", "nombre": "Concepción"}, {"codigo": "8110", "nombre": "Talcahuano"}]
    assert_campos_ausentes(respuesta, {"es_base", "base", "comuna_base", "principal", "comuna_principal"})


def test_privacidad_nunca_datos_personales_ni_del_expediente(publicado):
    expediente = Expediente.objects.get(perfil_maestro_id=publicado.pk)
    licencia = Documento.objects.get(expediente=expediente)
    respuesta = Client().get(_url(publicado))

    assert_campos_ausentes(
        respuesta,
        {"rut", "telefono", "correo", "documentos", "motivo", "estado_motivo", "expediente",
         "fecha_vencimiento", "fecha_emision", "licencia", "id", "perfil_maestro_id", "usuario_id", "archivo",
         "retirado_en", "creado_en", "inicio_min", "fin_min", "visible", "motivos"},
        valores=[RUT_CANONICO, "11.111.111-1", "910000001", "maestro.uno@example.com", str(expediente.ref),
                 str(licencia.ref), str(licencia.archivo), licencia.fecha_vencimiento.isoformat(), "aprobado",
                 str(PerfilPublico.objects.get(perfil_maestro_id=publicado.pk).foto)],
    )
    # "estado" solo existe en los bloques de la ficha (S4, RF-14), nunca el del expediente.
    datos = respuesta.json()["maestro"]
    assert "estado" not in datos
    assert {b["estado"] for b in datos["bloques"]} <= {"libre", "ocupado"}
    for lista in ("servicios", "comunas", "agenda"):
        assert all("estado" not in elemento for elemento in datos[lista])


@pytest.mark.parametrize(
    "caso",
    ["en_revision", "observado", "suspendido", "rechazado", "sin_base", "sin_foto", "sin_servicio_visible",
     "solo_gas_sin_licencia"],
)
def test_maestro_no_publicado_responde_404_identico_sin_registro(publicado, catalogo, caso):
    estados = {"en_revision": EstadoExpediente.EN_REVISION, "observado": EstadoExpediente.OBSERVADO,
               "suspendido": EstadoExpediente.SUSPENDIDO, "rechazado": EstadoExpediente.RECHAZADO}
    if caso in estados:
        Expediente.objects.filter(perfil_maestro_id=publicado.pk).update(estado=estados[caso])
    elif caso == "sin_base":
        Cobertura.objects.filter(maestro_id=publicado.pk).update(es_base=False)
    elif caso == "sin_foto":
        PerfilPublico.objects.filter(perfil_maestro_id=publicado.pk).update(foto=None, foto_actualizada_en=None)
    elif caso == "sin_servicio_visible":
        ServicioMaestro.objects.filter(maestro_id=publicado.pk).update(retirado_en=timezone.now())
    else:
        ServicioMaestro.objects.filter(maestro_id=publicado.pk, servicio=catalogo["pintura"]).update(
            retirado_en=timezone.now()
        )
        Documento.objects.filter(expediente__perfil_maestro_id=publicado.pk).delete()
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    assert otro

    for client in (Client(), _sesion(RUT_OTRO), _sesion(RUT)):
        for url in (_url(publicado), f"{_url(publicado)}/foto?tam=160"):
            respuesta = client.get(url)
            assert respuesta.status_code == 404, (caso, url)
            assert respuesta.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


def test_ref_inexistente_o_del_expediente_responde_el_mismo_404(publicado):
    expediente = Expediente.objects.get(perfil_maestro_id=publicado.pk)
    for ref in (uuid.uuid4(), expediente.ref):
        respuesta = Client().get(f"/api/maestros/publicos/{ref}")
        assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


def test_rnf25_ca24_1_al_vencer_la_licencia_gas_desaparece_y_pintura_sigue(publicado):
    antes = Client().get(_url(publicado)).json()["maestro"]["servicios"]
    assert {s["oficio"]["codigo"] for s in antes} == {"gas", "pintura"}

    # Vence hoy (hora de Santiago): ya no está vigente (ADR-017, punto 4).
    Documento.objects.filter(expediente__perfil_maestro_id=publicado.pk).update(fecha_vencimiento=hoy_negocio())

    respuesta = Client().get(_url(publicado))
    assert respuesta.status_code == 200
    assert [s["oficio"]["codigo"] for s in respuesta.json()["maestro"]["servicios"]] == ["pintura"]
    assert str(MONTO_MARCA) not in respuesta.content.decode()


# --- Foto pública ---


def test_la_foto_publica_se_entrega_con_cabeceras_seguras_y_revalidacion(publicado):
    url = f"{_url(publicado)}/foto"
    for tamano, lado in ((160, 160), (480, 480)):
        respuesta = Client().get(url, {"tam": tamano})
        assert respuesta.status_code == 200
        assert respuesta["Content-Type"] == "image/jpeg"
        for cabecera, valor in CABECERAS_FOTO.items():
            assert respuesta[cabecera] == valor
        assert str(PerfilPublico.objects.get(perfil_maestro_id=publicado.pk).foto) not in respuesta["ETag"]
        with Image.open(io.BytesIO(respuesta.content)) as imagen:
            assert max(imagen.size) == lado
        # Sin cambios: 304 sin cuerpo, siempre después de revisar la publicación.
        repetida = Client().get(url, {"tam": tamano}, HTTP_IF_NONE_MATCH=respuesta["ETag"])
        assert repetida.status_code == 304 and repetida.content == b""
    assert Client().get(url).status_code == 200  # sin "tam": 480

    Expediente.objects.filter(perfil_maestro_id=publicado.pk).update(estado=EstadoExpediente.SUSPENDIDO)
    etag = Client().get(url, {"tam": 160})
    assert etag.status_code == 404 and etag.content == NO_ENCONTRADO


@pytest.mark.parametrize("consulta", ["?tam=100", "?tam=abc", "?tam=160&x=1", "?tam=160&tam=480", "?tam="])
def test_tamano_no_admitido_responde_404_neutro(publicado, consulta):
    respuesta = Client().get(f"{_url(publicado)}/foto{consulta}")
    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO


# --- Terceros en las rutas públicas con identificador (RNF-07) ---


def _administrativo(rol, correo):
    return servicios_identidad.crear_cuenta_administrativa(
        nombre="Admin Prueba", correo=correo, roles=[rol], contrasena=CONTRASENA
    )


def _visitantes():
    crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    crear_cliente(correo="cliente.prueba@example.com", telefono=TEL_B)
    _administrativo(Rol.CURATORIA, "cura@example.com")
    _administrativo(Rol.COMERCIAL, "comercial@example.com")
    return [Client(), _sesion(RUT_OTRO), _sesion("cliente.prueba@example.com"), _sesion("cura@example.com"),
            _sesion("comercial@example.com")]


@pytest.mark.terceros("perfil_publico")
def test_perfil_publico_es_igual_para_todos_y_no_registra(publicado):
    cuerpos = {client.get(_url(publicado)).content for client in _visitantes()}
    assert len(cuerpos) == 1
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("perfil_publico")
def test_perfil_no_publicado_es_404_para_todos_sin_registro(maestro):
    for client in _visitantes():
        respuesta = client.get(_url(maestro))
        assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("foto_publica")
def test_foto_publica_es_igual_para_todos_y_no_registra(publicado):
    url = f"{_url(publicado)}/foto?tam=160"
    cuerpos = {client.get(url).content for client in _visitantes()}
    assert len(cuerpos) == 1
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("foto_publica")
def test_foto_de_maestro_no_publicado_es_404_para_todos_sin_registro(maestro):
    fotos.subir_foto(maestro, _archivo(_imagen()))
    for client in _visitantes():
        respuesta = client.get(f"{_url(maestro)}/foto?tam=480")
        assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_las_rutas_publicas_son_solo_de_lectura(publicado, metodo):
    for url in (_url(publicado), f"{_url(publicado)}/foto"):
        assert getattr(Client(), metodo)(url).status_code == 405


# --- RNF-25: barrido de todas las rutas públicas con combinaciones generadas ---

def _escenario_licencia(usuario, oficio, escenario):
    """Crea las licencias del escenario y dice si el oficio queda habilitado (ADR-017, punto 4 y E-1)."""
    hoy = hoy_negocio()
    futuro, pasado = hoy + datetime.timedelta(days=90), hoy - datetime.timedelta(days=1)
    hace = lambda dias: timezone.now() - datetime.timedelta(days=dias)  # noqa: E731
    V, R, O, RE = (EstadoDocumento.VALIDADO, EstadoDocumento.EN_REVISION, EstadoDocumento.OBSERVADO,
                   EstadoDocumento.REEMPLAZADO)
    if escenario == "sin_licencia":
        return False
    if escenario == "en_revision":
        _licencia(usuario, oficio, R, futuro)
        return False
    if escenario == "observada":
        _licencia(usuario, oficio, O, futuro)
        return False
    if escenario == "validada_vencida_ayer":
        _licencia(usuario, oficio, V, pasado)
        return False
    if escenario == "validada_vence_hoy":
        _licencia(usuario, oficio, V, hoy)
        return False
    if escenario == "validada_de_otro_oficio":
        otro = "electricidad" if oficio == "gas" else "gas"
        _licencia(usuario, otro, V, futuro)
        return False
    if escenario == "validada_vigente":
        _licencia(usuario, oficio, V, futuro)
        return True
    if escenario == "validada_sin_vencimiento":
        _licencia(usuario, oficio, V, None)
        return True
    if escenario == "renovacion_en_revision_con_anterior_vigente":
        _licencia(usuario, oficio, RE, futuro, cargado_en=hace(10))
        _licencia(usuario, oficio, R, futuro + datetime.timedelta(days=365))
        return True
    if escenario == "renovacion_en_revision_con_anterior_vencida":
        _licencia(usuario, oficio, RE, pasado, cargado_en=hace(10))
        _licencia(usuario, oficio, R, futuro)
        return False
    raise AssertionError(escenario)


ESCENARIOS = [
    "sin_licencia", "en_revision", "observada", "validada_vencida_ayer", "validada_vence_hoy",
    "validada_de_otro_oficio", "validada_vigente", "validada_sin_vencimiento",
    "renovacion_en_revision_con_anterior_vigente", "renovacion_en_revision_con_anterior_vencida",
]


def _urls_publicas(usuario, oficio="gas"):
    """Una URL GET por cada ruta pública, con la ref pública del maestro en las que la llevan.

    La búsqueda (S4, ADR-022) se consulta por el oficio regulado en sus dos
    comunas (la base y la otra): la tarjeta no lleva monto, así que ahí la
    marca de visibilidad es la ref pública del maestro en los resultados.
    """
    urls = []
    for ruta in rutas():
        if not ruta.publica:
            continue
        url = "/" + ruta.patron.replace("<uuid:ref>", str(_ref(usuario))).replace("<int:codigo>", "8")
        if ruta.patron == "api/busqueda":
            urls += [f"{url}?oficio={oficio}&comuna={comuna}" for comuna in ("8110", "8101")]
            continue
        urls.append(url)
        if url.endswith("/foto"):
            urls += [url + "?tam=160", url + "?tam=480"]
    return urls


def _marca(url, usuario):
    return str(_ref(usuario)).encode() if url.startswith("/api/busqueda") else str(MONTO_MARCA).encode()


@pytest.mark.regla("F-07")
@pytest.mark.parametrize(("oficio", "escenario"), list(itertools.product(["gas", "electricidad"], ESCENARIOS)))
def test_rnf25_ningun_servicio_regulado_visible_sin_licencia_habilitante(maestro, catalogo, oficio, escenario):
    _preparar(maestro, oficios=(oficio, "pintura"))
    habilitado = _escenario_licencia(maestro, oficio, escenario)
    ServicioMaestro.objects.create(maestro_id=maestro.pk, servicio=catalogo[oficio], modalidad=T, monto=MONTO_MARCA)
    ServicioMaestro.objects.create(maestro_id=maestro.pk, servicio=catalogo["pintura"], modalidad=T, monto=MONTO_PINTURA)

    urls = _urls_publicas(maestro, oficio)
    assert any("/api/maestros/publicos/" in u for u in urls) and "/api/catalogo" in urls
    assert any(u.startswith("/api/busqueda?") for u in urls)
    visto_en = []
    clientes = (Client(), _sesion())
    for url in urls:
        for client in clientes:
            respuesta = client.get(url)
            if url.startswith("/api/busqueda"):
                assert respuesta.status_code == 200, url
            if _marca(url, maestro) in respuesta.content:
                visto_en.append(url)
    assert bool(visto_en) is habilitado, (oficio, escenario, visto_en)
    if habilitado:
        assert {u for u in visto_en if u.startswith("/api/busqueda")} == {
            u for u in urls if u.startswith("/api/busqueda")
        }

    # El perfil sigue publicado por pintura; el servicio regulado solo aparece si está habilitado.
    servicios = Client().get(_url(maestro)).json()["maestro"]["servicios"]
    assert {s["oficio"]["codigo"] for s in servicios} == ({oficio, "pintura"} if habilitado else {"pintura"})
    # CA-24.4: por pintura (no regulado) aparece siempre en la búsqueda.
    pintura = Client().get("/api/busqueda", {"oficio": "pintura", "comuna": "8101"}).json()["resultados"]
    assert [t["ref"] for t in pintura] == [str(_ref(maestro))]


def test_tel_a_es_el_del_maestro_de_prueba():
    # Resguardo del valor buscado en la prueba de privacidad ("910000001").
    assert TEL_A.replace(" ", "").endswith("910000001")
