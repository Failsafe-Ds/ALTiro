"""Validaciones mínimas de texto en todos los campos que la persona escribe (CLAUDE.md §8-§9; ADR-013; RNF-15).

Auditoría del backend del 2026-10-11 (``docs/testing/auditoria-backend-ponytail.md``), hallazgos 1, 3, 4, 5, 7 y 8:

- el carácter nulo da 400 en el campo, nunca 500;
- solo espacios cuenta como vacío (400 «falta» si es obligatorio);
- los espacios del inicio y del final se recortan antes de medir el largo y de guardar;
- largo máximo + 1 da 400 en el campo, sin recorte silencioso;
- los campos de formato fijo (RUT, monto, fechas, horas, meses, comuna) se recortan antes de validar.

El motivo de curatoría ya se prueba igual en ``test_curatoria.py`` (vacío, solo espacios, largo y nulo).
Datos ficticios (``tests.tickets_ayudas``).
"""
import uuid

import pytest
import time_machine
from django.test import Client

from catalogo import servicios as catalogo_servicios
from catalogo.models import Oficio
from comun import texto
from evaluaciones.models import LARGO_COMENTARIO, LARGO_MOTIVO, Denuncia, Evaluacion, ParteEvaluacion
from expediente import servicios as expediente_servicios
from gestion import vistas as gestion_vistas
from identidad.autenticacion import interpretar_identificador
from identidad.models import Rol, Usuario
from identidad.validadores import NOMBRE_LARGO_MAXIMO
from mensajeria.models import LARGO_MAXIMO as LARGO_MENSAJE
from mensajeria.models import Mensaje
from perfil import agenda
from perfil.servicios import MENSAJE_MONTO_FALTA, validar_monto
from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from tests.ayudas import (
    URL_CLIENTES,
    URL_POSTULACIONES,
    datos_cliente,
    datos_maestro,
    iniciar_sesion,
    post_json,
)
from tickets.models import LARGO_DESCRIPCION, LARGO_DIRECCION, EstadoTicket, Ticket

pytestmark = pytest.mark.django_db

NOTAS = {"puntualidad": 5, "trabajo": 4, "cordialidad": 5}
CORREO_MOD = "moderacion@example.com"
CORREO_COMERCIAL = "comercial@example.com"


@pytest.fixture
def reloj():
    with time_machine.travel(tk.AHORA, tick=False):
        yield


@pytest.fixture
def catalogo(reloj):
    return ay.catalogo_basico()


@pytest.fixture
def maestro(catalogo):
    return tk.maestro_con_agenda(catalogo)


@pytest.fixture
def cliente(reloj):
    return tk.cliente()


def _ticket(cliente, maestro, estado):
    return tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=estado)


def _evaluacion(ticket, cliente, maestro):
    return Evaluacion.objects.create(ticket=ticket, parte=ParteEvaluacion.CLIENTE, autor_id=cliente.pk,
                                     evaluado_id=maestro.pk, puntualidad=1, trabajo=1, cordialidad=1)


# --- Preparación de cada endpoint: devuelve (cliente HTTP, URL, cuerpo sin el campo, lectura de lo guardado) ---


def _registro_cliente(request):
    request.getfixturevalue("reloj")
    return Client(), URL_CLIENTES, datos_cliente(nombre=None), lambda: Usuario.objects.get().nombre


def _postulacion(request):
    request.getfixturevalue("reloj")
    return Client(), URL_POSTULACIONES, datos_maestro(nombre=None), lambda: Usuario.objects.get().nombre


def _pedido(campo):
    def preparar(request):
        maestro, catalogo = request.getfixturevalue("maestro"), request.getfixturevalue("catalogo")
        request.getfixturevalue("cliente")
        cuerpo = tk.pedido(maestro, catalogo, **{campo: None})
        return tk.sesion(tk.CORREO_CLIENTE), tk.URL, cuerpo, lambda: getattr(Ticket.objects.get(), campo)
    return preparar


def _mensaje(request):
    cliente, maestro = request.getfixturevalue("cliente"), request.getfixturevalue("maestro")
    ticket = _ticket(cliente, maestro, EstadoTicket.ACEPTADO)
    cuerpo = {"clave_envio": str(uuid.uuid4())}
    return tk.sesion(tk.CORREO_CLIENTE), f"{tk.URL}/{ticket.ref}/mensajes", cuerpo, lambda: Mensaje.objects.get().texto


def _evaluar(request):
    cliente, maestro = request.getfixturevalue("cliente"), request.getfixturevalue("maestro")
    ticket = _ticket(cliente, maestro, EstadoTicket.FINALIZADO)
    url = f"{tk.URL}/{ticket.ref}/evaluacion"
    return tk.sesion(tk.CORREO_CLIENTE), url, dict(NOTAS), lambda: Evaluacion.objects.get().comentario


def _denunciar(request):
    cliente, maestro = request.getfixturevalue("cliente"), request.getfixturevalue("maestro")
    ticket = _ticket(cliente, maestro, EstadoTicket.FINALIZADO)
    _evaluacion(ticket, cliente, maestro)
    url = f"{tk.URL}/{ticket.ref}/evaluacion-recibida/denuncia"
    return tk.sesion(ay.rut(1)), url, {}, lambda: Denuncia.objects.get().motivo


