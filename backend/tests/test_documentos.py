"""Carga segura de documentos, incremento 2 del S2 (RF-04; ADR-015; ADR-017, puntos 2, 3 y 5).

- POST /api/maestros/expediente/documentos (multipart, patrón "me"): sin
  identificador en la ruta, así que la prueba de terceros de RNF-07 no le aplica.
- Contenido: JPEG y PNG por contenido, recodificados sin metadatos; HTML o
  texto disfrazados, bombas de descompresión y archivos pesados se rechazan.
- Cifrado AES-256-GCM con datos asociados (ref + cara), escritura atómica y
  permisos 0600; reemplazo D-11; privacidad de la respuesta y de los registros.
Solo imágenes sintéticas generadas aquí con Pillow; datos ficticios.
``ALTIRO_DOCUMENTOS_DIR`` apunta a un directorio temporal, nunca al volumen real.
"""
import datetime
import io
import logging
import os
import stat
import uuid

import pytest
from django.conf import settings as ajustes
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from PIL import ExifTags, Image, ImageCms

from autorizacion.models import RegistroAccesoDenegado
from catalogo.models import Oficio
from expediente import almacenamiento, imagenes
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, TipoDocumento
from expediente.servicios import declarar_oficios
from expediente.vigencia import (
    ANTECEDENTES,
    CEDULA,
    LICENCIA_SEC,
    faltantes_para_aprobar,
    hoy_negocio,
    requisitos_sin_documento,
)
from tests.ayudas import TEL_B, crear_cliente, crear_maestro, iniciar_sesion, sin_texto_prohibido
from tests.privacidad import assert_campos_ausentes

URL = "/api/maestros/expediente/documentos"
URL_EXPEDIENTE = "/api/maestros/expediente"
RUT_PROPIO = "11.111.111-1"
RUT_OTRO = "22.222.222-2"
MARCADOR = "MARCADOR-CONTENIDO-SINTETICO-7Q2"


# --- Imágenes sintéticas ---


def _jpeg(tamano=(64, 48), color=(200, 120, 40), **opciones):
    salida = io.BytesIO()
    Image.new("RGB", tamano, color).save(salida, format="JPEG", **opciones)
    return salida.getvalue()


def _png(tamano=(64, 48), modo="RGB", color=(40, 120, 200)):
    salida = io.BytesIO()
    Image.new(modo, tamano, color).save(salida, format="PNG")
    return salida.getvalue()


def _jpeg_con_gps():
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "Camara Ficticia"
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "S"
    gps[ExifTags.GPS.GPSLatitude] = (36.0, 49.0, 30.0)
    gps[ExifTags.GPS.GPSLongitudeRef] = "W"
    gps[ExifTags.GPS.GPSLongitude] = (73.0, 3.0, 0.0)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    return _jpeg(exif=exif.tobytes(), icc_profile=icc, comment=MARCADOR.encode())


def _foto(contenido=None, nombre="foto.jpg", tipo="image/jpeg"):
    return SimpleUploadedFile(nombre, _jpeg() if contenido is None else contenido, content_type=tipo)


# --- Fixtures y ayudas ---


@pytest.fixture(autouse=True)
def directorio_documentos(settings, tmp_path):
    directorio = tmp_path / "documentos"
    directorio.mkdir(mode=0o700)
    settings.ALTIRO_DOCUMENTOS_DIR = directorio
    return directorio


@pytest.fixture
def maestro():
    return crear_maestro(rut=RUT_PROPIO)


@pytest.fixture
def navegador(client, maestro):
    assert iniciar_sesion(client, RUT_PROPIO).status_code == 200
    return client


def _hoy():
    return hoy_negocio()


def _datos(tipo=ANTECEDENTES, **cambios):
    datos = {"tipo": tipo, "fecha_emision": (_hoy() - datetime.timedelta(days=30)).isoformat()}
    if tipo == CEDULA:
        datos["archivo_reverso"] = _foto(nombre="reverso.jpg")
    datos["archivo"] = _foto()
    datos.update(cambios)
    return {clave: valor for clave, valor in datos.items() if valor is not None}


def _subir(cliente, **datos):
    return cliente.post(URL, data=datos)


def _expediente(usuario):
    return Expediente.objects.get(perfil_maestro_id=usuario.pk)


def _archivos_en(directorio):
    return sorted(p.name for p in directorio.iterdir())


def _cifrado_de(directorio, nombre):
    return (directorio / str(nombre)).read_bytes()


# --- Carga válida, cifrado y recodificación ---


