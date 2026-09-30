"""Aceptar, rechazar, cancelar y cerrar tickets (S4, incrementos 5 y 6).

RF-19 a RF-24, HU-10, HU-15, HU-23, CA-10.2, CA-14.3, CA-15.2 a CA-15.4,
CA-23.1 a CA-23.7, RNF-07, RNF-08; ADR-023, puntos 3 a 6; ADR-024, punto 2;
ADR-016 E-1. Datos ficticios (``tests.tickets_ayudas``). Reloj: miércoles
7 de octubre de 2026, 08:00 en Santiago (sin cambio de horario cerca).
"""
import datetime
import json
import threading
from urllib.parse import parse_qs, urlsplit

import pytest
import time_machine
from django.db import connection
from django.utils import timezone

from autorizacion.models import RegistroAccesoDenegado
from comun.api import respuesta_no_encontrado
from expediente.errores import ErrorEstado
from expediente.management.commands import planificador
from identidad.models import Rol
from perfil.models import ServicioMaestro
from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from tests.ayudas import TEL_A, post_json
from tests.privacidad import assert_campos_ausentes
from tickets import servicios, transiciones
from tickets import vistas as vistas_tickets
from tickets.models import AutorTipo, AvisoTicket, EstadoTicket, MotivoCierre, Ticket, TicketEvento, TipoAvisoTicket

pytestmark = pytest.mark.django_db

D = datetime.timedelta
AHORA = tk.AHORA
NO_ENCONTRADO = respuesta_no_encontrado().content
PRIVADOS_DEL_CLIENTE = (tk.DIRECCION, tk.TELEFONO_CLIENTE, tk.NOMBRE_CLIENTE)


@pytest.fixture
def reloj():
    with time_machine.travel(AHORA, tick=False):
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


@pytest.fixture
def otro_cliente(reloj):
    return tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A)


@pytest.fixture
def sesion_cliente(cliente):
    return tk.sesion(tk.CORREO_CLIENTE)


@pytest.fixture
def sesion_maestro(maestro):
    return tk.sesion(ay.rut(1))


def _url(ticket, accion):
    return f"{tk.URL}/{ticket.ref}/{accion}"


def _post(sesion, ticket, accion):
    return post_json(sesion, _url(ticket, accion), {})


def _pendiente(cliente, maestro, inicio="08:00", fin="12:00", fecha=None, **extra):
    return tk.ticket_directo(cliente, maestro, fecha or tk.JUEVES, inicio, fin, **extra)


def _eventos(ticket):
    return list(TicketEvento.objects.filter(ticket_id=ticket.pk).order_by("id"))


def _avisos(ticket, tipo):
    return set(AvisoTicket.objects.filter(ticket=ticket, tipo=tipo).values_list("destinatario_id", flat=True))


# --- Aceptar (RF-19, CA-15.2, CA-14.3) ---


def test_rf19_aceptar_pasa_a_aceptado_con_evento_y_aviso_al_cliente(sesion_maestro, cliente, maestro):
    ticket = _pendiente(cliente, maestro)

    respuesta = _post(sesion_maestro, ticket, "aceptacion")

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta["Cache-Control"] == "no-store"
    datos = respuesta.json()["ticket"]
    assert (datos["estado"], datos["motivo_cierre"]) == (EstadoTicket.ACEPTADO, None)
    ticket.refresh_from_db()
    assert ticket.aceptado_en == AHORA
    evento = _eventos(ticket)[-1]
    assert (evento.estado_anterior, evento.estado_nuevo, evento.autor_tipo, evento.autor_id) == (
        EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO, AutorTipo.USUARIO, maestro.pk
    )
    assert _avisos(ticket, TipoAvisoTicket.TICKET_ACEPTADO) == {cliente.pk}


