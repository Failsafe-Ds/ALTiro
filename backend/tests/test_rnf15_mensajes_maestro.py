"""RNF-15 y RNF-17: evidencia automática de los mensajes de error que ve el maestro.

Dos pruebas complementarias, pensadas para no depender de una lista copiada de
textos (si se agrega un mensaje nuevo, entra solo):

1. Recorrido del código fuente del backend (AST): todo texto que se entrega a
   ``ErrorValidacion``, ``ErrorEstado``, ``ErroresValidacion``,
   ``ErroresDeCampo``, ``ErrorSolicitud``, ``ImagenInvalida`` o
   ``respuesta_error``, y toda constante ``MENSAJE*``, se revisa contra
   ``TEXTO_PROHIBIDO`` (texto de programador, RNF-15). Incluye los mensajes de
   curatoría, que pueden decir "expediente".
2. Recorrido por la API del maestro: se provoca cada error que puede ver un
   maestro (postulación, inicio de sesión, oficios, documentos y errores
   generales) y se revisa el JSON recibido contra ``TEXTO_PROHIBIDO`` más los
   términos que RNF-17 excluye del lenguaje del maestro.
3. Servicios del maestro (S3): errores de sus servicios y los motivos y
   pendientes que explican por qué los clientes no ven un servicio.
Datos ficticios; imágenes sintéticas; ``ALTIRO_DOCUMENTOS_DIR`` temporal.
"""
import ast
import datetime
import io
import json
import uuid
from pathlib import Path

import pytest
from django.test import Client
from PIL import Image

from catalogo.models import Oficio, Servicio, ServicioModalidad
from expediente import servicios as expedientes
from expediente.models import EstadoExpediente, Expediente
from expediente.vigencia import ANTECEDENTES, CEDULA, LICENCIA_SEC, hoy_negocio
from perfil import publicacion
from perfil.vistas import MENSAJES_MOTIVO, MENSAJES_PENDIENTE, MENSAJES_POSTULACION
from tests.ayudas import (
    TEL_B,
    TEXTO_PROHIBIDO,
    URL_CLIENTES,
    URL_POSTULACIONES,
    crear_maestro,
    datos_maestro,
    iniciar_sesion,
    post_json,
)

# RNF-17: términos que no se usan en lo que ve el maestro (jerga, unidades, pantallas).
TERMINOS_RNF17 = ["expediente", "perfil", "solicitud", "resolución", " MB", "navegador", "pestaña"]
PROHIBIDO_PARA_EL_MAESTRO = TEXTO_PROHIBIDO + TERMINOS_RNF17

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
RUT_PROPIO = "11.111.111-1"
URL_OFICIOS = "/api/maestros/expediente/oficios"
URL_DOCUMENTOS = "/api/maestros/expediente/documentos"


# --- 1. Recorrido del código fuente ---

_CONSTRUCTORES_DE_ERROR = {
    "ErrorValidacion", "ErrorEstado", "ErroresValidacion", "ErroresDeCampo", "ErrorSolicitud",
    "ImagenInvalida", "respuesta_error",
}


def _nombre_llamado(nodo):
    funcion = nodo.func
    return funcion.id if isinstance(funcion, ast.Name) else getattr(funcion, "attr", None)


def _textos(nodo):
    """Textos literales dentro de ``nodo`` (incluidas las partes fijas de un f-string)."""
    return [n.value for n in ast.walk(nodo) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _mensajes_del_codigo():
    mensajes = []
    for ruta in sorted(RAIZ_BACKEND.rglob("*.py")):
        relativa = ruta.relative_to(RAIZ_BACKEND)
        if relativa.parts[0] == "tests" or "migrations" in relativa.parts:
            continue
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Call) and _nombre_llamado(nodo) in _CONSTRUCTORES_DE_ERROR:
                argumentos = nodo.args
                if _nombre_llamado(nodo) == "ErrorValidacion" and len(argumentos) == 2:
                    argumentos = argumentos[1:]  # el primero es el nombre del campo
                elif _nombre_llamado(nodo) == "respuesta_error":
                    argumentos = argumentos[1:]  # el primero es el código HTTP
                mensajes += [(str(relativa), t) for a in argumentos for t in _textos(a)]
            elif isinstance(nodo, ast.Assign) and any(
                isinstance(o, ast.Name) and o.id.lstrip("_").startswith("MENSAJE") for o in nodo.targets
            ):
                mensajes += [(str(relativa), t) for t in _textos(nodo.value)]
    return mensajes


