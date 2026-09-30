"""Enlace y descarga de documentos, incremento 3 del S2 (RNF-06, CA-25.2, RNF-07; ADR-011, ADR-015).

- GET /api/documentos/<uuid:ref>/enlace: dueño o curatoría (PoliticaDocumento);
  el resto, el 404 idéntico y una fila en ``acceso_denegado`` (CA-25.2).
- GET /api/documentos/<uuid:ref>/archivo?cara=…&t=…: token de 600 s ligado al
  usuario, al documento y a la cara, y la política aplicada otra vez.
Solo imágenes sintéticas generadas con Pillow y datos ficticios.
``ALTIRO_DOCUMENTOS_DIR`` apunta a un directorio temporal, nunca al volumen real.
Sin ``transaction=True``: las filas de ``acceso_denegado`` se revierten con cada prueba.
"""
import datetime
import io
import logging
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
import time_machine
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from autorizacion import enlaces
from autorizacion.models import RegistroAccesoDenegado
from comun.api import respuesta_no_encontrado
from expediente import almacenamiento
from expediente.models import Documento, EstadoDocumento, Expediente, TipoDocumento
from expediente.vistas_documentos import MENSAJE_FOTO_INVALIDA, MENSAJE_ILEGIBLE, MENSAJE_SIN_REVERSO
from identidad import servicios
from identidad.models import Rol, UsuarioRol
from tests.ayudas import CONTRASENA, TEL_B, crear_cliente, crear_maestro, iniciar_sesion, sin_texto_prohibido
from tests.privacidad import assert_campos_ausentes

pytestmark = pytest.mark.django_db

RUT_PROPIO = "11.111.111-1"
RUT_OTRO = "22.222.222-2"
CORREO_CURATORIA = "cura@example.com"
PATRON_ENLACE = "GET api/documentos/<uuid:ref>/enlace"
PATRON_ARCHIVO = "GET api/documentos/<uuid:ref>/archivo"
NO_ENCONTRADO = respuesta_no_encontrado().content

ANVERSO = almacenamiento.ANVERSO
REVERSO = almacenamiento.REVERSO


def _jpeg(color):
    salida = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(salida, format="JPEG")
    return salida.getvalue()


FOTO_ANVERSO = _jpeg((10, 120, 200))
FOTO_REVERSO = _jpeg((200, 40, 10))


# --- Fixtures y ayudas ---


@pytest.fixture(autouse=True)
def directorio_documentos(settings, tmp_path):
    directorio = tmp_path / "documentos"
    directorio.mkdir(mode=0o700)
    settings.ALTIRO_DOCUMENTOS_DIR = directorio
    return directorio


def _crear_documento(usuario, tipo=TipoDocumento.CEDULA_IDENTIDAD, estado=EstadoDocumento.EN_REVISION):
    """Documento con archivos cifrados reales en el directorio temporal."""
    ref = uuid.uuid4()
    reverso = None
    if tipo == TipoDocumento.CEDULA_IDENTIDAD:
        reverso = almacenamiento.guardar(ref, REVERSO, FOTO_REVERSO)
    return Documento.objects.create(
        ref=ref,
        expediente=Expediente.objects.get(perfil_maestro_id=usuario.pk),
        tipo=tipo,
        fecha_emision=datetime.date(2026, 1, 10),
        estado=estado,
        archivo=almacenamiento.guardar(ref, ANVERSO, FOTO_ANVERSO),
        archivo_reverso=reverso,
    )


def _administrativo(rol, correo):
    return servicios.crear_cuenta_administrativa(nombre="Admin Prueba", correo=correo, roles=[rol], contrasena=CONTRASENA)


def _sesion(identificador):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


def _url_enlace(ref, **consulta):
    return f"/api/documentos/{ref}/enlace" + (f"?{urlencode(consulta)}" if consulta else "")


def _url_archivo(ref, **consulta):
    return f"/api/documentos/{ref}/archivo" + (f"?{urlencode(consulta)}" if consulta else "")


def _pedir_enlace(client, ref, cara=ANVERSO):
    respuesta = client.get(_url_enlace(ref, cara=cara))
    assert respuesta.status_code == 200, respuesta.content
    return respuesta.json()["url"]


def _consulta(url):
    return {clave: valores[0] for clave, valores in parse_qs(urlsplit(url).query).items()}