@pytest.mark.django_db
@pytest.mark.parametrize("contenido", [_jpeg(), _png(), _png(modo="RGBA", color=(0, 0, 0, 0)), _png(modo="L", color=90)])
def test_foto_valida_se_guarda_cifrada_y_se_descifra_a_un_jpeg(navegador, maestro, directorio_documentos, contenido):
    respuesta = _subir(navegador, **_datos(archivo=_foto(contenido)))

    assert respuesta.status_code == 201
    assert respuesta["Cache-Control"] == "no-store"
    documento = Documento.objects.get()
    assert (documento.tipo, documento.estado) == (ANTECEDENTES, EstadoDocumento.EN_REVISION)
    assert _archivos_en(directorio_documentos) == [str(documento.archivo)]
    cifrado = _cifrado_de(directorio_documentos, documento.archivo)
    assert not cifrado.startswith(b"\xff\xd8") and not cifrado.startswith(b"\x89PNG")
    claro = almacenamiento.leer(documento.ref, almacenamiento.ANVERSO, documento.archivo)
    assert claro.startswith(b"\xff\xd8")
    assert claro != contenido
    with Image.open(io.BytesIO(claro)) as imagen:
        assert imagen.format == "JPEG"
        assert imagen.size == (64, 48)


@pytest.mark.django_db
def test_la_respuesta_devuelve_el_expediente_con_lista_explicita(navegador, maestro):
    respuesta = _subir(navegador, **_datos(fecha_vencimiento=(_hoy() + datetime.timedelta(days=200)).isoformat()))

    documento = Documento.objects.get()
    datos = respuesta.json()["expediente"]
    assert datos["documentos"] == [
        {
            "ref": str(documento.ref),
            "tipo": ANTECEDENTES,
            "oficio": None,
            "estado": "en_revision",
            "fecha_emision": documento.fecha_emision.isoformat(),
            "fecha_vencimiento": documento.fecha_vencimiento.isoformat(),
        }
    ]
    assert set(datos) == {"estado", "motivo", "oficios", "documentos", "faltantes", "avisos"}


@pytest.mark.django_db
def test_sin_vencimiento_se_guarda_sin_fecha(navegador, maestro):
    """RF-04, CA-11.2: el vencimiento es opcional (vacío o ausente)."""
    assert _subir(navegador, **_datos(fecha_vencimiento="")).status_code == 201
    assert Documento.objects.get().fecha_vencimiento is None
    assert navegador.get(URL_EXPEDIENTE).json()["expediente"]["documentos"][0]["fecha_vencimiento"] is None


@pytest.mark.django_db
def test_se_eliminan_exif_gps_icc_y_comentarios(navegador, maestro):
    original = _jpeg_con_gps()
    with Image.open(io.BytesIO(original)) as imagen:
        assert imagen.getexif().get_ifd(ExifTags.IFD.GPSInfo)  # la entrada sí trae GPS
        assert "icc_profile" in imagen.info

    assert _subir(navegador, **_datos(archivo=_foto(original))).status_code == 201

    documento = Documento.objects.get()
    claro = almacenamiento.leer(documento.ref, almacenamiento.ANVERSO, documento.archivo)
    with Image.open(io.BytesIO(claro)) as imagen:
        assert len(imagen.getexif()) == 0
        assert not imagen.getexif().get_ifd(ExifTags.IFD.GPSInfo)
        assert not {"exif", "icc_profile", "comment", "xmp"} & set(imagen.info)
    for rastro in (b"Exif", b"ICC_PROFILE", b"Camara Ficticia", MARCADOR.encode()):
        assert rastro not in claro


def test_la_orientacion_exif_se_aplica_antes_de_descartarla(settings):
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6  # girada 90 grados
    resultado = imagenes.recodificar(_jpeg(tamano=(40, 20), exif=exif.tobytes()))

    with Image.open(io.BytesIO(resultado)) as imagen:
        assert imagen.size == (20, 40)
        assert len(imagen.getexif()) == 0


@pytest.mark.django_db
def test_cedula_guarda_las_dos_caras_cifradas_por_separado(navegador, maestro, directorio_documentos):
    respuesta = _subir(navegador, **_datos(tipo=CEDULA))

    assert respuesta.status_code == 201
    documento = Documento.objects.get()
    assert documento.archivo_reverso is not None
    assert _archivos_en(directorio_documentos) == sorted([str(documento.archivo), str(documento.archivo_reverso)])
    for cara, nombre in ((almacenamiento.ANVERSO, documento.archivo), (almacenamiento.REVERSO, documento.archivo_reverso)):
        assert almacenamiento.leer(documento.ref, cara, nombre).startswith(b"\xff\xd8")


@pytest.mark.django_db
def test_archivo_con_permisos_0600_y_sin_temporales(navegador, maestro, directorio_documentos):
    assert _subir(navegador, **_datos(tipo=CEDULA)).status_code == 201

    for ruta in directorio_documentos.iterdir():
        assert not ruta.name.startswith(".")
        assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o600
        uuid.UUID(ruta.name)  # el nombre es un UUID generado por el servidor
    assert "foto.jpg" not in _archivos_en(directorio_documentos)