@pytest.mark.regla("A-03")
def test_ca15_2_d21_al_aceptar_aparece_el_contacto_mutuo(sesion_maestro, sesion_cliente, cliente, maestro):
    ticket = _pendiente(cliente, maestro)
    antes = sesion_maestro.get(f"{tk.URL}/{ticket.ref}")
    assert_campos_ausentes(antes, {"contacto", "direccion", "telefono"}, PRIVADOS_DEL_CLIENTE)

    crudo = json.loads(_post(sesion_maestro, ticket, "aceptacion").content)

    assert crudo["ticket"]["contacto"] == {
        "nombre": tk.NOMBRE_CLIENTE, "telefono": tk.TELEFONO_CLIENTE, "direccion": tk.DIRECCION
    }
    del_cliente = json.loads(sesion_cliente.get(f"{tk.URL}/{ticket.ref}").content)["ticket"]
    assert del_cliente["contacto"] == {"telefono": maestro.telefono}


@pytest.mark.regla("C-06")
def test_rf19_ca23_5_aceptar_cierra_los_pendientes_que_se_cruzan_con_bloque_tomado(
    sesion_maestro, cliente, otro_cliente, maestro
):
    elegido = _pendiente(cliente, maestro, "08:00", "12:00")
    mismo = _pendiente(otro_cliente, maestro, "08:00", "12:00")
    cruzado = _pendiente(otro_cliente, maestro, "10:00", "14:00")
    contiguo = _pendiente(otro_cliente, maestro, "12:00", "16:00")

    assert _post(sesion_maestro, elegido, "aceptacion").status_code == 200

    for ticket in (mismo, cruzado):
        ticket.refresh_from_db()
        assert (ticket.estado, ticket.motivo_cierre, ticket.cerrado_en) == (
            EstadoTicket.CERRADO, MotivoCierre.BLOQUE_TOMADO, AHORA
        )
        evento = _eventos(ticket)[-1]
        assert (evento.motivo, evento.autor_tipo, evento.autor_id) == (
            MotivoCierre.BLOQUE_TOMADO, AutorTipo.USUARIO, maestro.pk
        )
        assert _avisos(ticket, TipoAvisoTicket.TICKET_CERRADO) == {otro_cliente.pk, maestro.pk}
    contiguo.refresh_from_db()
    assert contiguo.estado == EstadoTicket.PENDIENTE


def test_ca23_5_el_aviso_de_bloque_tomado_lleva_al_cliente_a_la_busqueda_con_alternativas(
    sesion_maestro, cliente, otro_cliente, maestro, catalogo
):
    elegido = _pendiente(cliente, maestro)
    tomado = _pendiente(otro_cliente, maestro)
    _post(sesion_maestro, elegido, "aceptacion")

    avisos = tk.sesion("otro.cliente@example.com").get(tk.URL_AVISOS).json()["avisos"]

    aviso = next(a for a in avisos if a["ticket"] == str(tomado.ref))
    assert aviso["tipo"] == TipoAvisoTicket.TICKET_CERRADO
    assert "tomó otro trabajo en ese horario" in aviso["texto"]
    partes = urlsplit(aviso["enlace"])
    assert partes.path == "/buscar.html"
    assert parse_qs(partes.query) == {
        "oficio": [catalogo["pintura"].oficio.codigo], "region": [str(8)], "comuna": [str(ay.CONCEPCION)],
        "fecha": [tk.JUEVES.isoformat()], "inicio": ["08:00"], "fin": ["12:00"],
    }
    # El maestro no recibe enlace de alternativas; su aviso dice que aceptó otro trabajo.
    del_maestro = tk.sesion(ay.rut(1)).get(tk.URL_AVISOS).json()["avisos"]
    propio = next(a for a in del_maestro if a["ticket"] == str(tomado.ref) and a["tipo"] == "ticket_cerrado")
    assert propio["enlace"] is None


@pytest.mark.regla("F-10")
def test_ca14_3_aceptado_el_horario_queda_ocupado_para_nuevos_pedidos(sesion_maestro, cliente, maestro, catalogo):
    ticket = _pendiente(cliente, maestro)
    _post(sesion_maestro, ticket, "aceptacion")
    tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A)

    respuesta = tk.enviar(tk.sesion("otro.cliente@example.com"), tk.pedido(maestro, catalogo))

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == servicios.MENSAJE_HORARIO_OCUPADO


