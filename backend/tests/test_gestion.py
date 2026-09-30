"""Indicadores base y exportación agregada (S5, incremento 7).

HU-22; RF-38; CA-22.1, CA-22.2; R-08; ADR-026, E-6; propuesta del S5, §3.5.
Datos ficticios (``tests.busqueda_ayudas`` y ``tests.tickets_ayudas``).
"""
import csv
import datetime
import io
import re
import uuid

import pytest
import time_machine
from django.test import Client

from autorizacion.models import RegistroAccesoDenegado
from bitacora.models import Bitacora
from catalogo.models import Oficio
from expediente.models import Documento, EstadoDocumento, EstadoExpediente, Expediente, TipoDocumento
from gestion import exportacion
from identidad.models import PerfilMaestro, Rol, Usuario
from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from territorio.models import Comuna
from tests.ayudas import sin_texto_prohibido
from tickets.models import AutorTipo, EstadoTicket, MotivoCierre, Ticket, TicketEvento

pytestmark = pytest.mark.django_db

AHORA = tk.AHORA  # 2026-10-07 08:00, Santiago
ZONA = AHORA.tzinfo
URL_IND = "/api/gestion/indicadores"
URL_EXP = "/api/gestion/exportacion"
CORREO_GESTION = "gestion@example.com"
PERIODO = {"desde": "2026-09-01", "hasta": "2026-10-06"}
BASE = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=ZONA)


@pytest.fixture
def reloj():
    with time_machine.travel(AHORA, tick=False):
        yield


@pytest.fixture
def catalogo(reloj):
    return ay.catalogo_basico()


@pytest.fixture
def sesion_gestion(reloj):
    tk.administrativo(Rol.CONTROL_GESTION, CORREO_GESTION)
    return tk.sesion(CORREO_GESTION)


def _maestros(catalogo, cantidad, desde=1, **cambios):
    return [ay.maestro(n, catalogo, **cambios) for n in range(desde, desde + cantidad)]


def _clientes(cantidad, desde=1):
    return [
        tk.cliente(correo=f"cliente{n:02d}.prueba@example.com", telefono=f"+56 9 2000 {n:04d}")
        for n in range(desde, desde + cantidad)
    ]


_contador = iter(range(10_000))


def _ticket(cliente, maestro, estado=EstadoTicket.PENDIENTE, enviado_en=None, motivo=None, monto_final=None,
            comuna=None):
    """Ticket en el período; cada uno en un día distinto para no chocar con las restricciones del bloque."""
    i = next(_contador)
    enviado_en = enviado_en or BASE + datetime.timedelta(minutes=i)
    fecha = enviado_en.date() + datetime.timedelta(days=3 + i % 40)
    ticket = tk.ticket_directo(cliente, maestro, fecha, "08:00", "12:00", estado=estado, enviado_en=enviado_en,
                               motivo=motivo)
    cambios = {}
    if monto_final is not None:
        cambios.update(monto_final=monto_final, precio_aceptado_en=enviado_en)
    if comuna is not None:
        cambios["comuna_id"] = comuna
    if cambios:
        Ticket.objects.filter(pk=ticket.pk).update(**cambios)
    return ticket


def _evento(ticket, minutos, estado_nuevo, motivo=None, autor_id=None, sistema=False):
    TicketEvento.objects.create(
        ticket_id=ticket.pk,
        fecha=ticket.enviado_en + datetime.timedelta(minutes=minutos),
        estado_anterior=EstadoTicket.PENDIENTE,
        estado_nuevo=estado_nuevo,
        motivo=motivo,
        autor_tipo=AutorTipo.SISTEMA if sistema else AutorTipo.USUARIO,
        autor_id=None if sistema else (autor_id or ticket.perfil_maestro_id),
    )


def _documento(maestro, tipo, vencimiento=None, estado=EstadoDocumento.VALIDADO):
    return Documento.objects.create(
        expediente=Expediente.objects.get(perfil_maestro_id=maestro.pk),
        tipo=tipo,
        fecha_emision=datetime.date(2020, 1, 10),
        fecha_vencimiento=vencimiento,
        estado=estado,
        archivo=uuid.uuid4(),
        archivo_reverso=uuid.uuid4() if tipo == TipoDocumento.CEDULA_IDENTIDAD else None,
    )


def _al_dia(maestro, cedula_vence=datetime.date(2030, 1, 1)):
    _documento(maestro, TipoDocumento.CEDULA_IDENTIDAD, cedula_vence)
    _documento(maestro, TipoDocumento.CERTIFICADO_ANTECEDENTES)  # sin vencimiento: siempre vigente


def _csv(respuesta):
    return list(csv.reader(io.StringIO(respuesta.content.decode("utf-8-sig"))))


# --- Acceso (HU-22; E-6.3) ---