@pytest.mark.django_db
def test_licencia_de_oficio_regulado_declarado(navegador, maestro):
    declarar_oficios(_expediente(maestro), ["gas", "ejemplo_1"])

    respuesta = _subir(
        navegador,
        **_datos(tipo=LICENCIA_SEC, oficio="gas", fecha_vencimiento=(_hoy() + datetime.timedelta(days=365)).isoformat()),
    )

    assert respuesta.status_code == 201
    assert Documento.objects.get().oficio.codigo == "gas"
    assert respuesta.json()["expediente"]["documentos"][0]["oficio"] == {"codigo": "gas", "nombre": "Gas"}


# --- Cifrado: datos asociados ---


@pytest.mark.django_db
def test_intercambiar_archivos_entre_documentos_impide_descifrar(navegador, maestro, directorio_documentos):
    assert _subir(navegador, **_datos(tipo=ANTECEDENTES)).status_code == 201
    assert _subir(navegador, **_datos(tipo=CEDULA)).status_code == 201
    antecedentes = Documento.objects.get(tipo=ANTECEDENTES)
    cedula = Documento.objects.get(tipo=CEDULA)

    # El archivo de otro documento, o la otra cara del mismo, no se descifra.
    with pytest.raises(almacenamiento.ArchivoIlegible):
        almacenamiento.leer(antecedentes.ref, almacenamiento.ANVERSO, cedula.archivo)
    with pytest.raises(almacenamiento.ArchivoIlegible):
        almacenamiento.leer(cedula.ref, almacenamiento.ANVERSO, cedula.archivo_reverso)
    # Tampoco si se copia el contenido cifrado sobre el archivo de otro registro.
    (directorio_documentos / str(antecedentes.archivo)).write_bytes(_cifrado_de(directorio_documentos, cedula.archivo))
    with pytest.raises(almacenamiento.ArchivoIlegible):
        almacenamiento.leer(antecedentes.ref, almacenamiento.ANVERSO, antecedentes.archivo)


def test_archivo_alterado_o_inexistente_es_ilegible(settings, directorio_documentos):
    ref = uuid.uuid4()
    nombre = almacenamiento.guardar(ref, almacenamiento.ANVERSO, b"contenido de prueba")
    ruta = directorio_documentos / str(nombre)
    alterado = bytearray(ruta.read_bytes())
    alterado[-1] ^= 1
    ruta.write_bytes(bytes(alterado))

    with pytest.raises(almacenamiento.ArchivoIlegible):
        almacenamiento.leer(ref, almacenamiento.ANVERSO, nombre)
    with pytest.raises(almacenamiento.ArchivoIlegible):
        almacenamiento.leer(ref, almacenamiento.ANVERSO, uuid.uuid4())


def test_otra_clave_no_descifra(settings, directorio_documentos):
    ref = uuid.uuid4()
    nombre = almacenamiento.guardar(ref, almacenamiento.ANVERSO, b"contenido de prueba")
    settings.ALTIRO_DOCUMENTOS_KEY = bytes(32)

    with pytest.raises(almacenamiento.ArchivoIlegible):
        almacenamiento.leer(ref, almacenamiento.ANVERSO, nombre)


def test_el_nonce_es_aleatorio_por_archivo(settings, directorio_documentos):
    ref = uuid.uuid4()
    uno = almacenamiento.guardar(ref, almacenamiento.ANVERSO, b"mismo contenido")
    dos = almacenamiento.guardar(ref, almacenamiento.ANVERSO, b"mismo contenido")

    primero, segundo = (_cifrado_de(directorio_documentos, n) for n in (uno, dos))
    assert primero[:12] != segundo[:12]
    assert primero != segundo


# --- Contenido rechazado ---


@pytest.mark.django_db
@pytest.mark.parametrize(
    "contenido",
    [
        b"<!doctype html><html><script>alert(1)</script></html>",
        b"texto plano que no es una foto",
        b"\xff\xd8\xff\xe0 cabecera JPEG sin imagen",
        _jpeg()[:200],  # truncado
        b"GIF89a" + _png()[6:],
    ],
)
def test_archivo_que_no_es_jpeg_ni_png_responde_400_en_el_campo(navegador, maestro, directorio_documentos, contenido):
    respuesta = _subir(navegador, **_datos(archivo=_foto(contenido, nombre="documento.jpg", tipo="image/jpeg")))

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"archivo": imagenes.MENSAJE_FORMATO}
    assert sin_texto_prohibido(respuesta)
    assert not Documento.objects.exists()
    assert _archivos_en(directorio_documentos) == []


