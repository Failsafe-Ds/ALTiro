"""Conversación del ticket aceptado (S5, incremento 4).

HU-07; RF-25; CA-07.1 a CA-07.3, CA-15.2 (conversación); CA-25.1; RNF-07,
RNF-08, RNF-11; ADR-005; ADR-026, E-2; propuesta del S5, §3.1 a §3.4. Datos
ficticios (``tests.tickets_ayudas``). Reloj: miércoles 7 de octubre de 2026,
08:00 en Santiago.
"""
import datetime
import uuid

import pytest
import time_machine
from django.db import IntegrityError, connection, transaction

from autorizacion.models import RegistroAccesoDenegado
from comun.api import MENSAJE_CLAVE_DESCONOCIDA, respuesta_no_encontrado
from comun.solo_insercion import OperacionNoPermitida
from identidad.models import Rol
from mensajeria import conversacion
from mensajeria.models import Mensaje
from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from tests.ayudas import TEL_A, post_json
from tickets.models import AvisoTicket, EstadoTicket, MotivoCierre, TipoAvisoTicket

pytestmark = pytest.mark.django_db

D = datetime.timedelta
AHORA = tk.AHORA
NO_ENCONTRADO = respuesta_no_encontrado().content


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
def sesion_cliente(cliente):
    return tk.sesion(tk.CORREO_CLIENTE)


@pytest.fixture
def sesion_maestro(maestro):
    return tk.sesion(ay.rut(1))


def _ticket(cliente, maestro, estado=EstadoTicket.ACEPTADO, **extra):
    return tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=estado, **extra)


def _url(ticket, despues=None):
    url = f"{tk.URL}/{ticket.ref}/mensajes"
    return f"{url}?despues={despues}" if despues else url


def _enviar(sesion, ticket, texto="Hola, ¿a qué hora llega?", clave=None):
    return post_json(sesion, _url(ticket), {"texto": texto, "clave_envio": str(clave or uuid.uuid4())})


# --- CA-07.1, CA-07.2, CA-15.2: ambas partes escriben y leen en aceptado ---


def test_ca07_1_ambas_partes_escriben_y_leen_la_conversacion(sesion_cliente, sesion_maestro, cliente, maestro):
    ticket = _ticket(cliente, maestro)

    primero = _enviar(sesion_cliente, ticket, "Hola, ¿trae escalera?")
    segundo = _enviar(sesion_maestro, ticket, "Sí, llevo escalera.")

    assert (primero.status_code, segundo.status_code) == (201, 201)
    assert primero.json()["mensaje"]["autor"] == "tu"
    del_cliente = sesion_cliente.get(_url(ticket)).json()
    del_maestro = sesion_maestro.get(_url(ticket)).json()
    assert [(m["autor"], m["texto"]) for m in del_cliente["mensajes"]] == [
        ("tu", "Hola, ¿trae escalera?"), ("maestro", "Sí, llevo escalera.")]
    assert [(m["autor"], m["texto"]) for m in del_maestro["mensajes"]] == [
        ("cliente", "Hola, ¿trae escalera?"), ("tu", "Sí, llevo escalera.")]
    assert del_cliente["puede_escribir"] is True and del_cliente["aviso"] is None
    assert set(Mensaje.objects.values_list("ticket_id", flat=True)) == {ticket.pk}