def test_d11_no_se_acepta_si_el_servicio_ya_no_esta_visible_y_sigue_pendiente(sesion_maestro, cliente, maestro):
    ticket = _pendiente(cliente, maestro)
    ServicioMaestro.objects.filter(maestro_id=maestro.pk).update(retirado_en=AHORA)

    respuesta = _post(sesion_maestro, ticket, "aceptacion")

    assert respuesta.status_code == 409
    assert respuesta.json() == {"mensaje": transiciones.MENSAJE_SERVICIO_NO_VISIBLE, "errores": {}}
    ticket.refresh_from_db()
    assert ticket.estado == EstadoTicket.PENDIENTE
    # Se puede rechazar (ADR-023, punto 3: no se inventa un sexto motivo).
    assert _post(sesion_maestro, ticket, "rechazo").status_code == 200


def test_no_se_acepta_si_se_cruza_con_otro_trabajo_aceptado(sesion_maestro, cliente, otro_cliente, maestro):
    _pendiente(otro_cliente, maestro, "10:00", "14:00", estado=EstadoTicket.ACEPTADO)
    ticket = _pendiente(cliente, maestro, "08:00", "12:00")

    respuesta = _post(sesion_maestro, ticket, "aceptacion")

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == transiciones.MENSAJE_CRUCE
    ticket.refresh_from_db()
    assert ticket.estado == EstadoTicket.PENDIENTE


# --- Rechazar (RF-20, CA-15.3, CA-23.4) ---


@pytest.mark.regla("C-05")
def test_rf20_rechazar_cierra_y_el_horario_queda_libre_para_otro_cliente(sesion_maestro, cliente, maestro, catalogo):
    ticket = _pendiente(cliente, maestro)

    respuesta = _post(sesion_maestro, ticket, "rechazo")

    assert respuesta.status_code == 200
    assert (respuesta.json()["ticket"]["estado"], respuesta.json()["ticket"]["motivo_cierre"]) == (
        EstadoTicket.CERRADO, MotivoCierre.RECHAZADO_MAESTRO
    )
    assert _avisos(ticket, TipoAvisoTicket.TICKET_CERRADO) == {cliente.pk, maestro.pk}
    tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A)
    otro = tk.enviar(tk.sesion("otro.cliente@example.com"), tk.pedido(maestro, catalogo))
    assert otro.status_code == 201


# --- Cancelar (RF-23, CA-23.3, CA-10.2) ---


@pytest.mark.regla("C-04")
def test_rf23_el_cliente_cancela_y_despues_no_se_puede_aceptar(sesion_cliente, sesion_maestro, cliente, maestro):
    ticket = _pendiente(cliente, maestro)

    respuesta = _post(sesion_cliente, ticket, "cancelacion")

    assert respuesta.status_code == 200
    assert respuesta.json()["ticket"]["motivo_cierre"] == MotivoCierre.CANCELADO_CLIENTE
    assert _avisos(ticket, TipoAvisoTicket.TICKET_CERRADO) == {cliente.pk, maestro.pk}
    aceptar = _post(sesion_maestro, ticket, "aceptacion")
    assert aceptar.status_code == 409
    assert aceptar.json()["mensaje"] == "Este pedido se cerró: el cliente lo canceló. Ya no se puede responder."


def test_ca10_2_un_ticket_aceptado_no_se_cancela_y_se_indica_coordinar(sesion_cliente, cliente, maestro):
    ticket = _pendiente(cliente, maestro, estado=EstadoTicket.ACEPTADO)

    respuesta = _post(sesion_cliente, ticket, "cancelacion")

    assert respuesta.status_code == 409
    assert respuesta.json() == {"mensaje": transiciones.MENSAJE_YA_ACEPTADO_CANCELACION, "errores": {}}
    ticket.refresh_from_db()
    assert ticket.estado == EstadoTicket.ACEPTADO