@pytest.mark.django_db
def test_otros_formatos_de_imagen_no_se_aceptan(navegador, maestro):
    salida = io.BytesIO()
    Image.new("RGB", (10, 10)).save(salida, format="GIF")

    respuesta = _subir(navegador, **_datos(archivo=_foto(salida.getvalue(), nombre="foto.png", tipo="image/png")))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"archivo"}


@pytest.mark.django_db
def test_bomba_de_descompresion_responde_400(navegador, maestro, directorio_documentos):
    # 6000 x 6000 = 36 MP en un PNG de pocos KB (supera MAXIMO_PIXELES).
    bomba = _png(tamano=(6000, 6000), modo="L", color=0)
    assert len(bomba) < 200_000

    respuesta = _subir(navegador, **_datos(archivo=_foto(bomba, nombre="foto.png", tipo="image/png")))

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"archivo": imagenes.MENSAJE_PIXELES}
    assert not Documento.objects.exists()
    assert _archivos_en(directorio_documentos) == []


@pytest.mark.parametrize("tamano", [(12, 12), (40, 40)])
def test_limite_propio_de_pillow_es_error_de_validacion(monkeypatch, tamano):
    """DecompressionBombWarning (sobre el límite) y DecompressionBombError (sobre el doble)."""
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)

    with pytest.raises(imagenes.ImagenInvalida) as error:
        imagenes.recodificar(_png(tamano=tamano))

    assert error.value.mensaje == imagenes.MENSAJE_PIXELES


@pytest.mark.django_db
def test_foto_de_mas_de_8_mb_responde_400_con_mensaje(navegador, maestro, directorio_documentos):
    pesada = _jpeg() + b"\x00" * (8 * 1024 * 1024)

    respuesta = _subir(navegador, **_datos(archivo=_foto(pesada)))

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"archivo": imagenes.MENSAJE_PESO}
    assert "8 MB" in imagenes.MENSAJE_PESO
    assert not Documento.objects.exists()


def test_foto_justo_bajo_el_limite_de_peso_se_evalua_por_contenido():
    with pytest.raises(imagenes.ImagenInvalida) as error:
        imagenes.recodificar(b"x" * ajustes.ALTIRO_DOCUMENTO_MAXIMO_BYTES)
    assert error.value.mensaje == imagenes.MENSAJE_FORMATO
    with pytest.raises(imagenes.ImagenInvalida) as error:
        imagenes.recodificar(b"x" * (ajustes.ALTIRO_DOCUMENTO_MAXIMO_BYTES + 1))
    assert error.value.mensaje == imagenes.MENSAJE_PESO


@pytest.mark.django_db
def test_peticion_sobre_el_maximo_total_responde_413_sin_escribir_a_disco(navegador, maestro, directorio_documentos):
    enorme = b"\x00" * (ajustes.FILE_UPLOAD_MAX_MEMORY_SIZE + 1)

    respuesta = _subir(navegador, **_datos(archivo=_foto(enorme)))

    assert respuesta.status_code == 413
    assert "8 MB" in respuesta.json()["mensaje"]
    assert sin_texto_prohibido(respuesta)
    assert not Documento.objects.exists()


# --- Validación de campos (RF-04, CA-11.2, RF-33) ---


def _dias(n):
    return (_hoy() + datetime.timedelta(days=n)).isoformat()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"tipo": "pasaporte"}, "tipo"),
        ({"tipo": None}, "tipo"),
        ({"fecha_emision": None}, "fecha_emision"),
        ({"fecha_emision": "28-09-2026"}, "fecha_emision"),
        ({"fecha_emision": "2026-02-30"}, "fecha_emision"),
        ({"fecha_emision": _dias(1)}, "fecha_emision"),
        ({"fecha_emision": _dias(-10), "fecha_vencimiento": _dias(-10)}, "fecha_vencimiento"),
        ({"fecha_emision": _dias(-10), "fecha_vencimiento": _dias(-20)}, "fecha_vencimiento"),
        ({"fecha_emision": _dias(-10), "fecha_vencimiento": _dias(0)}, "fecha_vencimiento"),  # ya vencido
        ({"fecha_emision": _dias(-400), "fecha_vencimiento": _dias(-1)}, "fecha_vencimiento"),  # ya vencido
        ({"fecha_vencimiento": "mañana"}, "fecha_vencimiento"),
        ({"archivo": None}, "archivo"),
        ({"oficio": "gas"}, "oficio"),  # el oficio solo va en la licencia
        ({"archivo_reverso": _foto()}, "archivo_reverso"),  # el reverso solo va en la cédula
    ],
)
def test_campo_invalido_responde_400_en_el_campo_sin_guardar(navegador, maestro, directorio_documentos, cambios, campo):
    respuesta = _subir(navegador, **_datos(**cambios))

    assert respuesta.status_code == 400
    assert campo in respuesta.json()["errores"]
    assert sin_texto_prohibido(respuesta)
    assert not Documento.objects.exists()
    assert _archivos_en(directorio_documentos) == []


