"""Precio final, finalización e historial (S5, incremento 1).

HU-16, HU-08; RF-26 a RF-28; CA-16.1 a CA-16.3, CA-08.1, CA-08.2; RNF-07, RNF-11;
ADR-026, E-1 y E-5; propuesta del S5, §3.1 a §3.3. Datos ficticios
(``tests.tickets_ayudas``). Reloj: miércoles 7 de octubre de 2026, 08:00 en
Santiago; el trabajo es el jueves de 08:00 a 12:00 (empieza en 24 horas). La
aritmética de horas se hace en UTC (DEF-QA-005).
"""
import contextlib
import datetime

import pytest
import time_machine
from django.db import IntegrityError, connection, transaction

from autorizacion.models import RegistroAccesoDenegado
from catalogo.models import Modalidad
from comun.api import MENSAJE_CLAVE_DESCONOCIDA, respuesta_no_encontrado
from comun.solo_insercion import OperacionNoPermitida
from identidad.models import Rol
from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from tests.ayudas import TEL_A, iniciar_sesion, post_json
from tickets import transiciones
from tickets import vistas as vistas_tickets
from tickets.models import (
    AccionPrecio,
    AutorTipo,
    AvisoTicket,
    EstadoTicket,
    MotivoCierre,
    PrecioFinalEvento,
    Ticket,
    TicketEvento,
    TipoAvisoTicket,
)

pytestmark = pytest.mark.django_db

D = datetime.timedelta
UTC = datetime.timezone.utc
AHORA = tk.AHORA
NO_ENCONTRADO = respuesta_no_encontrado().content
PUBLICADO = 20001  # monto de ``busqueda_ayudas.maestro(1)``


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


# Sesiones de la prueba: al saltar en el tiempo expiran (1800 s, ADR-005) y ``_a`` las renueva.
_SESIONES = []


@pytest.fixture(autouse=True)
def _limpiar_sesiones():
    _SESIONES.clear()
    yield
    _SESIONES.clear()


def _sesion(identificador):
    client = tk.sesion(identificador)
    _SESIONES.append((client, identificador))
    return client


@pytest.fixture
def sesion_cliente(cliente):
    return _sesion(tk.CORREO_CLIENTE)


@pytest.fixture
def sesion_maestro(maestro):
    return _sesion(ay.rut(1))


def _aceptado(cliente, maestro, modalidad=Modalidad.POR_TRABAJO):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.ACEPTADO)
    if modalidad != ticket.modalidad:
        Ticket.objects.filter(pk=ticket.pk).update(modalidad=modalidad)
        ticket.refresh_from_db()
    return ticket


@contextlib.contextmanager
def _a(instante):
    """Viaja a ``instante`` y vuelve a iniciar las sesiones de la prueba."""
    with time_machine.travel(instante, tick=False):
        for client, identificador in _SESIONES:
            assert iniciar_sesion(client, identificador).status_code == 200
        yield


def _en_el_horario(ticket, horas=1):
    """Un reloj dentro del horario del trabajo (suma en UTC, DEF-QA-005)."""
    return _a(ticket.inicio_en.astimezone(UTC) + D(hours=horas))


def _registrar(sesion, ticket, monto):
    return post_json(sesion, f"{tk.URL}/{ticket.ref}/precio-final", {"monto": monto})


def _aceptar(sesion, ticket, monto):
    return post_json(sesion, f"{tk.URL}/{ticket.ref}/precio-final/aceptacion", {"monto": monto})


def _objetar(sesion, ticket, cuerpo=None):
    return post_json(sesion, f"{tk.URL}/{ticket.ref}/precio-final/objecion", cuerpo or {})


def _acciones(ticket):
    return [(e.accion, e.monto, e.autor_id) for e in PrecioFinalEvento.objects.filter(ticket_id=ticket.pk).order_by("id")]


def _eventos(ticket):
    return [(e.estado_anterior, e.estado_nuevo, e.autor_tipo, e.autor_id)
            for e in TicketEvento.objects.filter(ticket_id=ticket.pk).order_by("id")]


def _avisos(ticket, tipo):
    return set(AvisoTicket.objects.filter(ticket=ticket, tipo=tipo).values_list("destinatario_id", flat=True))


# --- Finalización según la modalidad (RF-26, RF-27, CA-16.1, CA-16.2) ---