@pytest.fixture
def maestro():
    return crear_maestro(rut=RUT_PROPIO)


@pytest.fixture
def cedula(maestro):
    return _crear_documento(maestro)


@pytest.fixture
def dueno(maestro):
    return _sesion(RUT_PROPIO)


@pytest.fixture
def curatoria():
    return _administrativo(Rol.CURATORIA, CORREO_CURATORIA)


def _terceros():
    """Cada tercero sin relación con el documento (CA-25.2 y RNF-07)."""
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


def _tercero(nombre):
    crear, identificador = _terceros()[nombre]
    return crear(), _sesion(identificador)


# --- Dueño y curatoría: acceso permitido ---


@pytest.mark.parametrize(("cara", "foto"), [(ANVERSO, FOTO_ANVERSO), (REVERSO, FOTO_REVERSO)])
def test_el_dueno_obtiene_el_enlace_y_descarga_la_foto(dueno, cedula, cara, foto):
    antes = datetime.datetime.now(datetime.timezone.utc)
    respuesta = dueno.get(_url_enlace(cedula.ref, cara=cara))

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    datos = respuesta.json()
    assert set(datos) == {"url", "caduca_en"}
    assert datos["url"].startswith(f"/api/documentos/{cedula.ref}/archivo?")
    assert set(_consulta(datos["url"])) == {"cara", "t"}
    assert _consulta(datos["url"])["cara"] == cara
    caduca = datetime.datetime.fromisoformat(datos["caduca_en"])
    assert caduca.tzinfo is not None
    assert datetime.timedelta(seconds=599) <= caduca - antes <= datetime.timedelta(seconds=601)

    archivo = dueno.get(datos["url"])

    assert archivo.status_code == 200
    assert archivo.content == foto
    assert not RegistroAccesoDenegado.objects.exists()


def test_sin_cara_el_enlace_es_de_la_foto_de_adelante(dueno, cedula):
    respuesta = dueno.get(_url_enlace(cedula.ref))

    assert respuesta.status_code == 200
    assert _consulta(respuesta.json()["url"])["cara"] == ANVERSO
    assert dueno.get(respuesta.json()["url"]).content == FOTO_ANVERSO


@pytest.mark.parametrize(("cara", "foto"), [(ANVERSO, FOTO_ANVERSO), (REVERSO, FOTO_REVERSO)])
def test_curatoria_obtiene_el_enlace_y_descarga_la_foto(curatoria, cedula, cara, foto):
    client = _sesion(CORREO_CURATORIA)

    archivo = client.get(_pedir_enlace(client, cedula.ref, cara))

    assert archivo.status_code == 200
    assert archivo.content == foto
    assert not RegistroAccesoDenegado.objects.exists()


def test_un_maestro_con_rol_curatoria_abre_documentos_ajenos_por_su_funcion(cedula):
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    servicios.asignar_rol_administrativo(otro, Rol.CURATORIA)
    client = _sesion(RUT_OTRO)

    assert client.get(_pedir_enlace(client, cedula.ref)).content == FOTO_ANVERSO


def test_el_dueno_con_rol_curatoria_abre_su_propio_documento_como_dueno(maestro, cedula):
    # Estas rutas no son de curatoría: el conflicto de interés (ADR-011, E-2) no aplica.
    servicios.asignar_rol_administrativo(maestro, Rol.CURATORIA)
    client = _sesion(RUT_PROPIO)

    assert client.get(_pedir_enlace(client, cedula.ref)).content == FOTO_ANVERSO


def test_la_foto_subida_por_la_api_se_descarga_descifrada(dueno, maestro, directorio_documentos):
    subida = dueno.post(
        "/api/maestros/expediente/documentos",
        data={
            "tipo": TipoDocumento.CERTIFICADO_ANTECEDENTES,
            "fecha_emision": "2026-01-10",
            "archivo": SimpleUploadedFile("foto.jpg", FOTO_ANVERSO, content_type="image/jpeg"),
        },
    )
    assert subida.status_code == 201
    documento = Documento.objects.get()

    archivo = dueno.get(_pedir_enlace(dueno, documento.ref))

    assert archivo.status_code == 200
    assert archivo.content == almacenamiento.leer(documento.ref, ANVERSO, documento.archivo)
    assert archivo.content.startswith(b"\xff\xd8")
    with Image.open(io.BytesIO(archivo.content)) as imagen:
        assert imagen.format == "JPEG"
        assert imagen.size == (32, 24)
    # En el volumen solo está cifrado.
    assert not (directorio_documentos / str(documento.archivo)).read_bytes().startswith(b"\xff\xd8")