@pytest.mark.django_db
def test_documento_ya_vencido_tiene_mensaje_accionable(navegador, maestro):
    respuesta = _subir(navegador, **_datos(fecha_emision=_dias(-400), fecha_vencimiento=_dias(-1)))

    mensaje = respuesta.json()["errores"]["fecha_vencimiento"]
    assert "venció" in mensaje and "vigente" in mensaje


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("archivos", "campo"),
    [({"archivo": None}, "archivo"), ({"archivo_reverso": None}, "archivo_reverso")],
)
def test_cedula_exige_las_dos_caras(navegador, maestro, archivos, campo):
    respuesta = _subir(navegador, **_datos(tipo=CEDULA, **archivos))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {campo}
    assert not Documento.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("oficio", "declarados"),
    [(None, ["gas"]), ("ejemplo_1", ["ejemplo_1"]), ("no_existe", ["gas"]), ("GAS", ["gas"]), ("gas", ["electricidad"])],
)
def test_licencia_exige_oficio_regulado_y_declarado(navegador, maestro, directorio_documentos, oficio, declarados):
    declarar_oficios(_expediente(maestro), declarados)

    respuesta = _subir(navegador, **_datos(tipo=LICENCIA_SEC, oficio=oficio))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"oficio"}
    assert "no_existe" not in respuesta.content.decode("utf-8")
    assert not Documento.objects.exists()
    assert _archivos_en(directorio_documentos) == []


@pytest.mark.django_db
def test_varios_errores_se_informan_juntos(navegador, maestro):
    respuesta = _subir(navegador, tipo=CEDULA, fecha_emision=_dias(3))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"fecha_emision", "archivo", "archivo_reverso"}


# --- Estado del expediente ---


@pytest.mark.django_db
def test_expediente_rechazado_responde_409_sin_guardar(navegador, maestro, directorio_documentos):
    Expediente.objects.filter(perfil_maestro_id=maestro.pk).update(estado=EstadoExpediente.RECHAZADO)

    respuesta = _subir(navegador, **_datos())

    assert respuesta.status_code == 409
    assert "rechazado" in respuesta.json()["mensaje"]
    assert sin_texto_prohibido(respuesta)
    assert not Documento.objects.exists()
    assert _archivos_en(directorio_documentos) == []
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "estado",
    [EstadoExpediente.EN_REVISION, EstadoExpediente.OBSERVADO, EstadoExpediente.APROBADO, EstadoExpediente.SUSPENDIDO],
)
def test_se_carga_en_los_demas_estados_sin_cambiar_el_del_expediente(navegador, maestro, estado):
    Expediente.objects.filter(perfil_maestro_id=maestro.pk).update(estado=estado)

    assert _subir(navegador, **_datos()).status_code == 201
    assert _expediente(maestro).estado == estado


# --- Reemplazo (D-11) y reintentos ---