def test_rnf15_ningun_mensaje_de_error_del_codigo_tiene_texto_de_programador():
    mensajes = _mensajes_del_codigo()

    # Resguardo: si el recorrido dejara de encontrar mensajes, la prueba no probaría nada.
    assert len(mensajes) >= 60
    encontrados = [(archivo, texto, t) for archivo, texto in mensajes for t in TEXTO_PROHIBIDO if t in texto]
    assert encontrados == []


# --- 2. Recorrido por la API del maestro ---


def _png(tamano):
    salida = io.BytesIO()
    Image.new("RGB", tamano, (40, 120, 200)).save(salida, format="PNG")
    return salida.getvalue()


def _jpeg():
    salida = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 120, 40)).save(salida, format="JPEG")
    return salida.getvalue()


def _archivo(contenido, nombre="foto.jpg"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(nombre, contenido, content_type="image/jpeg")


def _fecha(dias):
    return (hoy_negocio() + datetime.timedelta(days=dias)).isoformat()


def _documento(tipo=ANTECEDENTES, archivo=True, foto=None, **cambios):
    datos = {"tipo": tipo, "fecha_emision": _fecha(-30)}
    if archivo:
        datos["archivo"] = _archivo(_jpeg() if foto is None else foto)
    datos.update(cambios)
    return {clave: valor for clave, valor in datos.items() if valor is not None}


def _textos_json(valor):
    """Solo los valores de texto del JSON (las claves son nombres de campo)."""
    if isinstance(valor, dict):
        return [t for v in valor.values() for t in _textos_json(v)]
    if isinstance(valor, list):
        return [t for v in valor for t in _textos_json(v)]
    return [valor] if isinstance(valor, str) else []


def _con_estado(estado):
    Expediente.objects.update(estado=estado)


@pytest.fixture(autouse=True)
def directorio_documentos(settings, tmp_path):
    directorio = tmp_path / "documentos"
    directorio.mkdir(mode=0o700)
    settings.ALTIRO_DOCUMENTOS_DIR = directorio
    return directorio


@pytest.mark.django_db
def test_rnf15_rnf17_los_errores_que_ve_el_maestro_estan_en_su_lenguaje(client):
    respuestas = []

    def registrar(descripcion, respuesta):
        assert respuesta.status_code >= 400, descripcion
        respuestas.append((descripcion, respuesta))

    # Postulación sin sesión.
    for descripcion, datos in [
        ("postulación vacía", {}),
        ("RUT con formato inválido", datos_maestro(rut="abc")),
        ("RUT con dígito verificador incorrecto", datos_maestro(rut="11.111.111-2")),
        ("teléfono inválido", datos_maestro(telefono="123")),
        ("contraseña corta", datos_maestro(contrasena="corta")),
        ("contraseña común", datos_maestro(contrasena="password1234")),
        ("nombre vacío", datos_maestro(nombre="")),
        ("correo inválido", datos_maestro(correo="no-es-correo")),
        ("dato que el formulario no usa", {**datos_maestro(), "otro_dato": "x"}),
        ("dato que no corresponde", {**datos_maestro(), "comuna": "8101"}),
    ]:
        registrar(descripcion, post_json(client, URL_POSTULACIONES, datos))
    registrar(
        "cuerpo ilegible",
        client.post(URL_POSTULACIONES, data="{no es json", content_type="application/json"),
    )
    crear_maestro(rut=RUT_PROPIO)
    registrar("RUT ya postulado", post_json(client, URL_POSTULACIONES, datos_maestro(telefono=TEL_B)))

    # Inicio de sesión.
    registrar("RUT de ingreso inválido", iniciar_sesion(client, "11.111.111-2"))
    registrar("contraseña vacía", iniciar_sesion(client, RUT_PROPIO, contrasena=""))
    registrar("contraseña incorrecta", iniciar_sesion(client, RUT_PROPIO, contrasena="otra clave de prueba"))
    assert iniciar_sesion(client, RUT_PROPIO).status_code == 200

    # Con sesión: postular de nuevo, pedir trabajos sin correo, rutas que no le corresponden.
    registrar("ya postuló", post_json(client, URL_POSTULACIONES, {"rut": "22.222.222-2"}))
    registrar("pedir trabajos sin correo", post_json(client, URL_CLIENTES, {"comuna": "8101"}))
    registrar("ruta inexistente", client.get("/api/no-existe"))
    registrar("método no disponible", client.get(URL_OFICIOS))
    registrar("sección de curatoría", client.get("/api/curatoria/expedientes"))
    registrar("host no permitido", client.get("/api/health/", HTTP_HOST="evil.example"))

    # Oficios.
    registrar("sin oficios", post_json(client, URL_OFICIOS, {"oficios": []}))
    registrar("oficio inexistente", post_json(client, URL_OFICIOS, {"oficios": ["no_existe"]}))

    # Documentos.
    for descripcion, datos in [
        ("documento sin tipo", {"archivo": _archivo(_jpeg())}),
        ("documento sin foto", _documento(archivo=False)),
        ("cédula sin reverso", _documento(tipo=CEDULA)),
        ("fecha inválida", _documento(fecha_emision="31-02-2026")),
        ("sin fecha de emisión", _documento(fecha_emision=None)),
        ("emisión futura", _documento(fecha_emision=_fecha(3))),
        ("vencimiento anterior a la emisión", _documento(fecha_vencimiento=_fecha(-40))),
        ("documento vencido", _documento(fecha_vencimiento=_fecha(-1))),
        ("oficio en un documento que no lo usa", _documento(oficio="gas")),
        ("licencia sin oficio", _documento(tipo=LICENCIA_SEC)),
        ("licencia de oficio no regulado", _documento(tipo=LICENCIA_SEC, oficio="pintura")),
        ("licencia de oficio no declarado", _documento(tipo=LICENCIA_SEC, oficio="gas")),
        ("archivo que no es foto", _documento(foto=b"<html>no</html>")),
        ("foto vacía", _documento(foto=b"")),
        ("foto con demasiados pixeles", _documento(foto=_png((6000, 6000)))),
    ]:
        registrar(descripcion, client.post(URL_DOCUMENTOS, data=datos))

    # Estados en que ya no puede cambiar oficios ni enviar documentos.
    for estado in (EstadoExpediente.APROBADO, EstadoExpediente.SUSPENDIDO, EstadoExpediente.RECHAZADO):
        _con_estado(estado)
        registrar(f"oficios en {estado}", post_json(client, URL_OFICIOS, {"oficios": ["gas"]}))
    registrar("documento con postulación no aprobada", client.post(URL_DOCUMENTOS, data=_documento()))

    # Formulario vencido (CSRF).
    con_csrf = Client(enforce_csrf_checks=True)
    registrar("formulario vencido", post_json(con_csrf, URL_POSTULACIONES, datos_maestro()))

    encontrados = []
    mensajes = set()
    for descripcion, respuesta in respuestas:
        assert respuesta["Content-Type"].startswith("application/json"), descripcion
        for texto in _textos_json(respuesta.json()):
            mensajes.add(texto)
            encontrados += [(descripcion, texto, t) for t in PROHIBIDO_PARA_EL_MAESTRO if t in texto]
    assert encontrados == []
    # Resguardo: los casos provocan errores distintos, no siempre el mismo texto.
    assert len(mensajes) >= 30


# --- 3. Servicios del maestro (S3, incremento 2; RF-05, CA-12.1, CA-12.2; ADR-019) ---

URL_SERVICIOS = "/api/maestros/servicios"


def _servicio_del_catalogo(oficio, nombre, modalidades):
    servicio = Servicio.objects.create(oficio=Oficio.objects.get(codigo=oficio), nombre=nombre, orden=1)
    for modalidad in modalidades:
        ServicioModalidad.objects.create(servicio=servicio, modalidad=modalidad, precio_referencia=10000)
    return servicio


def _patch(client, url, datos):
    return client.patch(url, data=json.dumps(datos), content_type="application/json")


@pytest.mark.django_db
def test_rnf15_rnf17_servicios_del_maestro_en_su_lenguaje(client):
    """Errores, motivos de no visibilidad y pendientes que ve el maestro en sus servicios."""
    maestro = crear_maestro(rut=RUT_PROPIO)
    expedientes.declarar_oficios(Expediente.objects.get(perfil_maestro_id=maestro.pk), ["gas", "pintura"])
    gas = _servicio_del_catalogo("gas", "Instalación de cocina", ["por_trabajo"])
    pintura = _servicio_del_catalogo("pintura", "Pintura de muro", ["por_trabajo", "por_hora"])
    carpinteria = _servicio_del_catalogo("carpinteria", "Arreglo de puerta", ["por_trabajo"])
    assert iniciar_sesion(client, RUT_PROPIO).status_code == 200

    respuestas = []

    def registrar(descripcion, respuesta):
        assert respuesta.status_code >= 400, descripcion
        respuestas.append((descripcion, respuesta))

    for descripcion, datos in [
        ("servicio vacío", {}),
        ("sin modalidad", {"servicio": str(gas.ref), "monto": 1000}),
        ("sin monto", {"servicio": str(gas.ref), "modalidad": "por_trabajo"}),
        ("monto inválido", {"servicio": str(gas.ref), "modalidad": "por_trabajo", "monto": "mil"}),
        ("monto sobre el tope", {"servicio": str(gas.ref), "modalidad": "por_trabajo", "monto": 10_000_001}),
        ("modalidad no admitida", {"servicio": str(gas.ref), "modalidad": "por_hora", "monto": 1000}),
        ("servicio inexistente", {"servicio": "no-es", "modalidad": "por_trabajo", "monto": 1000}),
        ("oficio no declarado", {"servicio": str(carpinteria.ref), "modalidad": "por_trabajo", "monto": 1000}),
        ("dato que no corresponde", {"servicio": str(gas.ref), "modalidad": "por_trabajo", "monto": 1, "rut": "x"}),
    ]:
        registrar(descripcion, post_json(client, URL_SERVICIOS, datos))
    creado = post_json(client, URL_SERVICIOS, {"servicio": str(gas.ref), "modalidad": "por_trabajo", "monto": 1000})
    assert creado.status_code == 201
    url = f"{URL_SERVICIOS}/{creado.json()['servicio']['ref']}"
    repetido = {"servicio": str(gas.ref), "modalidad": "por_trabajo", "monto": 1}
    registrar("servicio repetido", post_json(client, URL_SERVICIOS, repetido))
    registrar("cambio sin datos", _patch(client, url, {}))
    registrar("cambio a modalidad no admitida", _patch(client, url, {"modalidad": "por_hora"}))
    registrar("servicio ajeno o inexistente", _patch(client, f"{URL_SERVICIOS}/{uuid.uuid4()}", {"monto": 1}))
    assert client.delete(url).status_code == 204
    registrar("servicio ya quitado", client.delete(url))
    _con_estado(EstadoExpediente.RECHAZADO)
    otro = {"servicio": str(pintura.ref), "modalidad": "por_hora", "monto": 1}
    registrar("postulación rechazada", post_json(client, URL_SERVICIOS, otro))

    # Motivos y pendientes que se muestran en la lista (no son errores, pero los lee el maestro).
    textos_lista = []
    for estado in (EstadoExpediente.EN_REVISION, EstadoExpediente.SUSPENDIDO, EstadoExpediente.RECHAZADO):
        _con_estado(estado)
        textos_lista += _textos_json(client.get(URL_SERVICIOS).json())
    textos_lista += [m.format(oficio="Gas") for m in MENSAJES_MOTIVO.values()]
    textos_lista += list(MENSAJES_PENDIENTE.values()) + list(MENSAJES_POSTULACION.values())
    assert set(MENSAJES_MOTIVO) == set(publicacion.MOTIVOS)

    encontrados = []
    mensajes = set()
    for descripcion, respuesta in respuestas:
        assert respuesta["Content-Type"].startswith("application/json"), descripcion
        for texto in _textos_json(respuesta.json()):
            mensajes.add(texto)
            encontrados += [(descripcion, texto, t) for t in PROHIBIDO_PARA_EL_MAESTRO if t in texto]
    for texto in textos_lista:
        encontrados += [("lista de servicios", texto, t) for t in PROHIBIDO_PARA_EL_MAESTRO if t in texto]
    assert encontrados == []
    assert len(mensajes) >= 10
    assert Servicio.objects.count() == 3 and ServicioModalidad.objects.count() == 4
