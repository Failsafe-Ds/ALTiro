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
from gestion import exportacion, indicadores
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
PERIODO = {"desde": "2026-09", "hasta": "2026-09"}  # último mes cerrado (E-6.6)
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


def _crudo(funcion):
    """Fórmula sin la protección de celdas pequeñas (E-6.6), sobre septiembre de 2026."""
    return funcion(*indicadores.periodo(datetime.date(2026, 9, 1), datetime.date(2026, 9, 30)))


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
    assert set(datos) == {"periodo", "umbral", "concrecion", "primera_respuesta", "vigencia_documental"}
    assert datos["periodo"] == {"desde": "2026-09", "hasta": "2026-09"} and datos["umbral"] == 5
    for clave in ("concrecion", "primera_respuesta", "vigencia_documental"):
        assert datos[clave]["definicion"]
    assert datos["concrecion"]["porcentaje"] is None  # sin pedidos no hay división


# --- Período (E-6.3; ADR-013) ---


@pytest.mark.regla("I-04")
@pytest.mark.parametrize("url", [URL_IND, URL_EXP])
@pytest.mark.parametrize(
    "periodo, campos",
    [
        ({"desde": "2026-09", "hasta": "2026-10"}, {"hasta"}),  # mes en curso: todavía abierto
        ({"desde": "2026-10", "hasta": "2026-10"}, {"hasta"}),
        ({"desde": "2025-09", "hasta": "2026-09"}, {"hasta"}),  # 13 meses
        ({"desde": "2026-09", "hasta": "2026-08"}, {"hasta"}),  # al revés
        ({"desde": "2026-13", "hasta": "2026-09"}, {"desde"}),  # no existe
        ({"desde": "2026-08-15", "hasta": "2026-09"}, {"desde"}),  # día suelto: solo meses completos
        ({"desde": "09-2026", "hasta": "2026-09"}, {"desde"}),
        ({"desde": "2026-09"}, {"hasta"}),
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
    assert sesion_gestion.get(url, {"desde": "2026-09", "hasta": "2026-09"}).status_code == 200  # 1 mes
    assert sesion_gestion.get(url, {"desde": "2025-10", "hasta": "2026-09"}).status_code == 200  # 12 meses
    otra = sesion_gestion.get(url, {**PERIODO, "comuna": "8101"})
    assert otra.status_code == 400 and otra.json()["errores"] == {}
    repetida = sesion_gestion.get(f"{url}?desde=2026-08&desde=2026-09&hasta=2026-09")
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

    datos = _crudo(indicadores.concrecion)

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

    datos = _crudo(indicadores.primera_respuesta)

    assert (datos["mediana_minutos"], datos["cantidad"]) == (60, 3)


@pytest.mark.regla("I-02")
def test_primera_respuesta_mediana_par(sesion_gestion, catalogo):
    maestro = ay.maestro(1, catalogo)
    cliente = tk.cliente()
    for minutos in (10, 50):
        ticket = _ticket(cliente, maestro, EstadoTicket.ACEPTADO)
        _evento(ticket, minutos, EstadoTicket.ACEPTADO)

    datos = _crudo(indicadores.primera_respuesta)

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

    datos = indicadores.vigencia_documental()

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


def _escenario_mediana(catalogo, finalizadas, maestros_fin=5, clientes_fin=5, comuna=None, mes=BASE):
    """Grupo que supera la supresión de fila (5 maestros y 5 clientes con pedidos pendientes) y
    ``finalizadas`` órdenes con monto repartidas entre ``maestros_fin`` maestros y ``clientes_fin`` clientes."""
    maestros = _maestros(catalogo, 5, desde=next(_personas))
    clientes = _clientes(5, desde=next(_personas))
    for i in range(5):
        _ticket(clientes[i], maestros[i], enviado_en=mes + datetime.timedelta(hours=i), comuna=comuna)
    for i in range(finalizadas):
        _ticket(clientes[i % clientes_fin], maestros[i % maestros_fin], EstadoTicket.FINALIZADO,
                enviado_en=mes + datetime.timedelta(hours=10 + i), monto_final=12000 + 1000 * i, comuna=comuna)


@pytest.mark.regla("N-06")
@pytest.mark.parametrize("finalizadas, maestros_fin, clientes_fin, mediana", [
    (1, 1, 1, ""),  # una sola orden: la mediana sería su precio exacto (y el conteo se vacía, E-6.6)
    (5, 4, 5, ""),  # 5 órdenes, pero de 4 maestros distintos
    (5, 5, 4, ""),  # 5 órdenes, pero de 4 clientes distintos
    (5, 5, 5, "14000"),
])
def test_mediana_solo_con_5_finalizadas_de_5_maestros_y_5_clientes(sesion_gestion, catalogo, finalizadas,
                                                                     maestros_fin, clientes_fin, mediana):
    _escenario_mediana(catalogo, finalizadas, maestros_fin, clientes_fin)

    filas = _csv(sesion_gestion.get(URL_EXP, PERIODO))

    assert len(filas) == 2  # la fila se publica: 5 maestros y 5 clientes entre los enviados
    assert filas[1][4:] == [str(5 + finalizadas), str(finalizadas) if finalizadas >= 5 else "", mediana]


@pytest.mark.regla("N-03")
def test_sin_totales_minimos_ni_maximos(sesion_gestion, catalogo):
    _escenario_exportable(catalogo)
    _escenario_exportable(catalogo, mes=datetime.datetime(2026, 8, 2, 10, 0, tzinfo=ZONA))

    filas = _csv(sesion_gestion.get(URL_EXP, {"desde": "2026-08", "hasta": "2026-09"}))

    assert [f[0] for f in filas[1:]] == ["2026-08", "2026-09"]  # una fila por grupo, ninguna de totales
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
    assert entrada.valor_nuevo == {
        "desde": "2026-09", "hasta": "2026-09", "filas": 1, "filas_suprimidas": 1, "celdas_suprimidas": 0,
    }
    assert "@" not in str(entrada.valor_nuevo) + entrada.motivo + entrada.entidad_ref


# --- Celdas pequeñas y diferenciación (R-08; ADR-026, E-6.6) ---


@pytest.mark.regla("N-07")
def test_finalizadas_bajo_5_se_vacia_con_supresion_complementaria(sesion_gestion, catalogo):
    _escenario_mediana(catalogo, 2, comuna=ay.CONCEPCION)  # 2 finalizadas: celda vacía
    _escenario_mediana(catalogo, 7, comuna=ay.CORONEL)  # la menor de las demás: complementaria
    _escenario_mediana(catalogo, 9, comuna=ay.HUALPEN)  # se publica
    # Agosto: una sola celda pequeña y ninguna otra fila (no hay complementaria posible).
    _escenario_mediana(catalogo, 3, mes=datetime.datetime(2026, 8, 3, 10, 0, tzinfo=ZONA))

    filas = _csv(sesion_gestion.get(URL_EXP, {"desde": "2026-08", "hasta": "2026-09"}))

    por_comuna = {(f[0], f[2]): f[4:] for f in filas[1:]}
    assert por_comuna == {
        ("2026-08", "Concepción"): ["8", "", ""],
        ("2026-09", "Concepción"): ["7", "", ""],
        ("2026-09", "Coronel"): ["12", "", ""],  # complementaria: también sin mediana
        ("2026-09", "Hualpén"): ["14", "9", "16000"],
    }
    entrada = Bitacora.objects.get(accion="exportacion_agregada")
    assert entrada.valor_nuevo["celdas_suprimidas"] == 3
    # El total del mes (concreción) menos lo publicado ya no despeja la celda de 2.
    concretados = sesion_gestion.get(URL_IND, PERIODO).json()["concrecion"]["concretados"]
    publicadas = sum(int(f[5]) for f in filas[1:] if f[0] == "2026-09" and f[5])
    assert concretados - publicadas == 2 + 7


@pytest.mark.regla("N-08")
def test_ventanas_solapadas_no_aislan_dias(sesion_gestion, catalogo):
    """Los períodos son meses cerrados: dos exportaciones solapadas traen las mismas filas del mes común."""
    _escenario_exportable(catalogo)
    _escenario_exportable(catalogo, mes=datetime.datetime(2026, 8, 20, 10, 0, tzinfo=ZONA))
    _escenario_exportable(catalogo, mes=datetime.datetime(2026, 9, 15, 10, 0, tzinfo=ZONA))  # un solo día

    dos_meses = _csv(sesion_gestion.get(URL_EXP, {"desde": "2026-08", "hasta": "2026-09"}))
    un_mes = _csv(sesion_gestion.get(URL_EXP, PERIODO))

    assert [f for f in dos_meses[1:] if f[0] == "2026-09"] == un_mes[1:]
    for desde, hasta in (("2026-08-15", "2026-09-15"), ("2026-08-16", "2026-09-16"), ("2026-09", "2026-10")):
        assert sesion_gestion.get(URL_EXP, {"desde": desde, "hasta": hasta}).status_code == 400
    # El 30 de septiembre a las 23:30 en Santiago, septiembre todavía está abierto.
    with time_machine.travel(datetime.datetime(2026, 9, 30, 23, 30, tzinfo=ZONA), tick=False):
        assert set(sesion_gestion.get(URL_EXP, PERIODO).json()["errores"]) == {"hasta"}


@pytest.mark.regla("I-05")
def test_indicadores_con_menos_de_5_se_suprimen(sesion_gestion, catalogo):
    maestro = ay.maestro(1, catalogo)
    cliente = tk.cliente()
    for minutos in (10, 20, 30, 40, 50):  # 5 respuestas, pero de un solo maestro
        _evento(_ticket(cliente, maestro, EstadoTicket.FINALIZADO), minutos, EstadoTicket.ACEPTADO)
    _al_dia(maestro)  # 1 maestro aprobado y vigente

    datos = sesion_gestion.get(URL_IND, PERIODO).json()

    assert datos["concrecion"]["suprimido"] is False and datos["concrecion"]["enviados"] == 5
    respuesta = datos["primera_respuesta"]
    assert respuesta == {**respuesta, "suprimido": True, "mediana_minutos": None, "cantidad": None}
    vigencia = datos["vigencia_documental"]
    assert vigencia == {**vigencia, "suprimido": True, "porcentaje": None, "vigentes": None, "aprobados": None}
    assert _crudo(indicadores.primera_respuesta)["cantidad"] == 5  # la fórmula no cambia


@pytest.mark.regla("I-05")
def test_primera_respuesta_con_5_maestros_se_publica(sesion_gestion, catalogo):
    cliente = tk.cliente()
    for n, minutos in enumerate((10, 20, 30, 40, 50), start=1):
        _evento(_ticket(cliente, ay.maestro(n, catalogo), EstadoTicket.ACEPTADO), minutos, EstadoTicket.ACEPTADO)

    datos = sesion_gestion.get(URL_IND, PERIODO).json()["primera_respuesta"]

    assert (datos["suprimido"], datos["mediana_minutos"], datos["cantidad"]) == (False, 30, 5)


@pytest.mark.regla("I-05")
def test_un_mes_pequeno_suprime_todo_el_periodo(sesion_gestion, catalogo):
    """Restar [ago..sep] menos [ago..ago] no despeja septiembre si septiembre tiene de 1 a 4 pedidos."""
    maestro = ay.maestro(1, catalogo)
    cliente = tk.cliente()
    agosto = datetime.datetime(2026, 8, 5, 10, 0, tzinfo=ZONA)
    for horas in range(10):
        _ticket(cliente, maestro, enviado_en=agosto + datetime.timedelta(hours=horas))
    for _ in range(2):
        _ticket(cliente, maestro, EstadoTicket.FINALIZADO)  # septiembre: 2 pedidos

    def concrecion(desde, hasta):
        return sesion_gestion.get(URL_IND, {"desde": desde, "hasta": hasta}).json()["concrecion"]

    solo_agosto = concrecion("2026-08", "2026-08")
    ambos = concrecion("2026-08", "2026-09")
    septiembre = concrecion("2026-09", "2026-09")
    julio = concrecion("2026-07", "2026-07")

    assert (solo_agosto["suprimido"], solo_agosto["enviados"], solo_agosto["porcentaje"]) == (False, 10, 0.0)
    assert ambos["suprimido"] is True and ambos["enviados"] is None and ambos["concretados"] is None
    assert septiembre["suprimido"] is True and septiembre["porcentaje"] is None
    assert (julio["suprimido"], julio["enviados"]) == (False, 0)  # el cero no se suprime


@pytest.mark.regla("I-04")
def test_periodo_al_reves_dice_que_hasta_no_puede_ser_anterior(sesion_gestion):
    respuesta = sesion_gestion.get(URL_IND, {"desde": "2026-09", "hasta": "2026-08"})

    assert respuesta.status_code == 400
    assert "igual o posterior" in respuesta.json()["errores"]["hasta"]