@pytest.mark.django_db
def test_reemplazar_un_documento_sin_revisar_borra_fila_y_archivo(
    navegador, maestro, directorio_documentos, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        assert _subir(navegador, **_datos(tipo=CEDULA)).status_code == 201
    primero = Documento.objects.get()

    with django_capture_on_commit_callbacks(execute=True):
        assert _subir(navegador, **_datos(tipo=CEDULA)).status_code == 201

    segundo = Documento.objects.get()
    assert segundo.ref != primero.ref
    assert segundo.reemplaza_a_id is None
    assert _archivos_en(directorio_documentos) == sorted([str(segundo.archivo), str(segundo.archivo_reverso)])


@pytest.mark.django_db
def test_el_archivo_anterior_no_se_borra_si_la_transaccion_no_se_confirma(
    navegador, maestro, directorio_documentos, django_capture_on_commit_callbacks
):
    assert _subir(navegador, **_datos()).status_code == 201
    primero = Documento.objects.get()

    with django_capture_on_commit_callbacks(execute=False) as pendientes:
        assert _subir(navegador, **_datos()).status_code == 201

    assert len(pendientes) == 1  # borrado agendado para después del commit
    assert str(primero.archivo) in _archivos_en(directorio_documentos)


@pytest.mark.django_db
@pytest.mark.parametrize("estado_revisado", [EstadoDocumento.VALIDADO, EstadoDocumento.OBSERVADO])
def test_reemplazar_un_documento_revisado_lo_conserva_como_reemplazado(
    navegador, maestro, directorio_documentos, django_capture_on_commit_callbacks, estado_revisado
):
    assert _subir(navegador, **_datos()).status_code == 201
    Documento.objects.update(estado=estado_revisado, motivo_observacion="Foto borrosa, repítela.")
    revisado = Documento.objects.get()

    with django_capture_on_commit_callbacks(execute=True):
        assert _subir(navegador, **_datos()).status_code == 201
    intermedio = Documento.objects.get(estado=EstadoDocumento.EN_REVISION)
    # Un nuevo reintento sustituye al que nadie revisó y conserva la cadena.
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = _subir(navegador, **_datos())

    revisado.refresh_from_db()
    actual = Documento.objects.get(estado=EstadoDocumento.EN_REVISION)
    assert revisado.estado == EstadoDocumento.REEMPLAZADO
    assert not Documento.objects.filter(pk=intermedio.pk).exists()
    assert actual.reemplaza_a_id == revisado.pk
    assert Documento.objects.count() == 2
    assert _archivos_en(directorio_documentos) == sorted([str(revisado.archivo), str(actual.archivo)])
    assert almacenamiento.leer(revisado.ref, almacenamiento.ANVERSO, revisado.archivo).startswith(b"\xff\xd8")
    assert [d["ref"] for d in respuesta.json()["expediente"]["documentos"]] == [str(actual.ref)]


@pytest.mark.django_db
def test_reintentar_la_misma_subida_no_duplica(navegador, maestro, directorio_documentos, django_capture_on_commit_callbacks):
    for _ in range(3):
        with django_capture_on_commit_callbacks(execute=True):
            assert _subir(navegador, **_datos()).status_code == 201

    assert Documento.objects.count() == 1
    assert len(_archivos_en(directorio_documentos)) == 1
    assert len(navegador.get(URL_EXPEDIENTE).json()["expediente"]["documentos"]) == 1


@pytest.mark.django_db
def test_licencias_de_distintos_oficios_no_se_reemplazan_entre_si(navegador, maestro):
    declarar_oficios(_expediente(maestro), ["gas", "electricidad"])

    for oficio in ("gas", "electricidad", "gas"):
        assert _subir(navegador, **_datos(tipo=LICENCIA_SEC, oficio=oficio)).status_code == 201

    assert sorted(Documento.objects.values_list("oficio__codigo", flat=True)) == ["electricidad", "gas"]


@pytest.mark.django_db
def test_si_falla_la_transaccion_no_quedan_archivos_nuevos(navegador, maestro, directorio_documentos, monkeypatch):
    def falla(*args, **kwargs):
        raise IntegrityError("falla forzada")

    monkeypatch.setattr(Documento.objects, "create", falla)
    with pytest.raises(IntegrityError):
        _subir(navegador, **_datos(tipo=CEDULA))

    assert _archivos_en(directorio_documentos) == []


# --- Restricciones de la base de datos ---


def _documento(expediente, **cambios):
    campos = {
        "expediente": expediente,
        "tipo": ANTECEDENTES,
        "fecha_emision": datetime.date(2026, 1, 10),
        "archivo": uuid.uuid4(),
    }
    campos.update(cambios)
    return Documento.objects.create(**campos)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "cambios",
    [
        {"tipo": "pasaporte"},
        {"estado": "borrado"},
        {"tipo": LICENCIA_SEC},  # licencia sin oficio
        {"oficio_codigo": "gas"},  # oficio en un documento que no es licencia
        {"fecha_vencimiento": datetime.date(2026, 1, 10)},
        {"fecha_vencimiento": datetime.date(2025, 1, 10)},
        {"estado": EstadoDocumento.OBSERVADO},  # sin motivo
        {"estado": EstadoDocumento.OBSERVADO, "motivo_observacion": "   "},
        {"tipo": CEDULA},  # sin reverso
        {"archivo_reverso": "nuevo"},  # reverso fuera de la cédula
    ],
)
def test_la_bd_rechaza_documentos_incoherentes(maestro, cambios):
    cambios = dict(cambios)
    if "oficio_codigo" in cambios:
        cambios["oficio"] = Oficio.objects.get(codigo=cambios.pop("oficio_codigo"))
    if cambios.get("archivo_reverso") == "nuevo":
        cambios["archivo_reverso"] = uuid.uuid4()
    with pytest.raises(IntegrityError), transaction.atomic():
        _documento(_expediente(maestro), **cambios)


@pytest.mark.django_db
def test_la_bd_admite_un_solo_documento_actual_por_tipo_y_oficio(maestro):
    expediente = _expediente(maestro)
    gas = Oficio.objects.get(codigo="gas")
    _documento(expediente)
    _documento(expediente, tipo=LICENCIA_SEC, oficio=gas)

    for cambios in ({}, {"tipo": LICENCIA_SEC, "oficio": gas}):
        with pytest.raises(IntegrityError), transaction.atomic():
            _documento(expediente, **cambios)

    # Los reemplazados no cuentan; otro oficio u otro maestro tampoco chocan.
    _documento(expediente, estado=EstadoDocumento.REEMPLAZADO)
    _documento(expediente, tipo=LICENCIA_SEC, oficio=Oficio.objects.get(codigo="electricidad"))
    _documento(_expediente(crear_maestro(rut=RUT_OTRO, telefono=TEL_B)))