# --- Terceros (CA-25.2, RNF-07): 404 idéntico y exactamente una fila ---


@pytest.mark.terceros("documento_enlace")
@pytest.mark.parametrize("nombre", TERCEROS)
def test_un_tercero_no_obtiene_el_enlace(cedula, nombre):
    tercero, client = _tercero(nombre)

    ajeno = client.get(_url_enlace(cedula.ref, cara=ANVERSO))
    inexistente = client.get(_url_enlace(uuid.uuid4(), cara=ANVERSO))
    ruta_inexistente = client.get("/api/no-existe")

    assert ajeno.status_code == inexistente.status_code == 404
    assert ajeno.content == inexistente.content == ruta_inexistente.content == NO_ENCONTRADO
    assert ajeno["Content-Type"] == inexistente["Content-Type"]
    assert "url" not in ajeno.json()
    fila = RegistroAccesoDenegado.objects.get()
    assert fila.usuario_id == tercero.pk
    assert fila.recurso == PATRON_ENLACE
    assert (fila.entidad, fila.entidad_ref) == ("documento", str(cedula.ref))


@pytest.mark.terceros("documento_enlace")
@pytest.mark.parametrize("nombre", ["cliente", "otro_maestro"])
def test_un_tercero_con_parametros_invalidos_recibe_igual_el_404_registrado(maestro, cedula, nombre):
    # La política va antes que los parámetros: el tercero no aprende nada del documento.
    tercero, client = _tercero(nombre)
    antecedentes = _crear_documento(maestro, tipo=TipoDocumento.CERTIFICADO_ANTECEDENTES)

    for url in (_url_enlace(cedula.ref, cara="lado"), _url_enlace(antecedentes.ref, cara=REVERSO)):
        respuesta = client.get(url)
        assert respuesta.status_code == 404
        assert respuesta.content == NO_ENCONTRADO
    assert RegistroAccesoDenegado.objects.filter(usuario_id=tercero.pk, recurso=PATRON_ENLACE).count() == 2


@pytest.mark.terceros("documento_archivo")
@pytest.mark.parametrize("nombre", TERCEROS)
def test_un_tercero_no_descarga_el_archivo_ni_con_un_token_firmado_para_el(cedula, nombre):
    tercero, client = _tercero(nombre)
    token = enlaces.firmar(cedula.ref, tercero.pk, ANVERSO)

    ajeno = client.get(_url_archivo(cedula.ref, cara=ANVERSO, t=token))
    inexistente = client.get(_url_archivo(uuid.uuid4(), cara=ANVERSO, t=token))

    assert ajeno.status_code == inexistente.status_code == 404
    assert ajeno.content == inexistente.content == NO_ENCONTRADO
    assert FOTO_ANVERSO not in ajeno.content
    fila = RegistroAccesoDenegado.objects.get()
    assert fila.usuario_id == tercero.pk
    assert fila.recurso == PATRON_ARCHIVO
    assert (fila.entidad, fila.entidad_ref) == ("documento", str(cedula.ref))


@pytest.mark.terceros("documento_archivo")
def test_un_cliente_con_el_enlace_del_dueno_no_descarga(dueno, cedula):
    """CA-25.2: un cliente no abre el documento de identidad de un maestro, ni con su enlace."""
    url = _pedir_enlace(dueno, cedula.ref)
    cliente = crear_cliente()
    client = _sesion("ana.prueba@example.com")

    respuesta = client.get(url)

    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.recurso, fila.entidad_ref) == (cliente.pk, PATRON_ARCHIVO, str(cedula.ref))