def _resolver(request):
    cliente, maestro = request.getfixturevalue("cliente"), request.getfixturevalue("maestro")
    evaluacion = _evaluacion(_ticket(cliente, maestro, EstadoTicket.FINALIZADO), cliente, maestro)
    denuncia = Denuncia.objects.create(evaluacion=evaluacion, denunciante_id=maestro.pk, motivo="No es verdad")
    tk.administrativo(Rol.MODERACION, CORREO_MOD)
    url = f"/api/moderacion/denuncias/{denuncia.ref}/resolucion"
    return tk.sesion(CORREO_MOD), url, {"decision": "mantener"}, lambda: Denuncia.objects.get().motivo_resolucion


def _oficio(request):
    request.getfixturevalue("reloj")
    tk.administrativo(Rol.COMERCIAL, CORREO_COMERCIAL)
    cuerpo = {"regulado": False}
    return tk.sesion(CORREO_COMERCIAL), "/api/comercial/oficios", cuerpo, lambda: Oficio.objects.order_by("-pk").first().nombre


# (endpoint, campo, preparación, largo máximo, obligatorio)
CAMPOS = [
    ("registro de cliente", "nombre", _registro_cliente, NOMBRE_LARGO_MAXIMO, True),
    ("postulación de maestro", "nombre", _postulacion, NOMBRE_LARGO_MAXIMO, True),
    ("ticket", "direccion", _pedido("direccion"), LARGO_DIRECCION, True),
    ("ticket", "descripcion", _pedido("descripcion"), LARGO_DESCRIPCION, True),
    ("mensaje", "texto", _mensaje, LARGO_MENSAJE, True),
    ("evaluación", "comentario", _evaluar, LARGO_COMENTARIO, False),
    ("denuncia", "motivo", _denunciar, LARGO_MOTIVO, True),
    ("resolución de moderación", "motivo", _resolver, LARGO_MOTIVO, True),
    ("oficio del catálogo", "nombre", _oficio, catalogo_servicios.NOMBRE_LARGO_MAXIMO, True),
]
CASOS = ("nulo", "solo espacios", "espacios en los bordes", "largo + 1")


@pytest.mark.parametrize("caso", CASOS)
@pytest.mark.parametrize(
    "endpoint,campo,preparar,largo,obligatorio", CAMPOS, ids=[f"{e}-{c}" for e, c, *_ in CAMPOS]
)
def test_cada_campo_de_texto_recorta_y_rechaza_en_el_campo(request, caso, endpoint, campo, preparar, largo,
                                                           obligatorio):
    client, url, cuerpo, guardado = preparar(request)
    valor = {
        "nulo": "Texto\u0000con nulo",
        "solo espacios": "   ",
        "espacios en los bordes": "  " + "a" * largo + " \n",
        "largo + 1": "a" * (largo + 1),
    }[caso]

    respuesta = post_json(client, url, {**cuerpo, campo: valor})

    assert respuesta.status_code != 500
    if caso == "espacios en los bordes" or (caso == "solo espacios" and not obligatorio):
        assert respuesta.status_code in (200, 201), respuesta.content
        assert guardado() == valor.strip()
    else:
        assert respuesta.status_code == 400, respuesta.content
        assert campo in respuesta.json()["errores"]
        assert respuesta.json()["errores"][campo]


# --- Campos de formato fijo: se recortan antes de validar (hallazgos 3, 5 y 8) ---


def test_el_rut_con_espacios_en_los_bordes_se_acepta_al_postular_e_ingresar(reloj):
    rut = " 11.111.111-1 "
    assert post_json(Client(), URL_POSTULACIONES, datos_maestro(rut=rut)).status_code == 201
    assert iniciar_sesion(Client(), rut).status_code == 200
    assert interpretar_identificador(rut) == interpretar_identificador(rut.strip())  # también en la recuperación


def test_el_monto_se_recorta_y_solo_espacios_cuenta_como_que_falta():
    errores = {}
    assert validar_monto({"monto": " 25000 "}, errores) == 25000 and not errores
    validar_monto({"monto": "   "}, errores)
    assert errores == {"monto": MENSAJE_MONTO_FALTA}


def test_el_precio_final_con_solo_espacios_dice_que_falta(cliente, maestro):
    ticket = _ticket(cliente, maestro, EstadoTicket.ACEPTADO)

    respuesta = post_json(tk.sesion(ay.rut(1)), f"{tk.URL}/{ticket.ref}/precio-final", {"monto": "   "})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"monto": MENSAJE_MONTO_FALTA}


def test_fechas_horas_meses_y_comuna_con_espacios_se_aceptan(cliente, maestro, catalogo):
    errores = {}
    assert expediente_servicios._fecha(" 2026-01-05 ", errores, "fecha_emision") is not None and not errores
    assert agenda.minutos_de_hora(" 08:00 ") == 480
    assert gestion_vistas._mes(" 2026-01 ") is not None
    cuerpo = tk.pedido(maestro, catalogo, comuna=f" {ay.CONCEPCION} ", fecha=f" {tk.JUEVES.isoformat()} ",
                       inicio=" 08:00 ", fin=" 12:00 ")

    respuesta = tk.enviar(tk.sesion(tk.CORREO_CLIENTE), cuerpo)

    assert respuesta.status_code == 201, respuesta.content


def test_contrato_de_limpiar_texto():
    """Recorta, rechaza control y nulo; un opcional vacío vuelve como texto vacío.

    La contraseña nunca pasa por aquí: no se recorta (ADR-013).
    """
    assert texto.limpiar_texto("  clave  ", 10) == ("clave", None)
    assert texto.limpiar_texto("a\x00b", 10) == (None, texto.INVALIDO)
    assert texto.limpiar_texto("a\nb", 10, una_linea=True) == (None, texto.INVALIDO)
    assert texto.limpiar_texto("   ", 10, obligatorio=False) == ("", None)