@pytest.mark.regla("A-25")
@pytest.mark.parametrize("url", [URL_IND, URL_EXP])
@pytest.mark.parametrize("rol", [Rol.CURATORIA, Rol.MODERACION, Rol.COMERCIAL])
def test_otro_rol_recibe_403_registrado(reloj, url, rol):
    usuario = tk.administrativo(rol, "otro.rol@example.com")
    respuesta = tk.sesion("otro.rol@example.com").get(url, PERIODO)

    assert respuesta.status_code == 403 and sin_texto_prohibido(respuesta)
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad) == (usuario.pk, "ruta")
    assert not Bitacora.objects.filter(accion="exportacion_agregada").exists()


@pytest.mark.regla("A-25")
@pytest.mark.parametrize("url", [URL_IND, URL_EXP])
def test_cliente_y_maestro_reciben_403_y_sin_sesion_401(catalogo, url):
    ay.maestro(1, catalogo)
    tk.cliente()
    assert tk.sesion(tk.CORREO_CLIENTE).get(url, PERIODO).status_code == 403
    assert tk.sesion(ay.rut(1)).get(url, PERIODO).status_code == 403
    assert Client().get(url, PERIODO).status_code == 401


@pytest.mark.regla("A-25")
def test_control_de_gestion_consulta_los_tres_indicadores(sesion_gestion):
    respuesta = sesion_gestion.get(URL_IND, PERIODO)

    assert respuesta.status_code == 200 and respuesta["Cache-Control"] == "no-store"
    datos = respuesta.json()
    assert set(datos) == {"periodo", "concrecion", "primera_respuesta", "vigencia_documental"}
    for clave in ("concrecion", "primera_respuesta", "vigencia_documental"):
        assert datos[clave]["definicion"]
    assert datos["concrecion"]["porcentaje"] is None  # sin pedidos no hay división


# --- Período (E-6.3; ADR-013) ---


@pytest.mark.regla("I-04")
@pytest.mark.parametrize("url", [URL_IND, URL_EXP])
@pytest.mark.parametrize(
    "periodo, campos",
    [
        ({"desde": "2026-09-01", "hasta": "2026-09-30"}, {"hasta"}),  # 30 días
        ({"desde": "2025-09-01", "hasta": "2026-09-02"}, {"hasta"}),  # 367 días
        ({"desde": "2026-10-01", "hasta": "2026-09-01"}, {"hasta"}),  # al revés
        ({"desde": "2026-02-30", "hasta": "2026-06-01"}, {"desde"}),  # no existe
        ({"desde": "01-09-2026", "hasta": "2026-12-01"}, {"desde"}),
        ({"desde": "2026-09-01"}, {"hasta"}),
        ({}, {"desde", "hasta"}),
    ],
)
def test_periodo_fuera_de_rango_o_invalido_da_400_en_el_campo(sesion_gestion, url, periodo, campos):
    respuesta = sesion_gestion.get(url, periodo)

    assert respuesta.status_code == 400 and sin_texto_prohibido(respuesta)
    assert set(respuesta.json()["errores"]) == campos
    assert not Bitacora.objects.filter(accion="exportacion_agregada").exists()


@pytest.mark.regla("I-04")
@pytest.mark.parametrize("url", [URL_IND, URL_EXP])
def test_limites_del_periodo_y_claves_desconocidas(sesion_gestion, url):
    assert sesion_gestion.get(url, {"desde": "2026-09-01", "hasta": "2026-10-01"}).status_code == 200  # 31
    assert sesion_gestion.get(url, {"desde": "2025-10-01", "hasta": "2026-10-01"}).status_code == 200  # 366
    otra = sesion_gestion.get(url, {**PERIODO, "comuna": "8101"})
    assert otra.status_code == 400 and otra.json()["errores"] == {}
    repetida = sesion_gestion.get(f"{url}?desde=2026-09-01&desde=2026-09-02&hasta=2026-10-06")
    assert repetida.status_code == 400 and repetida.json()["errores"] == {}


# --- Fórmulas (§2.9.2; E-6.1) ---


@pytest.mark.regla("I-01")
def test_tasa_de_concrecion(sesion_gestion, catalogo):
    maestro = ay.maestro(1, catalogo)
    cliente = tk.cliente()
    _ticket(cliente, maestro, EstadoTicket.FINALIZADO)
    _ticket(cliente, maestro, EstadoTicket.ACEPTADO)
    _ticket(cliente, maestro, EstadoTicket.CERRADO)
    _ticket(cliente, maestro)
    # Fuera del período (por enviado_en): no cuenta.
    _ticket(cliente, maestro, EstadoTicket.FINALIZADO, enviado_en=datetime.datetime(2026, 8, 31, 23, 0, tzinfo=ZONA))

    datos = sesion_gestion.get(URL_IND, PERIODO).json()["concrecion"]

    assert (datos["porcentaje"], datos["concretados"], datos["enviados"]) == (25.0, 1, 4)