@pytest.mark.terceros("documento_enlace")
@pytest.mark.terceros("documento_archivo")
def test_anonimo_recibe_401_sin_registro(dueno, cedula):
    url = _pedir_enlace(dueno, cedula.ref)

    for ruta in (_url_enlace(cedula.ref), url):
        respuesta = Client().get(ruta)
        assert respuesta.status_code == 401
        assert FOTO_ANVERSO not in respuesta.content
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("documento_enlace")
@pytest.mark.terceros("documento_archivo")
def test_un_uuid_inexistente_no_se_registra(dueno, cedula):
    for url in (_url_enlace(uuid.uuid4()), _url_archivo(uuid.uuid4(), cara=ANVERSO, t="x")):
        assert dueno.get(url).status_code == 404
    assert not RegistroAccesoDenegado.objects.exists()


# --- Token (RNF-06): 600 s, alterado, de otro usuario, de otro documento o de otra cara ---


@pytest.mark.terceros("documento_archivo")
def test_el_enlace_vale_a_los_600_segundos_y_no_a_los_601(maestro, cedula):
    inicio = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    with time_machine.travel(inicio, tick=False) as viaje:
        client = _sesion(RUT_PROPIO)
        respuesta = client.get(_url_enlace(cedula.ref))
        url = respuesta.json()["url"]
        assert datetime.datetime.fromisoformat(respuesta.json()["caduca_en"]) == inicio + datetime.timedelta(seconds=600)

        viaje.shift(600)
        assert client.get(url).content == FOTO_ANVERSO
        viaje.shift(1)
        vencido = client.get(url)

    assert vencido.status_code == 404
    assert vencido.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


def _alterar(token):
    medio = len(token) // 2
    return token[:medio] + ("A" if token[medio] != "A" else "B") + token[medio + 1:]


@pytest.mark.terceros("documento_archivo")
def test_token_alterado_de_otro_usuario_de_otro_documento_o_de_otra_cara_responde_404(maestro, dueno, curatoria, cedula):
    otro_documento = _crear_documento(maestro, tipo=TipoDocumento.CERTIFICADO_ANTECEDENTES)
    propio = _consulta(_pedir_enlace(dueno, cedula.ref, ANVERSO))
    de_curatoria = _consulta(_pedir_enlace(_sesion(CORREO_CURATORIA), cedula.ref, ANVERSO))
    token_reverso = _consulta(_pedir_enlace(dueno, cedula.ref, REVERSO))["t"]

    intentos = {
        "alterado": _url_archivo(cedula.ref, cara=ANVERSO, t=_alterar(propio["t"])),
        "de_otro_usuario": _url_archivo(cedula.ref, **de_curatoria),
        "con_otro_documento": _url_archivo(otro_documento.ref, **propio),
        "con_otra_cara": _url_archivo(cedula.ref, cara=REVERSO, t=propio["t"]),
        "reverso_como_anverso": _url_archivo(cedula.ref, cara=ANVERSO, t=token_reverso),
        "sin_token": _url_archivo(cedula.ref, cara=ANVERSO),
        "sin_cara": _url_archivo(cedula.ref, t=propio["t"]),
        "sin_consulta": _url_archivo(cedula.ref),
        "cara_invalida": _url_archivo(cedula.ref, cara="lado", t=propio["t"]),
        "parametro_extra": _url_archivo(cedula.ref, cara=ANVERSO, t=propio["t"], x="1"),
        "token_vacio": _url_archivo(cedula.ref, cara=ANVERSO, t=""),
        "token_repetido": _url_archivo(cedula.ref) + f"?cara={ANVERSO}&t={propio['t']}&t={propio['t']}",
    }
    for motivo, url in intentos.items():
        respuesta = dueno.get(url)
        assert respuesta.status_code == 404, motivo
        assert respuesta.content == NO_ENCONTRADO, motivo
    # El dueño sí tiene relación con el documento: no es un acceso de un tercero.
    assert not RegistroAccesoDenegado.objects.exists()
    # El enlace legítimo sigue funcionando.
    assert dueno.get(_url_archivo(cedula.ref, **propio)).content == FOTO_ANVERSO


@pytest.mark.terceros("documento_archivo")
def test_quitar_el_rol_curatoria_tras_emitir_el_enlace_deniega_la_descarga(curatoria, cedula):
    client = _sesion(CORREO_CURATORIA)
    url = _pedir_enlace(client, cedula.ref)
    otro_rol = UsuarioRol.objects.create(usuario=curatoria, rol=Rol.COMERCIAL)  # la cuenta sigue siendo administrativa
    UsuarioRol.objects.filter(usuario=curatoria, rol=Rol.CURATORIA).delete()

    respuesta = client.get(url)

    assert otro_rol.pk is not None
    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.recurso, fila.entidad_ref) == (curatoria.pk, PATRON_ARCHIVO, str(cedula.ref))