@pytest.mark.parametrize(
    ("estado", "accion", "mensaje"),
    [
        (EstadoTicket.ACEPTADO, "rechazo", transiciones.MENSAJE_YA_ACEPTADO_RECHAZO),
        (EstadoTicket.FINALIZADO, "aceptacion", transiciones.MENSAJE_FINALIZADO),
        (EstadoTicket.FINALIZADO, "rechazo", transiciones.MENSAJE_FINALIZADO),
    ],
)
def test_otras_transiciones_del_maestro_responden_409_accionable(sesion_maestro, cliente, maestro, estado, accion,
                                                                  mensaje):
    ticket = _pendiente(cliente, maestro, estado=estado)

    respuesta = _post(sesion_maestro, ticket, accion)

    assert respuesta.status_code == 409
    assert respuesta.json() == {"mensaje": mensaje, "errores": {}}


# --- Idempotencia (D-10) ---


@pytest.mark.parametrize(
    ("accion", "de_quien"), [("aceptacion", "maestro"), ("rechazo", "maestro"), ("cancelacion", "cliente")]
)
def test_d10_repetir_la_accion_devuelve_200_con_el_estado_actual_sin_efectos(
    sesion_cliente, sesion_maestro, cliente, maestro, accion, de_quien
):
    sesion = sesion_maestro if de_quien == "maestro" else sesion_cliente
    ticket = _pendiente(cliente, maestro)
    primera = _post(sesion, ticket, accion)
    eventos, avisos = len(_eventos(ticket)), AvisoTicket.objects.count()

    segunda = _post(sesion, ticket, accion)

    assert segunda.status_code == 200
    assert segunda.json() == primera.json()
    assert (len(_eventos(ticket)), AvisoTicket.objects.count()) == (eventos, avisos)


# --- Autorización (ADR-023, punto 6; A-02, CA-25.1) ---


@pytest.mark.regla("A-02")
@pytest.mark.parametrize(("accion", "de_quien"), [("aceptacion", "cliente"), ("rechazo", "cliente"),
                                                  ("cancelacion", "maestro")])
def test_a02_la_parte_equivocada_recibe_403_registrado_sin_cambios(
    sesion_cliente, sesion_maestro, cliente, maestro, accion, de_quien
):
    sesion = sesion_cliente if de_quien == "cliente" else sesion_maestro
    usuario = cliente if de_quien == "cliente" else maestro
    ticket = _pendiente(cliente, maestro)

    respuesta = _post(sesion, ticket, accion)

    assert respuesta.status_code == 403
    cancela = accion == "cancelacion"
    esperado = vistas_tickets.MENSAJE_SOLO_CLIENTE if cancela else vistas_tickets.MENSAJE_SOLO_MAESTRO
    assert respuesta.json() == {"mensaje": esperado, "errores": {}}
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (usuario.pk, "ticket", str(ticket.ref))
    assert fila.recurso == f"POST api/tickets/<uuid:ref>/{accion}"
    ticket.refresh_from_db()
    assert ticket.estado == EstadoTicket.PENDIENTE
    assert _eventos(ticket) == []  # ticket_directo no escribe el evento inicial


def _terceros(catalogo):
    return {
        "otro_cliente": (lambda: tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A),
                         "otro.cliente@example.com"),
        "otro_maestro": (lambda: tk.maestro_con_agenda(catalogo, n=2), ay.rut(2)),
        "curatoria": (lambda: tk.administrativo(Rol.CURATORIA, "cura@example.com"), "cura@example.com"),
        "moderacion": (lambda: tk.administrativo(Rol.MODERACION, "moderacion@example.com"), "moderacion@example.com"),
    }