def test_la_respuesta_no_trae_ids_internos_ni_datos_de_contacto(sesion_cliente, sesion_maestro, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    _enviar(sesion_cliente, ticket, "Hola")

    respuesta = sesion_maestro.get(_url(ticket))

    mensaje = respuesta.json()["mensajes"][0]
    assert set(mensaje) == {"ref", "texto", "enviado_en", "autor"}
    contenido = respuesta.content.decode("utf-8")
    for prohibido in (tk.TELEFONO_CLIENTE, tk.DIRECCION, tk.NOMBRE_CLIENTE, tk.CORREO_CLIENTE, '"autor_id"',
                      '"ticket_id"', '"clave_envio"'):
        assert prohibido not in contenido
    assert respuesta["Cache-Control"] == "no-store"


def test_despues_devuelve_solo_los_mensajes_posteriores(sesion_cliente, sesion_maestro, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    primero = _enviar(sesion_cliente, ticket, "uno").json()["mensaje"]
    _enviar(sesion_maestro, ticket, "dos")
    _enviar(sesion_cliente, ticket, "tres")

    datos = sesion_maestro.get(_url(ticket, primero["ref"])).json()

    assert [m["texto"] for m in datos["mensajes"]] == ["dos", "tres"]


def test_despues_de_otra_conversacion_o_invalido_da_400_sin_revelar_nada(sesion_cliente, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    otro = tk.ticket_directo(cliente, maestro, tk.VIERNES, "08:00", "12:00", estado=EstadoTicket.ACEPTADO)
    ajeno = _enviar(sesion_cliente, otro, "en otro pedido").json()["mensaje"]["ref"]

    for valor in (ajeno, str(uuid.uuid4()), "no-es-ref"):
        respuesta = sesion_cliente.get(_url(ticket, valor))
        assert respuesta.status_code == 400 and "despues" in respuesta.json()["errores"]
    desconocido = sesion_cliente.get(f"{_url(ticket)}?pagina=1")
    assert desconocido.status_code == 400 and desconocido.json()["mensaje"] == MENSAJE_CLAVE_DESCONOCIDA


def test_el_otro_recibe_el_aviso_mensaje_nuevo_que_se_reactiva(sesion_cliente, sesion_maestro, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    _enviar(sesion_cliente, ticket, "uno")
    avisos = sesion_maestro.get(tk.URL_AVISOS).json()["avisos"]
    aviso = next(a for a in avisos if a["tipo"] == TipoAvisoTicket.MENSAJE_NUEVO)
    assert aviso["enlace"] == f"/conversacion.html?ticket={ticket.ref}"
    assert "mensaje nuevo" in aviso["texto"] and "_" not in aviso["texto"]
    post_json(sesion_maestro, tk.URL_VISTOS, {"avisos": [aviso["ref"]]})

    _enviar(sesion_cliente, ticket, "dos")

    filas = AvisoTicket.objects.filter(ticket=ticket, tipo=TipoAvisoTicket.MENSAJE_NUEVO)
    assert [(f.destinatario_id, f.visto_en) for f in filas] == [(maestro.pk, None)]


# --- Estados (ADR-026, E-2.2; P-31; CA-07.3) ---


@pytest.mark.regla("A-09")
def test_en_un_pedido_pendiente_no_hay_conversacion(sesion_cliente, sesion_maestro, cliente, maestro):
    ticket = _ticket(cliente, maestro, EstadoTicket.PENDIENTE)

    for sesion in (sesion_cliente, sesion_maestro):
        envio = _enviar(sesion, ticket)
        lectura = sesion.get(_url(ticket))
        assert envio.status_code == lectura.status_code == 409
        assert "cuando el maestro acepta" in envio.json()["mensaje"]
    assert not Mensaje.objects.exists()


@pytest.mark.regla("A-10")
@pytest.mark.parametrize(
    ("estado", "motivo", "texto"),
    [(EstadoTicket.FINALIZADO, None, "ya terminó"), (EstadoTicket.CERRADO, MotivoCierre.CANCELADO_CLIENTE, "no hubo")],
)
def test_en_finalizado_o_cerrado_no_se_escribe(sesion_cliente, sesion_maestro, cliente, maestro, estado, motivo,
                                               texto):
    ticket = _ticket(cliente, maestro, estado, motivo=motivo)

    for sesion in (sesion_cliente, sesion_maestro):
        respuesta = _enviar(sesion, ticket)
        assert respuesta.status_code == 409 and texto in respuesta.json()["mensaje"]
    assert not Mensaje.objects.exists()
    assert not AvisoTicket.objects.filter(tipo=TipoAvisoTicket.MENSAJE_NUEVO).exists()


@pytest.mark.regla("A-11")
def test_ca07_3_en_finalizado_la_conversacion_se_lee_con_el_aviso_escrito(sesion_cliente, sesion_maestro, cliente,
                                                                         maestro):
    ticket = _ticket(cliente, maestro)
    _enviar(sesion_cliente, ticket, "¿Llega a las 8?")
    _enviar(sesion_maestro, ticket, "Sí.")
    ticket.estado = EstadoTicket.FINALIZADO
    ticket.finalizado_en = AHORA
    ticket.monto_final, ticket.monto_final_en, ticket.monto_final_autor_id = ticket.monto_publicado, AHORA, maestro.pk
    ticket.precio_aceptado_en = AHORA
    ticket.save()

    for sesion in (sesion_cliente, sesion_maestro):
        datos = sesion.get(_url(ticket)).json()
        assert [m["texto"] for m in datos["mensajes"]] == ["¿Llega a las 8?", "Sí."]
        assert datos["puede_escribir"] is False and "ya no enviar" in datos["aviso"]


@pytest.mark.regla("A-11")
def test_ca07_3_en_cerrado_lista_vacia_y_no_hubo_conversacion(sesion_cliente, sesion_maestro, cliente, maestro):
    ticket = _ticket(cliente, maestro, EstadoTicket.CERRADO, motivo=MotivoCierre.RECHAZADO_MAESTRO)

    for sesion in (sesion_cliente, sesion_maestro):
        respuesta = sesion.get(_url(ticket))
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["mensajes"] == [] and datos["puede_escribir"] is False
        assert datos["aviso"].startswith("No hubo conversación")


# --- Acceso (CA-25.1, R-05; ADR-026, E-2.3) ---


def _terceros(catalogo):
    return {
        "otro_cliente": (lambda: tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A),
                         "otro.cliente@example.com"),
        "otro_maestro": (lambda: tk.maestro_con_agenda(catalogo, n=2), ay.rut(2)),
        "curatoria": (lambda: tk.administrativo(Rol.CURATORIA, "cura@example.com"), "cura@example.com"),
        "moderacion": (lambda: tk.administrativo(Rol.MODERACION, "moderacion@example.com"), "moderacion@example.com"),
        "control_gestion": (lambda: tk.administrativo(Rol.CONTROL_GESTION, "control@example.com"),
                            "control@example.com"),
    }


@pytest.mark.terceros("ticket_mensajes")
@pytest.mark.regla("A-12")
@pytest.mark.parametrize("metodo", ["GET", "POST"])
@pytest.mark.parametrize("nombre", ["otro_cliente", "otro_maestro", "curatoria", "moderacion", "control_gestion"])
def test_ca25_1_un_tercero_recibe_el_404_identico_con_registro(sesion_cliente, cliente, maestro, catalogo, metodo,
                                                              nombre):
    ticket = _ticket(cliente, maestro)
    _enviar(sesion_cliente, ticket, "Solo para las partes")
    crear, identificador = _terceros(catalogo)[nombre]
    tercero = crear()
    sesion = tk.sesion(identificador)

    respuesta = sesion.get(_url(ticket)) if metodo == "GET" else _enviar(sesion, ticket, "intruso")

    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "ticket", str(ticket.ref))
    assert Mensaje.objects.count() == 1


def test_un_ticket_inexistente_da_el_mismo_404(sesion_cliente):
    respuesta = sesion_cliente.get(f"{tk.URL}/{uuid.uuid4()}/mensajes")
    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO


def test_sin_sesion_401_y_metodos_no_permitidos_405(client, sesion_cliente, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    assert client.get(_url(ticket)).status_code == 401
    assert sesion_cliente.delete(_url(ticket)).status_code == 405


# --- Envío (ADR-026, E-2.4) ---


@pytest.mark.regla("A-13")
def test_reenviar_con_la_misma_clave_devuelve_el_mismo_mensaje(sesion_cliente, sesion_maestro, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    clave = uuid.uuid4()

    primero = _enviar(sesion_cliente, ticket, "Hola", clave)
    segundo = _enviar(sesion_cliente, ticket, "Hola", clave)

    assert (primero.status_code, segundo.status_code) == (201, 200)
    assert primero.json() == segundo.json()
    assert Mensaje.objects.count() == 1
    # La misma clave de la otra parte es otro mensaje (único por ticket, autor y clave).
    assert _enviar(sesion_maestro, ticket, "Hola", clave).status_code == 201
    assert Mensaje.objects.count() == 2


@pytest.mark.regla("A-13")
def test_el_unico_de_la_base_impide_duplicar_la_clave(sesion_cliente, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    clave = uuid.uuid4()
    _enviar(sesion_cliente, ticket, "Hola", clave)

    with pytest.raises(IntegrityError, match="mensaje_envio_unico"), transaction.atomic():
        Mensaje.objects.create(ticket_id=ticket.pk, autor_id=cliente.pk, texto="otra", enviado_en=AHORA,
                               clave_envio=clave)


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({"texto": "", "clave_envio": str(uuid.uuid4())}, "texto"),
        ({"texto": "   \n ", "clave_envio": str(uuid.uuid4())}, "texto"),
        ({"texto": "x" * 1001, "clave_envio": str(uuid.uuid4())}, "texto"),
        ({"texto": 5, "clave_envio": str(uuid.uuid4())}, "texto"),
        ({"texto": "Hola"}, "clave_envio"),
        ({"texto": "Hola", "clave_envio": "abc"}, "clave_envio"),
    ],
)
def test_validacion_del_envio(sesion_cliente, cliente, maestro, cuerpo, campo):
    ticket = _ticket(cliente, maestro)
    respuesta = post_json(sesion_cliente, _url(ticket), cuerpo)
    assert respuesta.status_code == 400 and campo in respuesta.json()["errores"]
    assert not Mensaje.objects.exists()


def test_mil_caracteres_se_aceptan_y_una_clave_desconocida_no(sesion_cliente, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    assert _enviar(sesion_cliente, ticket, "x" * 1000).status_code == 201
    extra = post_json(sesion_cliente, _url(ticket), {"texto": "Hola", "clave_envio": str(uuid.uuid4()), "autor": 1})
    assert extra.status_code == 400 and extra.json()["mensaje"] == MENSAJE_CLAVE_DESCONOCIDA


def test_el_check_de_texto_rechaza_un_mensaje_en_blanco():
    with pytest.raises(IntegrityError, match="mensaje_texto_valido"), transaction.atomic(), \
            connection.cursor() as cursor:
        cursor.execute("INSERT INTO mensaje (ref, ticket_id, autor_id, texto, enviado_en, clave_envio) "
                       "VALUES (gen_random_uuid(), 1, 1, '   ', now(), gen_random_uuid())")


# --- Solo inserción (RNF-11; patrón de ADR-010) ---


def _un_mensaje(sesion_cliente, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    _enviar(sesion_cliente, ticket, "Hola")
    return Mensaje.objects.get()


@pytest.mark.regla("A-14")
def test_el_mensaje_no_se_modifica_ni_se_borra_desde_la_aplicacion(sesion_cliente, cliente, maestro):
    mensaje = _un_mensaje(sesion_cliente, cliente, maestro)

    with pytest.raises(OperacionNoPermitida):
        mensaje.save()
    with pytest.raises(OperacionNoPermitida):
        mensaje.delete()
    with pytest.raises(OperacionNoPermitida):
        Mensaje.objects.filter(pk=mensaje.pk).update(texto="otro")
    with pytest.raises(OperacionNoPermitida):
        Mensaje.objects.filter(pk=mensaje.pk).delete()


@pytest.mark.regla("A-14")
@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE mensaje SET texto = 'otro' WHERE id = %s",
        "DELETE FROM mensaje WHERE id = %s",
        "TRUNCATE mensaje",
    ],
)
def test_los_triggers_de_mensaje_rechazan_update_delete_y_truncate(sesion_cliente, cliente, maestro, sentencia):
    mensaje = _un_mensaje(sesion_cliente, cliente, maestro)

    with pytest.raises(Exception, match="no admite"), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sentencia, [mensaje.pk] if "%s" in sentencia else None)

    assert Mensaje.objects.filter(pk=mensaje.pk, texto="Hola").exists()


# --- Sesión (ADR-005; ADR-026, E-2.5) ---


@pytest.mark.regla("A-15")
def test_la_consulta_periodica_no_renueva_la_sesion(sesion_cliente, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    primero = _enviar(sesion_cliente, ticket, "Hola").json()["mensaje"]["ref"]

    with time_machine.travel(AHORA + D(minutes=20), tick=False):
        assert sesion_cliente.get(_url(ticket, primero)).status_code == 200
        assert sesion_cliente.get(_url(ticket)).status_code == 200
    with time_machine.travel(AHORA + D(minutes=31), tick=False):
        assert sesion_cliente.get(_url(ticket, primero)).status_code == 401


def test_enviar_si_renueva_la_sesion(sesion_cliente, cliente, maestro):
    ticket = _ticket(cliente, maestro)

    with time_machine.travel(AHORA + D(minutes=20), tick=False):
        assert _enviar(sesion_cliente, ticket, "Hola").status_code == 201
    with time_machine.travel(AHORA + D(minutes=31), tick=False):
        assert sesion_cliente.get(_url(ticket)).status_code == 200


def test_el_texto_de_las_reglas_no_usa_jerga():
    for texto in (conversacion.MENSAJE_PENDIENTE, conversacion.MENSAJE_FINALIZADO, conversacion.MENSAJE_CERRADO,
                  conversacion.AVISO_FINALIZADO, conversacion.AVISO_CERRADO):
        assert "_" not in texto and "ticket" not in texto.lower()