# --- Parámetros del enlace: 400 accionable solo para quien tiene acceso ---


@pytest.mark.parametrize(
    "consulta",
    [{"cara": "lado"}, {"cara": ""}, {"cara": "ANVERSO"}, {"otra": "1"}, {"cara": ANVERSO, "t": "x"}],
)
def test_parametro_invalido_o_desconocido_responde_400_accionable(dueno, cedula, consulta):
    respuesta = dueno.get(_url_enlace(cedula.ref, **consulta))

    assert respuesta.status_code == 400
    assert respuesta.json() == {"mensaje": MENSAJE_FOTO_INVALIDA, "errores": {}}
    assert sin_texto_prohibido(respuesta)
    assert not RegistroAccesoDenegado.objects.exists()


def test_cara_repetida_responde_400(dueno, cedula):
    respuesta = dueno.get(f"/api/documentos/{cedula.ref}/enlace?cara={ANVERSO}&cara={REVERSO}")

    assert respuesta.status_code == 400
    assert respuesta.json()["mensaje"] == MENSAJE_FOTO_INVALIDA


@pytest.mark.parametrize("tipo", [TipoDocumento.CERTIFICADO_ANTECEDENTES, TipoDocumento.LICENCIA_SEC])
def test_el_reverso_solo_existe_en_la_cedula(maestro, dueno, tipo):
    if tipo == TipoDocumento.LICENCIA_SEC:
        from catalogo.models import Oficio

        ref = uuid.uuid4()
        documento = Documento.objects.create(
            ref=ref, expediente=Expediente.objects.get(perfil_maestro_id=maestro.pk), tipo=tipo,
            oficio=Oficio.objects.get(codigo="gas"), fecha_emision=datetime.date(2026, 1, 10),
            archivo=almacenamiento.guardar(ref, ANVERSO, FOTO_ANVERSO),
        )
    else:
        documento = _crear_documento(maestro, tipo=tipo)

    respuesta = dueno.get(_url_enlace(documento.ref, cara=REVERSO))

    assert respuesta.status_code == 400
    assert respuesta.json() == {"mensaje": MENSAJE_SIN_REVERSO, "errores": {}}
    assert dueno.get(_pedir_enlace(dueno, documento.ref)).content == FOTO_ANVERSO


# --- Documento reemplazado: solo se abre el actual ---


def test_un_documento_reemplazado_no_se_abre_y_no_se_registra_para_el_dueno(maestro, dueno, curatoria):
    viejo = _crear_documento(maestro, estado=EstadoDocumento.REEMPLAZADO)
    token = enlaces.firmar(viejo.ref, maestro.pk, ANVERSO)

    for client in (dueno, _sesion(CORREO_CURATORIA)):
        assert client.get(_url_enlace(viejo.ref)).content == NO_ENCONTRADO
    assert dueno.get(_url_archivo(viejo.ref, cara=ANVERSO, t=token)).content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("documento_enlace")
def test_un_documento_reemplazado_ajeno_se_registra_para_un_tercero(maestro):
    viejo = _crear_documento(maestro, estado=EstadoDocumento.REEMPLAZADO)
    crear_cliente()

    respuesta = _sesion("ana.prueba@example.com").get(_url_enlace(viejo.ref))

    assert respuesta.content == NO_ENCONTRADO
    assert RegistroAccesoDenegado.objects.get().entidad_ref == str(viejo.ref)


# --- Cabeceras y privacidad ---


def test_cabeceras_de_seguridad_del_archivo(dueno, cedula):
    respuesta = dueno.get(_pedir_enlace(dueno, cedula.ref))

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "image/jpeg"
    assert respuesta["Content-Disposition"] == 'inline; filename="documento.jpg"'
    assert respuesta["Cache-Control"] == "no-store, private"
    assert respuesta["X-Content-Type-Options"] == "nosniff"
    assert respuesta["Content-Security-Policy"] == "sandbox; default-src 'none'"
    assert respuesta["Cross-Origin-Resource-Policy"] == "same-origin"