@pytest.mark.terceros("ticket_aceptacion", "ticket_rechazo", "ticket_cancelacion")
@pytest.mark.regla("A-01")
@pytest.mark.parametrize("accion", ["aceptacion", "rechazo", "cancelacion"])
@pytest.mark.parametrize("nombre", ["otro_cliente", "otro_maestro", "curatoria", "moderacion"])
def test_ca25_1_un_tercero_recibe_el_404_identico_con_registro(cliente, maestro, catalogo, accion, nombre):
    ticket = _pendiente(cliente, maestro)
    crear, identificador = _terceros(catalogo)[nombre]
    tercero = crear()

    respuesta = _post(tk.sesion(identificador), ticket, accion)

    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "ticket", str(ticket.ref))
    ticket.refresh_from_db()
    assert ticket.estado == EstadoTicket.PENDIENTE


def test_una_clave_en_el_cuerpo_se_rechaza_con_400(sesion_maestro, cliente, maestro):
    ticket = _pendiente(cliente, maestro)

    respuesta = post_json(sesion_maestro, _url(ticket, "aceptacion"), {"estado": "aceptado"})

    assert respuesta.status_code == 400
    ticket.refresh_from_db()
    assert ticket.estado == EstadoTicket.PENDIENTE


# --- Privacidad de los cerrados desde pendiente (ADR-023, punto 5; RNF-08) ---


@pytest.mark.regla("A-03")
@pytest.mark.parametrize("motivo", list(MotivoCierre))
def test_rnf08_un_ticket_cerrado_desde_pendiente_nunca_revela_la_direccion_al_maestro(
    sesion_maestro, cliente, maestro, motivo
):
    ticket = _pendiente(cliente, maestro, estado=EstadoTicket.CERRADO, motivo=motivo)

    for respuesta in (sesion_maestro.get(f"{tk.URL}/{ticket.ref}"), sesion_maestro.get(tk.URL_MAESTRO)):
        assert respuesta.status_code == 200
        assert_campos_ausentes(respuesta, {"contacto", "direccion", "telefono"}, PRIVADOS_DEL_CLIENTE)


# --- Cierre automático (RF-21, RF-22, CA-23.1, CA-23.2, CA-23.6; ADR-016 E-1) ---


def _en(instante):
    return time_machine.travel(instante, tick=False)


@pytest.mark.regla("C-01", "C-02", "C-03")
@pytest.mark.parametrize(
    ("inicio", "fecha", "motivo"),
    [
        ("08:00", tk.JUEVES, MotivoCierre.VENCIDO_PROXIMIDAD),  # 24 h: vence a las 20 h (inicio - 4 h)
        ("12:00", tk.JUEVES, MotivoCierre.VENCIDO_PROXIMIDAD),  # 28 h exactas: coinciden; gana proximidad
        ("08:00", tk.VIERNES, MotivoCierre.VENCIDO_PLAZO),  # 48 h: vence a las 24 h
    ],
)
def test_ca23_la_tarea_cierra_al_vencer_con_el_motivo_correcto(cliente, maestro, inicio, fecha, motivo):
    fin = {"08:00": "12:00", "12:00": "16:00"}[inicio]
    ticket = _pendiente(cliente, maestro, inicio, fin, fecha=fecha)
    vence = ticket.vence_en

    with _en(vence - D(seconds=1)):
        assert transiciones.cerrar_vencidos(timezone.now()) == 0
    with _en(vence):
        conteos, fallidas = planificador.correr_tareas()

    assert "tickets_cerrados" not in fallidas and conteos["tickets_cerrados"] == 1
    ticket.refresh_from_db()
    assert (ticket.estado, ticket.motivo_cierre, ticket.cerrado_en) == (EstadoTicket.CERRADO, motivo, vence)
    evento = _eventos(ticket)[-1]
    assert (evento.motivo, evento.autor_tipo, evento.autor_id) == (motivo, AutorTipo.SISTEMA, None)
    assert _avisos(ticket, TipoAvisoTicket.TICKET_CERRADO) == {cliente.pk, maestro.pk}