@pytest.mark.regla("C-09")
def test_rf27_por_trabajo_con_el_monto_publicado_finaliza_sin_aceptacion(sesion_maestro, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        ahora = datetime.datetime.now(UTC)
        respuesta = _registrar(sesion_maestro, ticket, PUBLICADO)

    assert respuesta.status_code == 200, respuesta.content
    datos = respuesta.json()["ticket"]
    assert datos["estado"] == EstadoTicket.FINALIZADO
    assert (datos["precio"]["monto"], datos["precio"]["estado"], datos["precio"]["aceptado_en"]) == (
        PUBLICADO, "acordado", None
    )
    ticket.refresh_from_db()
    assert (ticket.monto_final, ticket.monto_final_autor_id, ticket.finalizado_en) == (PUBLICADO, maestro.pk, ahora)
    assert ticket.monto_final_en == ahora
    assert _eventos(ticket) == [(EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO, AutorTipo.USUARIO, maestro.pk)]
    assert _acciones(ticket) == [(AccionPrecio.REGISTRADO, PUBLICADO, maestro.pk)]
    assert _avisos(ticket, TipoAvisoTicket.ORDEN_FINALIZADA) == {cliente.pk}


@pytest.mark.regla("C-10")
def test_ca16_2_por_trabajo_con_otro_monto_espera_la_aceptacion_del_cliente(
    sesion_maestro, sesion_cliente, cliente, maestro
):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        registro = _registrar(sesion_maestro, ticket, 25000)
        ticket.refresh_from_db()
        assert registro.status_code == 200 and ticket.estado == EstadoTicket.ACEPTADO
        assert registro.json()["ticket"]["precio"]["estado"] == "por_aceptar"
        assert _avisos(ticket, TipoAvisoTicket.PRECIO_REGISTRADO) == {cliente.pk}
        assert _eventos(ticket) == []

        aceptacion = _aceptar(sesion_cliente, ticket, 25000)

    assert aceptacion.status_code == 200, aceptacion.content
    assert aceptacion.json()["ticket"]["precio"]["estado"] == "acordado"
    ticket.refresh_from_db()
    assert (ticket.estado, ticket.monto_final) == (EstadoTicket.FINALIZADO, 25000)
    assert ticket.precio_aceptado_en is not None
    assert _eventos(ticket) == [(EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO, AutorTipo.USUARIO, cliente.pk)]
    assert _acciones(ticket) == [(AccionPrecio.REGISTRADO, 25000, maestro.pk), (AccionPrecio.ACEPTADO, 25000, cliente.pk)]
    assert _avisos(ticket, TipoAvisoTicket.ORDEN_FINALIZADA) == {maestro.pk}


@pytest.mark.regla("C-11")
def test_rf27_por_hora_siempre_exige_aceptacion_aunque_el_monto_sea_el_publicado(sesion_maestro, cliente, maestro):
    ticket = _aceptado(cliente, maestro, Modalidad.POR_HORA)
    with _en_el_horario(ticket):
        respuesta = _registrar(sesion_maestro, ticket, PUBLICADO)

    assert respuesta.status_code == 200
    ticket.refresh_from_db()
    assert (ticket.estado, ticket.monto_final, ticket.precio_aceptado_en) == (EstadoTicket.ACEPTADO, PUBLICADO, None)
    assert respuesta.json()["ticket"]["precio"]["estado"] == "por_aceptar"


@pytest.mark.regla("C-12")
def test_e1_4_aceptar_un_monto_que_no_es_el_vigente_da_409_sin_cambios(sesion_maestro, sesion_cliente, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        _registrar(sesion_maestro, ticket, 25000)
        _registrar(sesion_maestro, ticket, 27000)  # el maestro lo cambió entre medio
        respuesta = _aceptar(sesion_cliente, ticket, 25000)

    assert respuesta.status_code == 409
    assert respuesta.json() == {"mensaje": transiciones.MENSAJE_MONTO_CAMBIO, "errores": {}}
    ticket.refresh_from_db()
    assert (ticket.estado, ticket.monto_final, ticket.precio_aceptado_en) == (EstadoTicket.ACEPTADO, 27000, None)
    assert [a for a, _, _ in _acciones(ticket)] == [AccionPrecio.REGISTRADO, AccionPrecio.REGISTRADO]


@pytest.mark.regla("C-13")
def test_ca16_3_una_orden_finalizada_no_cambia_de_precio(sesion_maestro, sesion_cliente, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        _registrar(sesion_maestro, ticket, PUBLICADO)
        otro_monto = _registrar(sesion_maestro, ticket, 30000)
        objecion = _objetar(sesion_cliente, ticket)
        repetido = _registrar(sesion_maestro, ticket, PUBLICADO)

    for respuesta in (otro_monto, objecion):
        assert respuesta.status_code == 409
        assert respuesta.json() == {"mensaje": transiciones.MENSAJE_PRECIO_FINALIZADO, "errores": {}}
    assert repetido.status_code == 200  # repetir lo mismo es idempotente (D-10)
    ticket.refresh_from_db()
    assert (ticket.estado, ticket.monto_final) == (EstadoTicket.FINALIZADO, PUBLICADO)
    assert len(_acciones(ticket)) == 1 and len(_eventos(ticket)) == 1


@pytest.mark.regla("C-14")
@pytest.mark.parametrize(
    ("modalidad", "sql", "restriccion"),
    [
        (Modalidad.POR_TRABAJO, "estado = 'finalizado', finalizado_en = aceptado_en", "ticket_finalizado_con_precio"),
        (Modalidad.POR_TRABAJO, "estado = 'finalizado', finalizado_en = aceptado_en, monto_final = monto_publicado + 1,"
         " monto_final_en = aceptado_en, monto_final_autor_id = perfil_maestro_id", "ticket_finalizado_con_precio"),
        (Modalidad.POR_HORA, "estado = 'finalizado', finalizado_en = aceptado_en, monto_final = monto_publicado,"
         " monto_final_en = aceptado_en, monto_final_autor_id = perfil_maestro_id", "ticket_finalizado_con_precio"),
        (Modalidad.POR_TRABAJO, "monto_final = 1000", "ticket_monto_final_con_fecha_y_autor"),
        (Modalidad.POR_TRABAJO, "precio_aceptado_en = aceptado_en", "ticket_aceptacion_exige_monto_final"),
        (Modalidad.POR_TRABAJO, "monto_final = 0, monto_final_en = aceptado_en, monto_final_autor_id = perfil_maestro_id",
         "ticket_monto_final_valido"),
    ],
)
def test_e1_8_los_check_del_precio_final_en_la_base(cliente, maestro, modalidad, sql, restriccion):
    ticket = _aceptado(cliente, maestro, modalidad)

    with pytest.raises(IntegrityError, match=restriccion), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"UPDATE ticket SET {sql} WHERE id = %s", [ticket.pk])


@pytest.mark.regla("C-14")
def test_e1_8_un_pendiente_no_puede_tener_precio_final(cliente, maestro):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00")

    with pytest.raises(IntegrityError, match="ticket_monto_final_solo_aceptado_o_finalizado"), transaction.atomic(), \
            connection.cursor() as cursor:
        cursor.execute("UPDATE ticket SET monto_final = 1000, monto_final_en = enviado_en, "
                       "monto_final_autor_id = perfil_maestro_id WHERE id = %s", [ticket.pk])


@pytest.mark.regla("C-15")
def test_p27_no_se_registra_el_precio_antes_de_que_empiece_el_horario(sesion_maestro, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _a(ticket.inicio_en.astimezone(UTC) - D(minutes=1)):
        antes = _registrar(sesion_maestro, ticket, PUBLICADO)
        assert sesion_maestro.get(f"{tk.URL}/{ticket.ref}").json()["ticket"]["precio_registrable"] is False
    with _a(ticket.inicio_en.astimezone(UTC)):
        justo = _registrar(sesion_maestro, ticket, PUBLICADO)

    assert antes.status_code == 409
    assert antes.json() == {"mensaje": transiciones.MENSAJE_PRECIO_ANTES_DEL_HORARIO, "errores": {}}
    assert justo.status_code == 200 and justo.json()["ticket"]["estado"] == EstadoTicket.FINALIZADO


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [(EstadoTicket.PENDIENTE, transiciones.MENSAJE_PRECIO_SIN_ACEPTAR), (EstadoTicket.CERRADO, None)],
)
def test_sin_aceptar_no_hay_precio_final(sesion_maestro, cliente, maestro, estado, esperado):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=estado)
    with _en_el_horario(ticket, horas=-5):  # antes del vencimiento del pendiente
        respuesta = _registrar(sesion_maestro, ticket, PUBLICADO)

    assert respuesta.status_code == 409
    if esperado is None:
        esperado = transiciones.mensaje_cerrado(ticket, para_maestro=True)
    assert respuesta.json()["mensaje"] == esperado
    assert _acciones(ticket) == []


# --- Objeción (ADR-026, E-1.5) ---


def test_e1_5_objetar_vacia_el_precio_avisa_al_maestro_y_se_puede_registrar_de_nuevo(
    sesion_maestro, sesion_cliente, cliente, maestro
):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        _registrar(sesion_maestro, ticket, 25000)
        AvisoTicket.objects.filter(ticket=ticket).update(visto_en=datetime.datetime.now(UTC))
        objecion = _objetar(sesion_cliente, ticket)
        repetida = _objetar(sesion_cliente, ticket)
    with _en_el_horario(ticket, horas=2):
        de_nuevo = _registrar(sesion_maestro, ticket, 24000)

    assert objecion.status_code == 200 and objecion.json()["ticket"]["precio"] is None
    assert repetida.status_code == 200  # idempotente
    assert _avisos(ticket, TipoAvisoTicket.PRECIO_OBJETADO) == {maestro.pk}
    assert de_nuevo.status_code == 200 and de_nuevo.json()["ticket"]["precio"]["monto"] == 24000
    assert _acciones(ticket) == [
        (AccionPrecio.REGISTRADO, 25000, maestro.pk),
        (AccionPrecio.OBJETADO, 25000, cliente.pk),
        (AccionPrecio.REGISTRADO, 24000, maestro.pk),
    ]
    # El aviso de precio se reactiva (único por ticket, destinatario y tipo; ADR-026, E-2).
    aviso = AvisoTicket.objects.get(ticket=ticket, tipo=TipoAvisoTicket.PRECIO_REGISTRADO)
    assert aviso.visto_en is None and aviso.creado_en == ticket.inicio_en + D(hours=2)


def test_sin_precio_por_aceptar_aceptar_u_objetar_da_409(sesion_cliente, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        aceptacion = _aceptar(sesion_cliente, ticket, PUBLICADO)
        objecion = _objetar(sesion_cliente, ticket)

    for respuesta in (aceptacion, objecion):
        assert respuesta.status_code == 409
        assert respuesta.json()["mensaje"] == transiciones.MENSAJE_SIN_PRECIO_POR_ACEPTAR


def test_registrar_dos_veces_el_mismo_monto_es_idempotente(sesion_maestro, sesion_cliente, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        primera = _registrar(sesion_maestro, ticket, 25000)
        segunda = _registrar(sesion_maestro, ticket, 25000)
        _aceptar(sesion_cliente, ticket, 25000)
        aceptar_otra_vez = _aceptar(sesion_cliente, ticket, 25000)

    assert primera.status_code == segunda.status_code == aceptar_otra_vez.status_code == 200
    assert [a for a, _, _ in _acciones(ticket)] == [AccionPrecio.REGISTRADO, AccionPrecio.ACEPTADO]


# --- Validación del cuerpo (ADR-013, E-2) ---


@pytest.mark.parametrize("monto", [0, -5, 10_000_001, "mil", 1.5, True, None])
def test_un_monto_invalido_da_400_en_el_campo(sesion_maestro, cliente, maestro, monto):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        respuesta = _registrar(sesion_maestro, ticket, monto)

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"monto"}
    assert _acciones(ticket) == []


def test_claves_desconocidas_o_cuerpo_en_la_objecion_dan_400(sesion_maestro, sesion_cliente, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        desconocida = post_json(sesion_maestro, f"{tk.URL}/{ticket.ref}/precio-final", {"monto": 1, "x": 1})
        con_monto = _objetar(sesion_cliente, ticket, {"monto": 1})

    assert desconocida.status_code == 400
    assert desconocida.json() == {"mensaje": MENSAJE_CLAVE_DESCONOCIDA, "errores": {}}
    assert con_monto.status_code == 400 and set(con_monto.json()["errores"]) == {"monto"}


# --- Autorización (RNF-07; ADR-011; ADR-026, E-5) ---


@pytest.mark.regla("A-06")
@pytest.mark.parametrize(
    ("ruta", "de_quien", "cuerpo", "mensaje"),
    [
        ("precio-final", "cliente", {"monto": PUBLICADO}, vistas_tickets.MENSAJE_SOLO_MAESTRO_PRECIO),
        ("precio-final/aceptacion", "maestro", {"monto": PUBLICADO}, vistas_tickets.MENSAJE_SOLO_CLIENTE_PRECIO),
        ("precio-final/objecion", "maestro", {}, vistas_tickets.MENSAJE_SOLO_CLIENTE_PRECIO),
    ],
)
def test_e5_la_parte_equivocada_recibe_403_registrado_sin_cambios(
    sesion_cliente, sesion_maestro, cliente, maestro, ruta, de_quien, cuerpo, mensaje
):
    sesion, usuario = (sesion_cliente, cliente) if de_quien == "cliente" else (sesion_maestro, maestro)
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        respuesta = post_json(sesion, f"{tk.URL}/{ticket.ref}/{ruta}", cuerpo)

    assert respuesta.status_code == 403
    assert respuesta.json() == {"mensaje": mensaje, "errores": {}}
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (usuario.pk, "ticket", str(ticket.ref))
    assert fila.recurso == f"POST api/tickets/<uuid:ref>/{ruta}"
    ticket.refresh_from_db()
    assert (ticket.estado, ticket.monto_final) == (EstadoTicket.ACEPTADO, None)
    assert _acciones(ticket) == []


def _terceros(catalogo):
    return {
        "otro_cliente": (lambda: tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A),
                         "otro.cliente@example.com"),
        "otro_maestro": (lambda: tk.maestro_con_agenda(catalogo, n=2), ay.rut(2)),
        "curatoria": (lambda: tk.administrativo(Rol.CURATORIA, "cura@example.com"), "cura@example.com"),
        "moderacion": (lambda: tk.administrativo(Rol.MODERACION, "moderacion@example.com"), "moderacion@example.com"),
    }


@pytest.mark.terceros("ticket_precio_final", "ticket_precio_aceptacion", "ticket_precio_objecion")
@pytest.mark.regla("A-07")
@pytest.mark.parametrize(
    ("ruta", "cuerpo"),
    [("precio-final", {"monto": PUBLICADO}), ("precio-final/aceptacion", {"monto": PUBLICADO}),
     ("precio-final/objecion", {})],
)
@pytest.mark.parametrize("nombre", ["otro_cliente", "otro_maestro", "curatoria", "moderacion"])
def test_ca25_1_un_tercero_recibe_el_404_identico_con_registro(cliente, maestro, catalogo, ruta, cuerpo, nombre):
    ticket = _aceptado(cliente, maestro)
    crear, identificador = _terceros(catalogo)[nombre]
    tercero = crear()
    with _en_el_horario(ticket):
        respuesta = post_json(tk.sesion(identificador), f"{tk.URL}/{ticket.ref}/{ruta}", cuerpo)

    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "ticket", str(ticket.ref))
    assert _acciones(ticket) == []


# --- Historial (HU-08, RF-28, CA-08.1, CA-08.2) ---


@pytest.mark.regla("A-08")
def test_rf28_ambas_partes_ven_el_mismo_precio_final(sesion_maestro, sesion_cliente, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        _registrar(sesion_maestro, ticket, 25000)
        _aceptar(sesion_cliente, ticket, 25000)
        del_cliente = sesion_cliente.get(f"{tk.URL}/{ticket.ref}").json()["ticket"]["precio"]
        del_maestro = sesion_maestro.get(f"{tk.URL}/{ticket.ref}").json()["ticket"]["precio"]
        bandeja_cliente = sesion_cliente.get(tk.URL_CLIENTE).json()["tickets"][0]["precio"]
        bandeja_maestro = sesion_maestro.get(tk.URL_MAESTRO).json()["tickets"][0]["precio"]

    assert del_cliente == del_maestro == bandeja_cliente == bandeja_maestro
    assert (del_cliente["monto"], del_cliente["estado"]) == (25000, "acordado")


def test_ca08_1_sin_estado_la_bandeja_trae_todo_el_historial_con_el_motivo_en_palabras(
    sesion_maestro, sesion_cliente, cliente, maestro
):
    finalizado = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.FINALIZADO)
    cerrado = tk.ticket_directo(cliente, maestro, tk.VIERNES, "08:00", "12:00", estado=EstadoTicket.CERRADO,
                                motivo=MotivoCierre.RECHAZADO_MAESTRO)
    pendiente = tk.ticket_directo(cliente, maestro, tk.JUEVES, "12:00", "16:00")

    del_cliente = {t["ref"]: t for t in sesion_cliente.get(tk.URL_CLIENTE).json()["tickets"]}
    del_maestro = {t["ref"]: t for t in sesion_maestro.get(tk.URL_MAESTRO).json()["tickets"]}

    refs = {str(t.ref) for t in (finalizado, cerrado, pendiente)}
    assert set(del_cliente) == set(del_maestro) == refs
    assert del_cliente[str(finalizado.ref)]["precio"]["monto"] == PUBLICADO
    assert del_cliente[str(finalizado.ref)]["motivo_cierre_texto"] is None
    assert del_cliente[str(cerrado.ref)]["precio"] is None
    assert del_cliente[str(cerrado.ref)]["motivo_cierre_texto"] == "El maestro no puede tomarlo"
    assert del_maestro[str(cerrado.ref)]["motivo_cierre_texto"] == "Lo rechazaste"
    assert del_cliente[str(pendiente.ref)]["precio"] is None


def test_los_avisos_de_precio_hablan_en_lenguaje_del_oficio(sesion_maestro, sesion_cliente, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        _registrar(sesion_maestro, ticket, 25000)
        del_cliente = sesion_cliente.get(tk.URL_AVISOS).json()["avisos"]
        _objetar(sesion_cliente, ticket)
        del_maestro = sesion_maestro.get(tk.URL_AVISOS).json()["avisos"]

    registrado = next(a for a in del_cliente if a["tipo"] == TipoAvisoTicket.PRECIO_REGISTRADO)
    assert "$25.000" in registrado["texto"] and "08:00 a 12:00" in registrado["texto"]
    objetado = next(a for a in del_maestro if a["tipo"] == TipoAvisoTicket.PRECIO_OBJETADO)
    assert "no está de acuerdo" in objetado["texto"]
    for aviso in (registrado, objetado):
        assert "_" not in aviso["texto"]


# --- precio_final_evento de solo inserción (RNF-11; patrón de ADR-010) ---


def _un_evento(sesion_maestro, cliente, maestro):
    ticket = _aceptado(cliente, maestro)
    with _en_el_horario(ticket):
        _registrar(sesion_maestro, ticket, 25000)
    return PrecioFinalEvento.objects.get(ticket_id=ticket.pk)


def test_precio_final_evento_no_se_modifica_ni_se_borra_desde_la_aplicacion(sesion_maestro, cliente, maestro):
    evento = _un_evento(sesion_maestro, cliente, maestro)

    with pytest.raises(OperacionNoPermitida):
        evento.save()
    with pytest.raises(OperacionNoPermitida):
        evento.delete()
    with pytest.raises(OperacionNoPermitida):
        PrecioFinalEvento.objects.filter(pk=evento.pk).update(monto=1)
    with pytest.raises(OperacionNoPermitida):
        PrecioFinalEvento.objects.filter(pk=evento.pk).delete()


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE precio_final_evento SET monto = 1 WHERE id = %s",
        "DELETE FROM precio_final_evento WHERE id = %s",
        "TRUNCATE precio_final_evento",
    ],
)
def test_los_triggers_de_precio_final_evento_rechazan_update_delete_y_truncate(
    sesion_maestro, cliente, maestro, sentencia
):
    evento = _un_evento(sesion_maestro, cliente, maestro)

    with pytest.raises(Exception, match="no admite"), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sentencia, [evento.pk] if "%s" in sentencia else None)

    assert PrecioFinalEvento.objects.filter(pk=evento.pk, monto=25000).exists()


def test_los_check_de_precio_final_evento():
    with pytest.raises(IntegrityError, match="precio_final_evento_accion_valida"), transaction.atomic(), \
            connection.cursor() as cursor:
        cursor.execute("INSERT INTO precio_final_evento (ticket_id, accion, monto, autor_id, fecha) "
                       "VALUES (1, 'borrado', 1000, 1, now())")