@pytest.mark.regla("I-02")
def test_primera_respuesta_mediana_y_cantidad(sesion_gestion, catalogo):
    maestro = ay.maestro(1, catalogo)
    cliente = tk.cliente()
    aceptado = _ticket(cliente, maestro, EstadoTicket.ACEPTADO)
    _evento(aceptado, 30, EstadoTicket.ACEPTADO)
    rechazado = _ticket(cliente, maestro, EstadoTicket.CERRADO, motivo=MotivoCierre.RECHAZADO_MAESTRO)
    _evento(rechazado, 90, EstadoTicket.CERRADO, MotivoCierre.RECHAZADO_MAESTRO)
    otro = _ticket(cliente, maestro, EstadoTicket.FINALIZADO)
    _evento(otro, 60, EstadoTicket.ACEPTADO)
    # Excluidos: bloque tomado (aunque su autor sea el maestro), cierre del Sistema y cancelación del cliente.
    tomado = _ticket(cliente, maestro, EstadoTicket.CERRADO, motivo=MotivoCierre.BLOQUE_TOMADO)
    _evento(tomado, 5, EstadoTicket.CERRADO, MotivoCierre.BLOQUE_TOMADO)
    vencido = _ticket(cliente, maestro, EstadoTicket.CERRADO, motivo=MotivoCierre.VENCIDO_PLAZO)
    _evento(vencido, 1, EstadoTicket.CERRADO, MotivoCierre.VENCIDO_PLAZO, sistema=True)
    cancelado = _ticket(cliente, maestro, EstadoTicket.CERRADO, motivo=MotivoCierre.CANCELADO_CLIENTE)
    _evento(cancelado, 2, EstadoTicket.CERRADO, MotivoCierre.CANCELADO_CLIENTE, autor_id=cliente.pk)

    datos = sesion_gestion.get(URL_IND, PERIODO).json()["primera_respuesta"]

    assert (datos["mediana_minutos"], datos["cantidad"]) == (60, 3)


@pytest.mark.regla("I-02")
def test_primera_respuesta_mediana_par(sesion_gestion, catalogo):
    maestro = ay.maestro(1, catalogo)
    cliente = tk.cliente()
    for minutos in (10, 50):
        ticket = _ticket(cliente, maestro, EstadoTicket.ACEPTADO)
        _evento(ticket, minutos, EstadoTicket.ACEPTADO)

    datos = sesion_gestion.get(URL_IND, PERIODO).json()["primera_respuesta"]

    assert (datos["mediana_minutos"], datos["cantidad"]) == (30, 2)


@pytest.mark.regla("I-03")
def test_vigencia_documental(sesion_gestion, catalogo):
    al_dia = ay.maestro(1, catalogo)
    _al_dia(al_dia)
    cedula_vencida = ay.maestro(2, catalogo)
    _al_dia(cedula_vencida, cedula_vence=ay.HOY)  # vence hoy: ya no está vigente
    regulado = ay.maestro(3, catalogo, servicios=("gas",))  # licencia vigente (HOY + 300)
    _al_dia(regulado)
    licencia_vencida = ay.maestro(4, catalogo, servicios=("electricidad",))
    _al_dia(licencia_vencida)
    Documento.objects.filter(expediente__perfil_maestro_id=licencia_vencida.pk, tipo=TipoDocumento.LICENCIA_SEC)\
        .update(fecha_vencimiento=ay.HOY - datetime.timedelta(days=1))
    ay.maestro(5, catalogo)  # aprobado sin documentos
    # No aprobado: no entra en el denominador.
    _al_dia(ay.maestro(6, catalogo, estado=EstadoExpediente.EN_REVISION))

    datos = sesion_gestion.get(URL_IND, PERIODO).json()["vigencia_documental"]

    assert (datos["porcentaje"], datos["vigentes"], datos["aprobados"]) == (40.0, 2, 5)


# --- Exportación (CA-22.2; E-6.2; R-08) ---


_personas = iter(range(100, 10_000, 10))


def _escenario_exportable(catalogo, cantidad=5, clientes=5, comuna=None, mes=BASE):
    """``cantidad`` maestros y ``clientes`` clientes nuevos, con pedidos finalizados en un mismo grupo."""
    maestros = _maestros(catalogo, cantidad, desde=next(_personas))
    lista_clientes = _clientes(clientes, desde=next(_personas))
    for i in range(max(cantidad, clientes)):
        _ticket(lista_clientes[i % clientes], maestros[i % cantidad], EstadoTicket.FINALIZADO,
                enviado_en=mes + datetime.timedelta(hours=i), monto_final=30000 + 1000 * i, comuna=comuna)
    return maestros, lista_clientes