@pytest.mark.regla("C-03")
def test_ca23_6_el_borde_de_28_horas_exactas_cuenta_como_proximidad():
    ticket = Ticket(enviado_en=AHORA, inicio_en=AHORA + D(hours=28))
    assert transiciones.motivo_vencimiento(ticket) == MotivoCierre.VENCIDO_PROXIMIDAD
    ticket.inicio_en = AHORA + D(hours=28, seconds=1)
    assert transiciones.motivo_vencimiento(ticket) == MotivoCierre.VENCIDO_PLAZO


def test_la_tarea_es_idempotente_y_no_toca_otros_estados(cliente, otro_cliente, maestro):
    vencido = _pendiente(cliente, maestro, enviado_en=AHORA - D(hours=25), fecha=tk.VIERNES)
    vigente = _pendiente(otro_cliente, maestro, "12:00", "16:00", fecha=tk.VIERNES)
    aceptado = _pendiente(otro_cliente, maestro, estado=EstadoTicket.ACEPTADO)

    assert transiciones.cerrar_vencidos(AHORA) == 1
    assert transiciones.cerrar_vencidos(AHORA) == 0

    vencido.refresh_from_db(), vigente.refresh_from_db(), aceptado.refresh_from_db()
    assert vencido.motivo_cierre == MotivoCierre.VENCIDO_PLAZO
    assert (vigente.estado, aceptado.estado) == (EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO)
    assert len(_eventos(vencido)) == 1


@pytest.mark.regla("C-07")
def test_rf24_los_cinco_motivos_quedan_registrados_de_forma_distinguible(
    sesion_cliente, sesion_maestro, cliente, otro_cliente, maestro
):
    plazo = _pendiente(cliente, maestro, fecha=tk.VIERNES, enviado_en=AHORA - D(hours=25))
    proximidad = _pendiente(cliente, maestro, "12:00", "16:00", fecha=tk.HOY, enviado_en=AHORA - D(hours=2))
    cancelado = _pendiente(cliente, maestro, "08:00", "12:00", fecha=tk.VIERNES + D(days=1))
    rechazado = _pendiente(cliente, maestro, "12:00", "16:00", fecha=tk.VIERNES)
    elegido = _pendiente(otro_cliente, maestro)
    tomado = _pendiente(cliente, maestro)

    assert transiciones.cerrar_vencidos(AHORA) == 2
    _post(sesion_cliente, cancelado, "cancelacion")
    _post(sesion_maestro, rechazado, "rechazo")
    _post(sesion_maestro, elegido, "aceptacion")

    motivos = {
        t.pk: m for t, m in ((plazo, MotivoCierre.VENCIDO_PLAZO), (proximidad, MotivoCierre.VENCIDO_PROXIMIDAD),
                             (cancelado, MotivoCierre.CANCELADO_CLIENTE), (rechazado, MotivoCierre.RECHAZADO_MAESTRO),
                             (tomado, MotivoCierre.BLOQUE_TOMADO))
    }
    for pk, motivo in motivos.items():
        assert Ticket.objects.get(pk=pk).motivo_cierre == motivo
        assert TicketEvento.objects.filter(ticket_id=pk, motivo=motivo).count() == 1
    assert len(set(motivos.values())) == 5


# --- Protección al actuar (ADR-016 E-1) ---


@pytest.mark.regla("C-01")
@pytest.mark.parametrize(("accion", "de_quien"), [("aceptacion", "maestro"), ("rechazo", "maestro"),
                                                  ("cancelacion", "cliente")])