@pytest.mark.django_db
def test_el_documento_no_se_borra_en_cascada(maestro):
    from django.db.models import ProtectedError

    _documento(_expediente(maestro))

    with pytest.raises(ProtectedError):
        _expediente(maestro).delete()


# --- Faltantes (ADR-017, punto 3) ---


@pytest.mark.django_db
def test_faltantes_del_maestro_cuentan_documentos_entregados_y_la_aprobacion_exige_validados(navegador, maestro):
    expediente = _expediente(maestro)
    declarar_oficios(expediente, ["gas"])
    gas = Oficio.objects.get(codigo="gas")

    respuesta = _subir(navegador, **_datos(tipo=CEDULA))

    assert respuesta.json()["expediente"]["faltantes"] == [
        {"tipo": ANTECEDENTES, "oficio": None},
        {"tipo": LICENCIA_SEC, "oficio": {"codigo": "gas", "nombre": "Gas"}},
    ]
    assert requisitos_sin_documento(expediente) == [(ANTECEDENTES, None), (LICENCIA_SEC, gas)]
    # Para aprobar, un documento en revisión no basta.
    assert faltantes_para_aprobar(expediente) == [(CEDULA, None), (ANTECEDENTES, None), (LICENCIA_SEC, gas)]

    Documento.objects.filter(tipo=CEDULA).update(estado=EstadoDocumento.VALIDADO)
    assert faltantes_para_aprobar(expediente) == [(ANTECEDENTES, None), (LICENCIA_SEC, gas)]


@pytest.mark.django_db
def test_una_licencia_validada_pero_vencida_sigue_faltando_para_aprobar(maestro):
    expediente = _expediente(maestro)
    declarar_oficios(expediente, ["gas"])
    gas = Oficio.objects.get(codigo="gas")
    _documento(
        expediente, tipo=LICENCIA_SEC, oficio=gas, estado=EstadoDocumento.VALIDADO,
        fecha_vencimiento=datetime.date(2026, 6, 1),
    )

    assert (LICENCIA_SEC, gas) in faltantes_para_aprobar(expediente, hoy=datetime.date(2026, 6, 1))
    assert (LICENCIA_SEC, gas) not in faltantes_para_aprobar(expediente, hoy=datetime.date(2026, 5, 31))


# --- Disciplina de campos (ADR-013, E-2) y formato del cuerpo ---


@pytest.mark.django_db
@pytest.mark.parametrize("extra", [{"estado": "validado"}, {"expediente": "1"}, {"<script>": "x"}])
def test_clave_desconocida_responde_400_general(navegador, maestro, extra):
    respuesta = _subir(navegador, **_datos(), **extra)

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {}
    for clave in extra:
        assert clave not in respuesta.content.decode("utf-8")
    assert not Documento.objects.exists()


@pytest.mark.django_db
def test_archivo_desconocido_responde_400_general(navegador, maestro):
    respuesta = _subir(navegador, **_datos(), ruta=_foto())

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {}


@pytest.mark.django_db
def test_campo_conocido_no_permitido_responde_400_en_el_campo(navegador, maestro):
    respuesta = _subir(navegador, **_datos(), rut=RUT_OTRO)

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"rut"}


@pytest.mark.django_db
def test_foto_enviada_como_texto_o_texto_como_archivo_responde_400_en_el_campo(navegador, maestro):
    como_texto = _subir(navegador, **_datos(archivo="no es un archivo"))
    como_archivo = _subir(navegador, **_datos(), fecha_vencimiento=_foto())

    assert set(como_texto.json()["errores"]) == {"archivo"}
    assert set(como_archivo.json()["errores"]) == {"fecha_vencimiento"}
    assert not Documento.objects.exists()


@pytest.mark.django_db
def test_valor_repetido_responde_400_en_el_campo(navegador, maestro):
    respuesta = _subir(navegador, **_datos(tipo=[ANTECEDENTES, CEDULA]))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"tipo"}


@pytest.mark.django_db
def test_cuerpo_json_responde_400_general(navegador, maestro):
    respuesta = navegador.post(URL, data={"tipo": ANTECEDENTES}, content_type="application/json")

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {}