def test_la_respuesta_del_enlace_no_expone_rutas_ni_nombres_internos(dueno, cedula, directorio_documentos):
    for cara in (ANVERSO, REVERSO):
        respuesta = dueno.get(_url_enlace(cedula.ref, cara=cara))
        assert_campos_ausentes(
            respuesta,
            {"archivo", "archivo_reverso", "ruta", "nombre_archivo", "id", "pk", "expediente_id", "rut", "usuario"},
            valores=[str(cedula.archivo), str(cedula.archivo_reverso), str(directorio_documentos),
                     "documentos_clave", "/secretos", "111111111"],
        )


@pytest.mark.parametrize(
    "ruta",
    [
        "/documentos/{archivo}",
        "/media/{archivo}",
        "/api/documentos/",
        "/api/documentos",
        "/api/documentos/{ref}",
        "/api/documentos/{ref}/",
        "/api/documentos/{ref}/enlace/",
        "/api/documentos/{archivo}/archivo",
        "/api/documentos/{ref}/{archivo}",
        "/api/media/{archivo}",
    ],
)
def test_rutas_adivinables_responden_404(dueno, cedula, ruta):
    respuesta = dueno.get(ruta.format(archivo=cedula.archivo, ref=cedula.ref))

    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    assert FOTO_ANVERSO not in respuesta.content


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_solo_get(dueno, cedula, metodo):
    for url in (_url_enlace(cedula.ref), _pedir_enlace(dueno, cedula.ref)):
        assert getattr(dueno, metodo)(url).status_code == 405


def test_archivo_ilegible_responde_409_accionable_y_registra_sin_datos(dueno, cedula, directorio_documentos, caplog):
    """Los documentos ilegibles del volumen (DEF-QA-008): error controlado y accionable, nunca 500."""
    url = _pedir_enlace(dueno, cedula.ref)
    (directorio_documentos / str(cedula.archivo)).unlink()
    caplog.set_level(logging.DEBUG)

    respuesta = dueno.get(url)

    assert respuesta.status_code == 409
    assert respuesta.json() == {"mensaje": MENSAJE_ILEGIBLE, "errores": {}}
    assert "cargarlo de nuevo" in MENSAJE_ILEGIBLE
    assert sin_texto_prohibido(respuesta)
    assert str(cedula.archivo) not in respuesta.content.decode("utf-8")
    errores = [r for r in caplog.records if r.name == "expediente.vistas_documentos"]
    assert len(errores) == 1 and errores[0].levelno == logging.ERROR
    texto = caplog.text + "".join(repr(r.__dict__) for r in caplog.records)
    for prohibido in (str(cedula.archivo), str(directorio_documentos), _consulta(url)["t"]):
        assert prohibido not in texto


def test_archivo_alterado_o_con_otra_clave_responde_409_sin_contenido(dueno, cedula, directorio_documentos, caplog):
    url = _pedir_enlace(dueno, cedula.ref)
    ruta = directorio_documentos / str(cedula.archivo)
    ruta.write_bytes(ruta.read_bytes()[:-1] + b"\x00")  # no descifra: como un archivo cifrado con otra clave
    caplog.set_level(logging.DEBUG)

    respuesta = dueno.get(url)

    assert respuesta.status_code == 409 and respuesta.json()["mensaje"] == MENSAJE_ILEGIBLE
    assert FOTO_ANVERSO not in respuesta.content
    assert not [r for r in caplog.records if r.name == "django.request"]


def test_el_token_no_queda_en_los_registros_de_la_aplicacion(dueno, cedula, caplog):
    caplog.set_level(logging.DEBUG)
    url = _pedir_enlace(dueno, cedula.ref)
    token = _consulta(url)["t"]

    dueno.get(url)
    dueno.get(_url_archivo(cedula.ref, cara=ANVERSO, t=_alterar(token)))  # 404: Django registra la ruta
    crear_cliente()
    _sesion("ana.prueba@example.com").get(url)  # 404 registrado en acceso_denegado

    texto = caplog.text + "".join(repr(r.__dict__) for r in caplog.records)
    assert token not in texto and _alterar(token) not in texto
    assert token not in "".join(RegistroAccesoDenegado.objects.values_list("recurso", flat=True))