@pytest.mark.regla("N-01")
def test_csv_solo_columnas_de_la_lista_y_sin_datos_personales(sesion_gestion, catalogo):
    maestros, clientes = _escenario_exportable(catalogo)

    respuesta = sesion_gestion.get(URL_EXP, PERIODO)

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"].startswith("text/csv")
    assert respuesta["Content-Disposition"].startswith("attachment;")
    filas = _csv(respuesta)
    assert tuple(filas[0]) == exportacion.COLUMNAS
    comuna = Comuna.objects.select_related("provincia__region").get(pk=ay.CONCEPCION)
    oficio = Oficio.objects.get(codigo="pintura").nombre
    assert filas[1:] == [["2026-09", comuna.provincia.region.nombre, comuna.nombre, oficio, "5", "5", "32000"]]
    texto = respuesta.content.decode("utf-8-sig")
    prohibidos = [tk.DIRECCION, "Trabajo de prueba", "Maestro Prueba", "Ana Prueba", "@example.com"]
    for usuario in maestros:
        prohibidos += [PerfilMaestro.objects.get(pk=usuario.pk).rut, usuario.nombre, usuario.telefono]
    for usuario in clientes:
        prohibidos += [usuario.correo, usuario.nombre, usuario.telefono, usuario.telefono.replace("+", "")]
    assert not [p for p in prohibidos if p and p in texto]
    assert not re.search(r"\d{7,8}-?[\dkK]", texto)  # forma de RUT
    assert not re.search(r"\+?56\s?9", texto)  # forma de teléfono
    assert not re.search(r"[\w.]+@[\w.]+", texto)  # forma de correo
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", texto)  # ref UUID


@pytest.mark.regla("N-02")
def test_supresion_con_menos_de_5_maestros_o_clientes(sesion_gestion, catalogo):
    _escenario_exportable(catalogo, cantidad=4, clientes=6)  # 4 maestros distintos
    _escenario_exportable(catalogo, cantidad=6, clientes=4, comuna=ay.CORONEL)  # 4 clientes distintos
    _escenario_exportable(catalogo, cantidad=5, clientes=5, comuna=ay.HUALPEN)  # se publica

    respuesta = sesion_gestion.get(URL_EXP, PERIODO)

    filas = _csv(respuesta)
    assert len(filas) == 2 and filas[1][2] == "Hualpén"


@pytest.mark.regla("N-03")
def test_sin_totales_minimos_ni_maximos(sesion_gestion, catalogo):
    _escenario_exportable(catalogo)
    _escenario_exportable(catalogo, mes=datetime.datetime(2026, 10, 2, 10, 0, tzinfo=ZONA))

    filas = _csv(sesion_gestion.get(URL_EXP, PERIODO))

    assert [f[0] for f in filas[1:]] == ["2026-09", "2026-10"]  # una fila por grupo, ninguna de totales
    assert not [c for f in filas for c in f if re.search(r"total|m[ií]nim|m[aá]xim", c, re.I)]
    assert all(len(f) == len(exportacion.COLUMNAS) for f in filas)


@pytest.mark.regla("N-04")
def test_neutralizacion_de_celdas(sesion_gestion, catalogo):
    for inicio in ("=", "+", "-", "@", "\t", "\r"):
        assert exportacion.neutralizar(f"{inicio}HYPERLINK(1)") == f"'{inicio}HYPERLINK(1)"
    assert exportacion.neutralizar("Pintura") == "Pintura" and exportacion.neutralizar(32000) == "32000"
    _escenario_exportable(catalogo)
    Oficio.objects.filter(codigo="pintura").update(nombre="=HYPERLINK(\"x\")")

    filas = _csv(sesion_gestion.get(URL_EXP, PERIODO))

    assert filas[1][3] == "'=HYPERLINK(\"x\")"


@pytest.mark.regla("N-05")
def test_cada_exportacion_escribe_la_bitacora_sin_datos_personales(sesion_gestion, catalogo):
    _escenario_exportable(catalogo)
    _escenario_exportable(catalogo, cantidad=1, clientes=1, comuna=ay.CORONEL)  # suprimida

    assert sesion_gestion.get(URL_EXP, PERIODO).status_code == 200
    sesion_gestion.get(URL_EXP, PERIODO)

    entradas = Bitacora.objects.filter(accion="exportacion_agregada")
    assert entradas.count() == 2
    entrada = entradas.first()
    autor = Usuario.objects.get(correo=CORREO_GESTION)
    assert (entrada.autor_tipo, entrada.autor_id, entrada.entidad) == ("usuario", autor.pk, "exportacion")
    assert entrada.valor_nuevo == {"desde": "2026-09-01", "hasta": "2026-10-06", "filas": 1, "filas_suprimidas": 1}
    assert "@" not in str(entrada.valor_nuevo) + entrada.motivo + entrada.entidad_ref