@pytest.mark.django_db
def test_multipart_ilegible_responde_400_en_json(navegador, maestro):
    respuesta = navegador.generic("POST", URL, b"--x\r\nbasura", content_type="multipart/form-data")

    assert respuesta.status_code == 400
    assert set(respuesta.json()) == {"mensaje", "errores"}
    assert sin_texto_prohibido(respuesta)


@pytest.mark.django_db
def test_mas_de_dos_archivos_responde_400_en_json(navegador, maestro):
    respuesta = _subir(navegador, **_datos(tipo=CEDULA), otro=_foto())

    assert respuesta.status_code == 400
    assert set(respuesta.json()) == {"mensaje", "errores"}
    assert not Documento.objects.exists()


@pytest.mark.django_db
def test_get_no_esta_disponible(navegador):
    assert navegador.get(URL).status_code == 405


# --- Autorización ---


@pytest.mark.django_db
def test_sin_sesion_responde_401(client, maestro, directorio_documentos):
    respuesta = _subir(client, **_datos())

    assert respuesta.status_code == 401
    assert not Documento.objects.exists()
    assert _archivos_en(directorio_documentos) == []


@pytest.mark.django_db
def test_cliente_recibe_403_registrado(client, directorio_documentos):
    cliente = crear_cliente()
    assert iniciar_sesion(client, "ana.prueba@example.com").status_code == 200

    respuesta = _subir(client, **_datos())

    assert respuesta.status_code == 403
    assert sin_texto_prohibido(respuesta)
    assert RegistroAccesoDenegado.objects.filter(usuario_id=cliente.pk, entidad="ruta").count() == 1
    assert not Documento.objects.exists()
    assert _archivos_en(directorio_documentos) == []


@pytest.mark.django_db
def test_el_documento_queda_en_el_expediente_propio(navegador, maestro):
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)

    assert _subir(navegador, **_datos()).status_code == 201

    assert Documento.objects.get().expediente == _expediente(maestro)
    assert not Documento.objects.filter(expediente=_expediente(otro)).exists()


# --- Privacidad de la respuesta y de los registros ---


@pytest.mark.django_db
def test_la_respuesta_no_expone_archivos_rutas_ni_revisor(navegador, maestro, directorio_documentos):
    assert _subir(navegador, **_datos(tipo=CEDULA)).status_code == 201
    documento = Documento.objects.get()

    for respuesta in (_subir(navegador, **_datos(tipo=CEDULA)), navegador.get(URL_EXPEDIENTE)):
        documento = Documento.objects.get()
        assert_campos_ausentes(
            respuesta,
            {"archivo", "archivo_reverso", "ruta", "nombre_archivo", "id", "pk", "expediente_id",
             "revisado_por", "revisado_por_id", "revisado_en", "reemplaza_a", "reemplaza_a_id", "motivo_observacion",
             "cargado_en", "rut"},
            valores=[str(documento.archivo), str(documento.archivo_reverso), str(directorio_documentos), "foto.jpg",
                     "reverso.jpg", "/documentos", "111111111"],
        )


@pytest.mark.django_db
def test_los_registros_no_contienen_la_clave_ni_el_contenido(navegador, maestro, caplog):
    caplog.set_level(logging.DEBUG)
    original = _jpeg_con_gps()

    assert _subir(navegador, **_datos(archivo=_foto(original))).status_code == 201
    assert _subir(navegador, **_datos(archivo=_foto(b"<html>" + MARCADOR.encode()))).status_code == 400
    Expediente.objects.filter(perfil_maestro_id=maestro.pk).update(estado=EstadoExpediente.RECHAZADO)
    assert _subir(navegador, **_datos()).status_code == 409

    texto = caplog.text + "".join(repr(r.__dict__) for r in caplog.records)
    clave = ajustes.ALTIRO_DOCUMENTOS_KEY
    for prohibido in (clave.hex(), clave.hex().upper(), repr(clave), MARCADOR, "Camara Ficticia", "foto.jpg"):
        assert prohibido not in texto


def test_la_clave_se_oculta_en_los_informes_de_error_de_django():
    from django.views.debug import SafeExceptionReporterFilter

    ajustes_seguros = SafeExceptionReporterFilter().get_safe_settings()

    assert ajustes_seguros["ALTIRO_DOCUMENTOS_KEY"] != ajustes.ALTIRO_DOCUMENTOS_KEY
    assert ajustes.ALTIRO_DOCUMENTOS_KEY.hex() not in repr(ajustes_seguros)


def test_tipos_de_documento_unificados_con_los_requisitos():
    assert {CEDULA, ANTECEDENTES, LICENCIA_SEC} == set(TipoDocumento.values)


def test_pillow_no_escribe_metadatos_en_los_registros():
    # Pillow registra en DEBUG los valores EXIF (GPS incluido) al leer una foto.
    assert logging.getLogger("PIL").getEffectiveLevel() >= logging.WARNING