def test_una_accion_sobre_un_pendiente_vencido_lo_cierra_y_responde_409(
    sesion_cliente, sesion_maestro, cliente, maestro, accion, de_quien
):
    sesion = sesion_maestro if de_quien == "maestro" else sesion_cliente
    ticket = _pendiente(cliente, maestro, fecha=tk.VIERNES, enviado_en=AHORA - D(hours=24))

    respuesta = _post(sesion, ticket, accion)

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"].startswith(
        ("Este pedido se cerró: pasaron 24 horas", "Tu pedido se cerró: el maestro no respondió en 24 horas")
    )
    ticket.refresh_from_db()
    assert (ticket.estado, ticket.motivo_cierre, ticket.cerrado_en) == (
        EstadoTicket.CERRADO, MotivoCierre.VENCIDO_PLAZO, AHORA
    )
    assert _eventos(ticket)[-1].autor_tipo == AutorTipo.SISTEMA
    assert _avisos(ticket, TipoAvisoTicket.TICKET_CERRADO) == {cliente.pk, maestro.pk}
    # Un segundo intento ya no cambia nada y sigue siendo 409.
    assert _post(sesion, ticket, accion).status_code == 409
    assert len(_eventos(ticket)) == 1


def test_aceptar_con_un_pendiente_cruzado_ya_vencido_lo_cierra_por_su_vencimiento(
    sesion_maestro, cliente, otro_cliente, maestro
):
    elegido = _pendiente(cliente, maestro, fecha=tk.VIERNES)
    vencido = _pendiente(otro_cliente, maestro, fecha=tk.VIERNES, enviado_en=AHORA - D(hours=24))

    assert _post(sesion_maestro, elegido, "aceptacion").status_code == 200

    vencido.refresh_from_db()
    assert vencido.motivo_cierre == MotivoCierre.VENCIDO_PLAZO
    assert _eventos(vencido)[-1].autor_tipo == AutorTipo.SISTEMA


def test_d10_repetir_un_pedido_vencido_lo_cierra_responde_409_y_permite_enviarlo_de_nuevo(
    sesion_cliente, cliente, maestro, catalogo
):
    viejo = _pendiente(cliente, maestro, fecha=tk.VIERNES, enviado_en=AHORA - D(hours=25))
    datos = tk.pedido(maestro, catalogo, fecha=tk.VIERNES.isoformat())

    respuesta = tk.enviar(sesion_cliente, datos)

    assert respuesta.status_code == 409
    assert respuesta.json() == {
        "mensaje": servicios.MENSAJE_PENDIENTE_VENCIDO.format(motivo="el maestro no respondió en 24 horas"),
        "errores": {},
    }
    viejo.refresh_from_db()
    assert (viejo.estado, viejo.motivo_cierre) == (EstadoTicket.CERRADO, MotivoCierre.VENCIDO_PLAZO)
    assert tk.enviar(sesion_cliente, datos).status_code == 201


# --- Concurrencia (D-9; ADR-023, punto 4) ---


@pytest.mark.django_db(transaction=True)
@pytest.mark.regla("C-06")
def test_d9_dos_aceptaciones_simultaneas_de_rangos_que_se_cruzan_dejan_solo_una(catalogo):
    # transaction=True: cada hilo usa su propia conexión. ``ticket_evento`` y
    # ``acceso_denegado`` no se vacían al terminar (managed=False, sin FK); los
    # ids no se repiten, así que no afectan a otras pruebas.
    maestro = tk.maestro_con_agenda(catalogo)
    uno = tk.cliente()
    dos = tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A)
    tickets = [_pendiente(uno, maestro, "08:00", "12:00"), _pendiente(dos, maestro, "10:00", "14:00")]
    barrera = threading.Barrier(2)
    resultados = []
    candado = threading.Lock()

    def aceptar(ticket):
        try:
            barrera.wait(timeout=10)
            resultado = transiciones.aceptar(ticket, maestro, ahora=AHORA)
        except ErrorEstado as error:
            resultado = error
        finally:
            connection.close()
        with candado:
            resultados.append(resultado)

    hilos = [threading.Thread(target=aceptar, args=(t,)) for t in tickets]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    assert len(resultados) == 2
    assert sum(isinstance(r, ErrorEstado) for r in resultados) == 1, resultados
    estados = sorted(Ticket.objects.filter(pk__in=[t.pk for t in tickets]).values_list("estado", "motivo_cierre"))
    assert estados == [(EstadoTicket.ACEPTADO, None), (EstadoTicket.CERRADO, MotivoCierre.BLOQUE_TOMADO)]
