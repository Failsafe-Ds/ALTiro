"""Creación y lectura del ticket (S4, incremento 4): RF-15 a RF-18, HU-06, HU-15 (lectura), CA-06.x, CA-15.1,
CA-25.1, RNF-07, RNF-08, ADR-013 E-9, ADR-023 y ADR-024.

Reloj fijo con time-machine: miércoles 7 de octubre de 2026, 08:00 en Santiago
(``tickets_ayudas``). Los estados aceptado, finalizado y cerrado se crean por
ORM (``ticket_directo``): sus transiciones son de los incrementos 5 y 6.
Datos ficticios.
"""
import datetime
import json

import pytest
import time_machine
from django.db import IntegrityError, connection, transaction
from django.test import Client

from autorizacion.middleware import MENSAJE_SIN_ROL
from autorizacion.models import RegistroAccesoDenegado
from comun.api import MENSAJE_CLAVE_DESCONOCIDA, respuesta_no_encontrado
from comun.solo_insercion import OperacionNoPermitida
from expediente.models import EstadoExpediente, Expediente
from identidad import servicios as servicios_identidad
from identidad.models import Rol
from perfil import ocupacion, ocurrencias
from perfil.models import PerfilPublico, ServicioMaestro
from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from tests.ayudas import CONTRASENA, TEL_A, TEXTO_PROHIBIDO, iniciar_sesion, post_json
from tests.privacidad import assert_campos_ausentes
from tickets import servicios
from tickets.models import AvisoTicket, EstadoTicket, MotivoCierre, Ticket, TicketEvento, TipoAvisoTicket

pytestmark = pytest.mark.django_db

D = datetime.timedelta
NO_ENCONTRADO = respuesta_no_encontrado().content
AHORA = tk.AHORA


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


def _crear(sesion_cliente, maestro, catalogo, **cambios):
    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, **cambios))
    assert respuesta.status_code == 201, respuesta.content
    return respuesta.json()["ticket"]


def _crear_en_servicio(cliente, maestro, catalogo, ahora=AHORA, **cambios):
    return servicios.crear_ticket(cliente, tk.pedido(maestro, catalogo, **cambios), ahora=ahora)


# --- Creación (RF-15, RF-18, CA-06.1) ---


def test_rf15_crea_el_ticket_pendiente_con_las_copias_del_servicio_y_del_bloque(
    sesion_cliente, cliente, maestro, catalogo
):
    datos = _crear(sesion_cliente, maestro, catalogo)

    ticket = Ticket.objects.get()
    servicio_maestro = ServicioMaestro.objects.get(maestro_id=maestro.pk)
    assert ticket.estado == EstadoTicket.PENDIENTE and ticket.motivo_cierre is None
    assert (ticket.cliente_id, ticket.perfil_maestro_id) == (cliente.pk, maestro.pk)
    assert (ticket.modalidad, ticket.monto_publicado) == (servicio_maestro.modalidad, servicio_maestro.monto)
    assert (ticket.fecha, ticket.inicio_min, ticket.fin_min) == (tk.JUEVES, 480, 720)
    assert ticket.inicio_en == ocurrencias.instante(tk.JUEVES, 480)
    assert ticket.fin_en == ocurrencias.instante(tk.JUEVES, 720)
    assert ticket.enviado_en == AHORA and ticket.materiales is True
    assert (ticket.direccion, ticket.comuna_id) == (tk.DIRECCION, ay.CONCEPCION)
    # La respuesta es la del cliente: su dirección (CA-06.3), el bloque y el maestro, sin ids internos.
    assert datos["ref"] == str(ticket.ref) and datos["numero"] == ticket.id
    assert datos["bloque"] == {"fecha": tk.JUEVES.isoformat(), "inicio": "08:00", "fin": "12:00"}
    assert datos["maestro"] == {"ref": ay.ref(maestro), "nombre": "Maestro Prueba 001"}
    assert datos["direccion"] == tk.DIRECCION and datos["estado"] == "pendiente"
    assert "contacto" not in datos


def test_rf15_el_ticket_conserva_modalidad_y_monto_aunque_el_maestro_cambie_su_precio(
    sesion_cliente, maestro, catalogo
):
    datos = _crear(sesion_cliente, maestro, catalogo)
    ServicioMaestro.objects.filter(maestro_id=maestro.pk).update(monto=99000)

    leido = sesion_cliente.get(f"{tk.URL}/{datos['ref']}").json()["ticket"]

    assert leido["monto_publicado"] == 20001 and leido["modalidad"] == "por_trabajo"
    assert Ticket.objects.get().monto_publicado == 20001


def test_rf18_el_evento_inicial_y_el_aviso_al_maestro_nacen_con_el_ticket(sesion_cliente, cliente, maestro, catalogo):
    _crear(sesion_cliente, maestro, catalogo)

    ticket = Ticket.objects.get()
    evento = TicketEvento.objects.get(ticket_id=ticket.pk)
    assert (evento.estado_anterior, evento.estado_nuevo, evento.motivo) == (None, "pendiente", None)
    assert (evento.autor_tipo, evento.autor_id, evento.fecha) == ("usuario", cliente.pk, AHORA)
    aviso = AvisoTicket.objects.get()
    assert (aviso.ticket_id, aviso.destinatario_id, aviso.tipo) == (ticket.pk, maestro.pk, "ticket_nuevo")
    assert aviso.visto_en is None


def test_rf18_si_falla_el_aviso_no_queda_ni_el_ticket_ni_el_evento(cliente, maestro, catalogo, monkeypatch):
    def fallar(*args, **kwargs):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(AvisoTicket.objects, "create", fallar)

    with pytest.raises(RuntimeError):
        _crear_en_servicio(cliente, maestro, catalogo)

    assert not Ticket.objects.exists()
    assert not TicketEvento.objects.filter(autor_id=cliente.pk).exists()


def test_materiales_false_es_una_respuesta_valida(sesion_cliente, maestro, catalogo):
    datos = _crear(sesion_cliente, maestro, catalogo, materiales=False)

    assert datos["materiales"] is False


# --- Datos completos (CA-06.4) ---


@pytest.mark.parametrize(
    ("cambios", "campo", "mensaje"),
    [
        ({"descripcion": None}, "descripcion", servicios.MENSAJE_DESCRIPCION_FALTA),
        ({"descripcion": "   "}, "descripcion", servicios.MENSAJE_DESCRIPCION_FALTA),
        ({"direccion": None}, "direccion", servicios.MENSAJE_DIRECCION_FALTA),
        ({"direccion": ""}, "direccion", servicios.MENSAJE_DIRECCION_FALTA),
        ({"materiales": None}, "materiales", servicios.MENSAJE_MATERIALES),
        ({"materiales": "true"}, "materiales", servicios.MENSAJE_MATERIALES),
        ({"materiales": 1}, "materiales", servicios.MENSAJE_MATERIALES),
        ({"direccion": "x" * 201}, "direccion", servicios.MENSAJE_DIRECCION_LARGA.format(largo="200")),
        ({"descripcion": "x" * 1001}, "descripcion", servicios.MENSAJE_DESCRIPCION_LARGA.format(largo="1.000")),
        ({"direccion": "Calle 1\nCalle 2"}, "direccion", "Este dato tiene caracteres que no se pueden usar. Escríbelo de nuevo."),
        ({"fecha": None}, "fecha", servicios.MENSAJE_FECHA_FALTA),
        ({"fecha": "2026-02-30"}, "fecha", servicios.MENSAJE_FECHA_INVALIDA),
        ({"inicio": "8:00"}, "inicio", "Elige una hora en formato de 24 horas, entre 00:00 y 24:00 (por ejemplo, 08:00 o 17:30)."),
        ({"fin": "08:00"}, "fin", servicios.MENSAJE_FIN_NO_POSTERIOR),
        ({"comuna": None}, "comuna", servicios.MENSAJE_COMUNA_FALTA),
        ({"comuna": "999999"}, "comuna", servicios.MENSAJE_COMUNA_INVALIDA),
        ({"servicio": "no-es-una-ref"}, "servicio", servicios.MENSAJE_SERVICIO),
        ({"maestro": None}, "maestro", servicios.MENSAJE_MAESTRO),
    ],
)
def test_ca06_4_el_servidor_impide_el_envio_incompleto_y_dice_que_falta(
    sesion_cliente, maestro, catalogo, cambios, campo, mensaje
):
    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, **cambios))

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"][campo] == mensaje
    assert not Ticket.objects.exists() and not AvisoTicket.objects.exists()


def test_ca06_4_sin_materiales_ni_descripcion_se_informan_los_dos_campos(sesion_cliente, maestro, catalogo):
    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, materiales=None, descripcion=None))

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) == {"materiales", "descripcion"}


def test_clave_desconocida_400_general_y_campo_no_permitido_400_en_el_campo(sesion_cliente, maestro, catalogo):
    desconocida = tk.enviar(sesion_cliente, {**tk.pedido(maestro, catalogo), "precio": 1})
    no_permitido = tk.enviar(sesion_cliente, {**tk.pedido(maestro, catalogo), "monto": 1})

    assert desconocida.status_code == 400 and desconocida.json() == {"mensaje": MENSAJE_CLAVE_DESCONOCIDA, "errores": {}}
    assert no_permitido.status_code == 400 and set(no_permitido.json()["errores"]) == {"monto"}
    assert not Ticket.objects.exists()


# --- Horario (RF-16, CA-06.2; ADR-022, punto 1) ---


@pytest.mark.regla("F-09")
def test_rf16_un_horario_que_empieza_en_exactamente_4_horas_se_rechaza(sesion_cliente, maestro, catalogo):
    # Miércoles 12:00 con el reloj a las 08:00: exactamente 4 horas.
    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, fecha=tk.HOY.isoformat(), inicio="12:00",
                                                    fin="16:00"))

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == servicios.MENSAJE_HORARIO_PRONTO
    # CA-06.2: se ofrecen los horarios libres vigentes, sin el que ya no se puede pedir.
    bloques = respuesta.json()["bloques"]
    assert {"fecha": tk.JUEVES.isoformat(), "inicio": "08:00", "fin": "12:00"} in bloques
    assert not any(b["fecha"] == tk.HOY.isoformat() for b in bloques)
    assert not Ticket.objects.exists()


@pytest.mark.regla("F-09")
def test_rf16_un_segundo_antes_del_borde_si_se_puede_pedir(cliente, maestro, catalogo):
    ahora = AHORA - D(seconds=1)

    ticket, creado = _crear_en_servicio(cliente, maestro, catalogo, ahora=ahora, fecha=tk.HOY.isoformat(),
                                        inicio="12:00", fin="16:00")

    assert creado and ticket.inicio_en - ticket.enviado_en == D(hours=4, seconds=1)
    assert ticket.vence_en == ticket.inicio_en - D(hours=4)


@pytest.mark.regla("C-08")
@pytest.mark.parametrize(
    ("fecha", "inicio", "fin", "horas_hasta_inicio", "vence_desde_ahora"),
    [
        (tk.JUEVES, "08:00", "12:00", 24, D(hours=20)),  # inicio - 4 h manda
        (tk.JUEVES, "12:00", "16:00", 28, D(hours=24)),  # 28 h: los dos términos coinciden
        (tk.VIERNES, "08:00", "12:00", 48, D(hours=24)),  # enviado + 24 h manda
    ],
)
def test_vence_en_es_el_menor_entre_24_horas_desde_el_envio_y_4_horas_antes_del_inicio(
    sesion_cliente, maestro, catalogo, fecha, inicio, fin, horas_hasta_inicio, vence_desde_ahora
):
    datos = _crear(sesion_cliente, maestro, catalogo, fecha=fecha.isoformat(), inicio=inicio, fin=fin)

    ticket = Ticket.objects.get()
    assert ticket.inicio_en - AHORA == D(hours=horas_hasta_inicio)
    assert ticket.vence_en == AHORA + vence_desde_ahora
    assert ticket.vence_en == min(AHORA + D(hours=24), ticket.inicio_en - D(hours=4))
    if horas_hasta_inicio == 28:
        assert ticket.vence_en == AHORA + D(hours=24) == ticket.inicio_en - D(hours=4)
    assert datetime.datetime.fromisoformat(datos["vence_en"]) == ticket.vence_en


@pytest.mark.regla("F-10")
def test_ca06_2_un_horario_ocupado_por_un_ticket_aceptado_se_rechaza_con_los_horarios_libres(
    sesion_cliente, maestro, catalogo
):
    otro = tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A)
    tk.ticket_directo(otro, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.ACEPTADO)

    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo))

    assert respuesta.status_code == 409
    datos = respuesta.json()
    assert datos["mensaje"] == servicios.MENSAJE_HORARIO_OCUPADO and datos["errores"] == {}
    assert {"fecha": tk.JUEVES.isoformat(), "inicio": "08:00", "fin": "12:00"} not in datos["bloques"]
    assert {"fecha": tk.JUEVES.isoformat(), "inicio": "12:00", "fin": "16:00"} in datos["bloques"]
    assert Ticket.objects.count() == 1


@pytest.mark.regla("F-10")
@pytest.mark.parametrize("estado", [EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO])
def test_ca14_3_la_busqueda_y_la_ficha_ven_ocupado_el_horario_de_un_ticket_aceptado(catalogo, estado):
    ocupado = ay.maestro(1, catalogo, bloques=[(4, "08:00", "12:00")])
    libre = ay.maestro(2, catalogo, bloques=[(4, "08:00", "12:00")])
    otro = tk.cliente()
    tk.ticket_directo(otro, ocupado, tk.JUEVES, "08:00", "12:00", estado=estado)

    busqueda = Client().get(ay.URL, {"oficio": "pintura", "comuna": str(ay.CONCEPCION),
                                     "fecha": tk.JUEVES.isoformat(), "inicio": "09:00", "fin": "10:00"})
    ficha = Client().get(f"/api/maestros/publicos/{ay.ref(ocupado)}").json()["maestro"]["bloques"]

    assert ay.refs(busqueda) == [ay.ref(libre)]
    del_jueves = [b for b in ficha if b["fecha"] == tk.JUEVES.isoformat()]
    assert [b["estado"] for b in del_jueves] == ["ocupado"]
    assert set(del_jueves[0]) == {"fecha", "inicio", "fin", "ref", "estado"}


@pytest.mark.parametrize("estado", [EstadoTicket.PENDIENTE, EstadoTicket.CERRADO])
def test_rf20_un_ticket_pendiente_o_cerrado_no_ocupa_el_horario(catalogo, maestro, estado):
    otro = tk.cliente()
    tk.ticket_directo(otro, maestro, tk.JUEVES, "08:00", "12:00", estado=estado)

    assert ocupacion.rangos_ocupados([maestro.pk], AHORA, AHORA + D(days=14)) == {}


def test_rangos_ocupados_entrega_los_cruces_de_aceptados_y_finalizados_en_una_consulta(
    catalogo, maestro, django_assert_num_queries
):
    otro = tk.cliente()
    aceptado = tk.ticket_directo(otro, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.ACEPTADO)
    finalizado = tk.ticket_directo(otro, maestro, tk.VIERNES, "08:00", "12:00", estado=EstadoTicket.FINALIZADO)

    with django_assert_num_queries(1):
        rangos = ocupacion.rangos_ocupados([maestro.pk, maestro.pk + 1000], AHORA, AHORA + D(days=14))

    assert rangos == {maestro.pk: [(aceptado.inicio_en, aceptado.fin_en), (finalizado.inicio_en, finalizado.fin_en)]}
    # Fuera de la ventana pedida no aparece.
    assert ocupacion.rangos_ocupados([maestro.pk], finalizado.fin_en, finalizado.fin_en + D(days=1)) == {}


@pytest.mark.parametrize(
    ("fecha", "inicio", "fin"),
    [
        (tk.JUEVES, "09:00", "11:00"),  # dentro de un horario, pero no es el horario completo
        (tk.JUEVES, "16:00", "18:00"),  # no está en la agenda
        (tk.HOY + D(days=5), "08:00", "12:00"),  # lunes: ese día no trabaja
    ],
)
def test_ca06_2_un_horario_que_no_esta_en_la_agenda_se_rechaza(sesion_cliente, maestro, catalogo, fecha, inicio, fin):
    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, fecha=fecha.isoformat(), inicio=inicio, fin=fin))

    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == servicios.MENSAJE_HORARIO_NO_EXISTE
    assert not Ticket.objects.exists()


@pytest.mark.parametrize("dias", [-1, 14, 30])
def test_la_fecha_debe_estar_en_el_horizonte_de_14_dias(sesion_cliente, maestro, catalogo, dias):
    fecha = (tk.HOY + D(days=dias)).isoformat()

    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, fecha=fecha))

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"]["fecha"] == servicios.MENSAJE_FECHA_FUERA.format(dias=13)


def test_un_horario_retirado_de_la_agenda_ya_no_se_puede_pedir(sesion_cliente, maestro, catalogo):
    from perfil.models import Disponibilidad

    Disponibilidad.objects.filter(maestro_id=maestro.pk, dia_semana=4, inicio_min=480).update(retirado_en=AHORA)

    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo))

    assert respuesta.status_code == 409 and respuesta.json()["mensaje"] == servicios.MENSAJE_HORARIO_NO_EXISTE


# --- Maestro publicado, servicio visible y comuna (ADR-023, punto 3) ---


def test_un_maestro_no_publicado_y_uno_inexistente_reciben_el_mismo_mensaje(sesion_cliente, maestro, catalogo):
    import uuid

    PerfilPublico.objects.filter(perfil_maestro_id=maestro.pk).update(foto=None, foto_actualizada_en=None)

    sin_foto = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo))
    inexistente = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, maestro=str(uuid.uuid4())))

    assert sin_foto.status_code == inexistente.status_code == 400
    assert sin_foto.json() == inexistente.json()
    assert sin_foto.json()["errores"] == {"maestro": servicios.MENSAJE_MAESTRO}
    assert not Ticket.objects.exists()


@pytest.mark.parametrize("estado", [EstadoExpediente.SUSPENDIDO, EstadoExpediente.EN_REVISION])
def test_un_maestro_suspendido_o_sin_aprobar_no_recibe_pedidos(sesion_cliente, maestro, catalogo, estado):
    Expediente.objects.filter(perfil_maestro_id=maestro.pk).update(estado=estado)

    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo))

    assert respuesta.status_code == 400 and respuesta.json()["errores"] == {"maestro": servicios.MENSAJE_MAESTRO}


def test_un_servicio_retirado_o_que_no_ofrece_no_se_puede_pedir(sesion_cliente, catalogo):
    maestro = tk.maestro_con_agenda(catalogo, servicios=("pintura", "gasfiteria"))
    ServicioMaestro.objects.filter(maestro_id=maestro.pk, servicio=catalogo["pintura"]).update(retirado_en=AHORA)

    retirado = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo))
    no_ofrecido = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, servicio=str(catalogo["electricidad"].ref)))

    for respuesta in (retirado, no_ofrecido):
        assert respuesta.status_code == 400
        assert respuesta.json()["errores"] == {"servicio": servicios.MENSAJE_SERVICIO}
    assert not Ticket.objects.exists()


def test_la_comuna_debe_estar_en_la_cobertura_del_maestro(sesion_cliente, maestro, catalogo):
    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, comuna=str(ay.LEBU)))

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"comuna": servicios.MENSAJE_COMUNA_FUERA}
    # Una comuna secundaria de su cobertura sí sirve.
    assert tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, comuna=str(ay.CORONEL))).status_code == 201


# --- Auto-envío (ADR-013, E-9) ---


def _maestro_que_tambien_es_cliente(maestro):
    return servicios_identidad.agregar_perfil_cliente(maestro, comuna="8101", correo="maestro.cliente@example.com")


@pytest.mark.regla("A-04")
def test_e9_nadie_puede_pedirse_un_trabajo_a_si_mismo(maestro, catalogo):
    _maestro_que_tambien_es_cliente(maestro)
    sesion = tk.sesion("maestro.cliente@example.com")

    respuesta = tk.enviar(sesion, tk.pedido(maestro, catalogo))

    assert respuesta.status_code == 400
    assert respuesta.json() == {
        "mensaje": "No puedes pedirte un trabajo a ti mismo.",
        "errores": {"maestro": "No puedes pedirte un trabajo a ti mismo."},
    }
    assert not Ticket.objects.exists() and not AvisoTicket.objects.exists()


@pytest.mark.regla("A-04")
def test_e9_el_check_de_la_base_impide_cliente_igual_a_maestro(maestro, catalogo):
    _maestro_que_tambien_es_cliente(maestro)

    with pytest.raises(IntegrityError, match="ticket_cliente_no_es_maestro"), transaction.atomic():
        tk.ticket_directo(maestro, maestro, tk.JUEVES, "08:00", "12:00")


# --- Pendiente duplicado (D-10) ---


def test_d10_repetir_el_mismo_pedido_devuelve_el_mismo_ticket_sin_duplicar(sesion_cliente, maestro, catalogo):
    primero = _crear(sesion_cliente, maestro, catalogo)

    repetido = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, descripcion="Otra descripción"))

    assert repetido.status_code == 200
    assert repetido.json()["ticket"]["ref"] == primero["ref"]
    assert repetido.json()["ticket"]["descripcion"] == primero["descripcion"]
    assert Ticket.objects.count() == 1 and AvisoTicket.objects.count() == 1
    assert TicketEvento.objects.filter(ticket_id=Ticket.objects.get().pk).count() == 1


def test_d10_otro_cliente_si_puede_pedir_el_mismo_horario_pendiente(sesion_cliente, maestro, catalogo):
    _crear(sesion_cliente, maestro, catalogo)
    tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A)

    respuesta = tk.enviar(tk.sesion("otro.cliente@example.com"), tk.pedido(maestro, catalogo))

    assert respuesta.status_code == 201
    assert Ticket.objects.filter(estado=EstadoTicket.PENDIENTE).count() == 2


def test_d10_un_pendiente_repetido_que_ya_vencio_responde_409(sesion_cliente, cliente, maestro, catalogo):
    viejo = tk.ticket_directo(cliente, maestro, tk.VIERNES, "08:00", "12:00", enviado_en=AHORA - D(hours=25))
    assert viejo.vence_en == AHORA - D(hours=1)

    respuesta = tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, fecha=tk.VIERNES.isoformat()))

    assert respuesta.status_code == 409
    assert respuesta.json() == {"mensaje": servicios.MENSAJE_PENDIENTE_VENCIDO, "errores": {}}
    assert Ticket.objects.count() == 1


def test_d10_el_unico_parcial_impide_dos_pendientes_del_mismo_cliente_maestro_e_inicio(cliente, maestro, catalogo):
    tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00")

    with pytest.raises(IntegrityError, match="ticket_pendiente_unico"), transaction.atomic():
        tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00")
    # Cerrado el primero, se puede volver a pedir.
    tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.CERRADO)


def test_d9_el_unico_parcial_impide_dos_aceptados_del_mismo_maestro_e_inicio(cliente, maestro, catalogo):
    otro = tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A)
    tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.ACEPTADO)

    with pytest.raises(IntegrityError, match="ticket_bloque_ocupado_unico"), transaction.atomic():
        tk.ticket_directo(otro, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.FINALIZADO)


# --- Solo el rol cliente crea tickets (ADR-023) ---


@pytest.mark.regla("A-05")
@pytest.mark.parametrize(
    "rol", ["maestro", Rol.CURATORIA, Rol.COMERCIAL, Rol.MODERACION, Rol.CONTROL_GESTION]
)
def test_solo_el_rol_cliente_crea_tickets(maestro, catalogo, rol):
    if rol == "maestro":
        otro = tk.maestro_con_agenda(catalogo, n=2)
        identificador = ay.rut(2)
    else:
        otro = tk.administrativo(rol, "admin@example.com")
        identificador = "admin@example.com"

    respuesta = tk.enviar(tk.sesion(identificador), tk.pedido(maestro, catalogo))

    assert respuesta.status_code == 403
    assert respuesta.json() == {"mensaje": MENSAJE_SIN_ROL, "errores": {}}
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.recurso) == (otro.pk, "ruta", "POST api/tickets")
    assert not Ticket.objects.exists()


def test_sin_sesion_401_sin_crear_nada(maestro, catalogo):
    respuesta = tk.enviar(Client(), tk.pedido(maestro, catalogo))

    assert respuesta.status_code == 401
    assert not Ticket.objects.exists() and not RegistroAccesoDenegado.objects.exists()


# --- Privacidad (RF-17, RNF-08; D-13) sobre el JSON crudo del servidor ---

CAMPOS_PRIVADOS_PENDIENTE = {"direccion", "telefono", "contacto", "correo", "cliente", "rut"}


def _valores_privados(cliente):
    return [tk.DIRECCION, "Pasaje Ficticio", tk.NOMBRE_CLIENTE, tk.TELEFONO_CLIENTE, "910000002",
            tk.CORREO_CLIENTE, str(cliente.pk)]


@pytest.mark.regla("A-03")
def test_rf17_el_maestro_no_recibe_direccion_telefono_ni_nombre_del_cliente_mientras_esta_pendiente(
    sesion_cliente, sesion_maestro, cliente, maestro, catalogo
):
    datos = _crear(sesion_cliente, maestro, catalogo)

    detalle = sesion_maestro.get(f"{tk.URL}/{datos['ref']}")
    lista = sesion_maestro.get(tk.URL_MAESTRO)
    avisos = sesion_maestro.get(tk.URL_AVISOS)

    for respuesta in (detalle, lista, avisos):
        assert respuesta.status_code == 200
        assert_campos_ausentes(respuesta, CAMPOS_PRIVADOS_PENDIENTE, valores=_valores_privados(cliente))
    # CA-15.1: ve el servicio, la descripción, la comuna, el bloque y los materiales.
    ticket = detalle.json()["ticket"]
    assert ticket["comuna"] == {"codigo": str(ay.CONCEPCION), "nombre": "Concepción"}
    assert ticket["servicio"]["nombre"] == "Pintura de habitación"
    assert ticket["descripcion"].startswith("Pintar") and ticket["materiales"] is True
    assert ticket["bloque"] == {"fecha": tk.JUEVES.isoformat(), "inicio": "08:00", "fin": "12:00"}
    assert set(ticket) == {
        "ref", "numero", "estado", "motivo_cierre", "servicio", "comuna", "bloque", "descripcion", "materiales",
        "modalidad", "modalidad_texto", "monto_publicado", "enviado_en", "vence_en", "aceptado_en",
        "finalizado_en", "cerrado_en",
    }


@pytest.mark.regla("A-03")
def test_rf17_un_ticket_cerrado_desde_pendiente_nunca_revela_la_direccion(sesion_maestro, cliente, maestro, catalogo):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.CERRADO,
                               motivo=MotivoCierre.VENCIDO_PLAZO)

    respuesta = sesion_maestro.get(f"{tk.URL}/{ticket.ref}")

    assert respuesta.status_code == 200 and respuesta.json()["ticket"]["estado"] == "cerrado"
    assert_campos_ausentes(respuesta, CAMPOS_PRIVADOS_PENDIENTE, valores=_valores_privados(cliente))


@pytest.mark.parametrize("estado", [EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO])
def test_d21_aceptado_revela_el_contacto_mutuo(sesion_cliente, sesion_maestro, cliente, maestro, catalogo, estado):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=estado)

    para_maestro = sesion_maestro.get(f"{tk.URL}/{ticket.ref}").json()["ticket"]
    para_cliente = sesion_cliente.get(f"{tk.URL}/{ticket.ref}").json()["ticket"]

    assert para_maestro["contacto"] == {
        "nombre": tk.NOMBRE_CLIENTE, "telefono": tk.TELEFONO_CLIENTE, "direccion": tk.DIRECCION,
    }
    assert para_cliente["contacto"] == {"telefono": "+56910000001"}
    # Ni aun aceptado se entrega el correo ni el RUT de nadie.
    for datos in (para_maestro, para_cliente):
        texto = json.dumps(datos)
        assert tk.CORREO_CLIENTE not in texto and maestro.perfil_maestro.rut not in texto


def test_el_cliente_no_recibe_el_telefono_del_maestro_mientras_esta_pendiente(sesion_cliente, maestro, catalogo):
    datos = _crear(sesion_cliente, maestro, catalogo)

    respuesta = sesion_cliente.get(f"{tk.URL}/{datos['ref']}")

    assert_campos_ausentes(respuesta, {"telefono", "contacto", "rut"}, valores=["+56910000001", "910000001"])


# --- Terceros (CA-25.1, RNF-07; cierra DA-05) ---


def _terceros(catalogo):
    return {
        "otro_cliente": (lambda: tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A),
                         "otro.cliente@example.com"),
        "otro_maestro": (lambda: tk.maestro_con_agenda(catalogo, n=2), ay.rut(2)),
        "curatoria": (lambda: tk.administrativo(Rol.CURATORIA, "cura@example.com"), "cura@example.com"),
        "comercial": (lambda: tk.administrativo(Rol.COMERCIAL, "comercial@example.com"), "comercial@example.com"),
        "moderacion": (lambda: tk.administrativo(Rol.MODERACION, "moderacion@example.com"), "moderacion@example.com"),
        "control_gestion": (lambda: tk.administrativo(Rol.CONTROL_GESTION, "gestion@example.com"),
                            "gestion@example.com"),
    }


@pytest.mark.terceros("ticket")
@pytest.mark.regla("A-01")
@pytest.mark.parametrize(
    "nombre", ["otro_cliente", "otro_maestro", "curatoria", "comercial", "moderacion", "control_gestion"]
)
@pytest.mark.parametrize("estado", [EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO])
def test_ca25_1_un_tercero_recibe_el_404_identico_y_queda_registrado(cliente, maestro, catalogo, nombre, estado):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=estado)
    crear, identificador = _terceros(catalogo)[nombre]
    tercero = crear()

    respuesta = tk.sesion(identificador).get(f"{tk.URL}/{ticket.ref}")

    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "ticket", str(ticket.ref))
    assert fila.recurso == "GET api/tickets/<uuid:ref>"


@pytest.mark.terceros("ticket")
@pytest.mark.regla("A-01")
def test_ca25_1_un_administrador_que_ademas_es_cliente_tampoco_ve_tickets_ajenos(cliente, maestro, catalogo):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00")
    otro = tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A)
    servicios_identidad.asignar_rol_administrativo(otro, Rol.MODERACION)

    respuesta = tk.sesion("otro.cliente@example.com").get(f"{tk.URL}/{ticket.ref}")

    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    assert RegistroAccesoDenegado.objects.get().usuario_id == otro.pk


@pytest.mark.terceros("ticket")
def test_una_ref_inexistente_da_el_mismo_404_sin_registro(sesion_cliente):
    import uuid

    respuesta = sesion_cliente.get(f"{tk.URL}/{uuid.uuid4()}")

    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("ticket")
def test_las_dos_partes_si_ven_el_ticket(sesion_cliente, sesion_maestro, maestro, catalogo):
    datos = _crear(sesion_cliente, maestro, catalogo)

    assert sesion_cliente.get(f"{tk.URL}/{datos['ref']}").status_code == 200
    assert sesion_maestro.get(f"{tk.URL}/{datos['ref']}").status_code == 200
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.terceros("ticket")
def test_sin_sesion_401_y_metodos_no_permitidos_405(cliente, maestro, catalogo):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00")

    assert Client().get(f"{tk.URL}/{ticket.ref}").status_code == 401
    assert tk.sesion(tk.CORREO_CLIENTE).delete(f"{tk.URL}/{ticket.ref}").status_code == 405
    assert Ticket.objects.filter(pk=ticket.pk, estado=EstadoTicket.PENDIENTE).exists()


# --- Listas propias (RF-28 parcial: versión mínima) ---


def test_cada_parte_lista_solo_sus_tickets(sesion_cliente, sesion_maestro, cliente, maestro, catalogo):
    mio = _crear(sesion_cliente, maestro, catalogo)
    otro_cliente = tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A)
    otro_maestro = tk.maestro_con_agenda(catalogo, n=2)
    ajeno_de_cliente = tk.ticket_directo(otro_cliente, maestro, tk.VIERNES, "08:00", "12:00")
    ajeno_de_maestro = tk.ticket_directo(cliente, otro_maestro, tk.VIERNES, "08:00", "12:00")

    del_cliente = sesion_cliente.get(tk.URL_CLIENTE).json()
    del_maestro = sesion_maestro.get(tk.URL_MAESTRO).json()

    # Del más nuevo al más antiguo; con la misma fecha de envío, el último creado primero.
    assert [t["ref"] for t in del_cliente["tickets"]] == [str(ajeno_de_maestro.ref), mio["ref"]]
    assert {t["ref"] for t in del_maestro["tickets"]} == {mio["ref"], str(ajeno_de_cliente.ref)}
    assert (del_maestro["pagina"], del_maestro["paginas"], del_maestro["total"]) == (1, 1, 2)
    # La lista del maestro usa la misma serialización: sin datos del cliente con el ticket pendiente.
    assert all("direccion" not in t and "contacto" not in t for t in del_maestro["tickets"])


def test_la_lista_se_pagina_de_a_20_y_valida_sus_parametros(sesion_cliente, cliente, catalogo):
    maestros = [tk.maestro_con_agenda(catalogo, n=n, bloques=[(d, "08:00", "12:00") for d in range(1, 8)])
                for n in range(1, 4)]
    fechas = [tk.HOY + D(days=d) for d in range(1, 8)]
    for m in maestros:
        for fecha in fechas:
            tk.ticket_directo(cliente, m, fecha, "08:00", "12:00")

    primera = sesion_cliente.get(tk.URL_CLIENTE).json()
    segunda = sesion_cliente.get(tk.URL_CLIENTE, {"pagina": "2"}).json()

    assert (len(primera["tickets"]), primera["total"], primera["paginas"]) == (20, 21, 2)
    assert len(segunda["tickets"]) == 1
    assert sesion_cliente.get(tk.URL_CLIENTE, {"pagina": "0"}).status_code == 400
    assert sesion_cliente.get(tk.URL_CLIENTE, {"otra": "1"}).json() == {
        "mensaje": MENSAJE_CLAVE_DESCONOCIDA, "errores": {},
    }


@pytest.mark.parametrize(("url", "rol_faltante"), [(tk.URL_CLIENTE, "cliente"), (tk.URL_MAESTRO, "maestro")])
def test_las_listas_exigen_el_rol(maestro, cliente, url, rol_faltante):
    identificador = ay.rut(1) if rol_faltante == "cliente" else tk.CORREO_CLIENTE

    respuesta = tk.sesion(identificador).get(url)

    assert respuesta.status_code == 403 and respuesta.json()["mensaje"] == MENSAJE_SIN_ROL


# --- Avisos (ADR-024) ---


def test_el_maestro_ve_el_aviso_del_pedido_nuevo_y_lo_marca_como_visto(
    sesion_cliente, sesion_maestro, cliente, maestro, catalogo
):
    datos = _crear(sesion_cliente, maestro, catalogo)

    lista = sesion_maestro.get(tk.URL_AVISOS).json()

    assert lista["sin_ver"] == 1 and lista["total"] == 1
    aviso = lista["avisos"][0]
    assert aviso["tipo"] == "ticket_nuevo" and aviso["ticket"] == datos["ref"] and aviso["visto"] is False
    assert aviso["texto"] == (
        "Tienes un pedido nuevo: Pintura de habitación en Concepción, el jueves 8 de octubre, "
        "de 08:00 a 12:00. Revísalo y responde."
    )
    # El cliente no tiene avisos de este pedido.
    assert sesion_cliente.get(tk.URL_AVISOS).json()["avisos"] == []

    marcado = post_json(sesion_maestro, tk.URL_VISTOS, {"avisos": [aviso["ref"]]})

    assert marcado.status_code == 200 and marcado.json() == {"sin_ver": 0}
    assert sesion_maestro.get(tk.URL_AVISOS).json()["avisos"][0]["visto"] is True


def test_nadie_marca_como_vistos_los_avisos_de_otra_persona(sesion_cliente, maestro, catalogo):
    _crear(sesion_cliente, maestro, catalogo)
    aviso = AvisoTicket.objects.get()

    respuesta = post_json(sesion_cliente, tk.URL_VISTOS, {"avisos": [str(aviso.ref)]})

    assert respuesta.status_code == 200 and respuesta.json() == {"sin_ver": 0}
    aviso.refresh_from_db()
    assert aviso.visto_en is None


@pytest.mark.parametrize("valor", [[], "no-es-lista", ["no-es-ref"], [1], ["00000000-0000-0000-0000-000000000001"] * 101])
def test_marcar_vistos_valida_la_lista(sesion_cliente, valor):
    respuesta = post_json(sesion_cliente, tk.URL_VISTOS, {"avisos": valor})

    assert respuesta.status_code == 400 and set(respuesta.json()["errores"]) == {"avisos"}


def test_los_avisos_exigen_sesion():
    assert Client().get(tk.URL_AVISOS).status_code == 401
    assert post_json(Client(), tk.URL_VISTOS, {"avisos": []}).status_code == 401


def test_el_aviso_de_cierre_explica_el_motivo_a_cada_parte(sesion_cliente, sesion_maestro, cliente, maestro, catalogo):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.CERRADO,
                               motivo=MotivoCierre.RECHAZADO_MAESTRO)
    for destinatario in (cliente, maestro):
        AvisoTicket.objects.create(ticket=ticket, destinatario=destinatario, tipo=TipoAvisoTicket.TICKET_CERRADO)

    para_cliente = sesion_cliente.get(tk.URL_AVISOS).json()["avisos"][0]["texto"]
    para_maestro = sesion_maestro.get(tk.URL_AVISOS)

    assert para_cliente.endswith("se cerró: el maestro no puede tomarlo.")
    assert para_maestro.json()["avisos"][0]["texto"].endswith("se cerró: lo rechazaste.")
    assert_campos_ausentes(para_maestro, CAMPOS_PRIVADOS_PENDIENTE, valores=_valores_privados(cliente))


# --- Historial de solo inserción (ADR-023, punto 2) y CHECK de defensa ---


def test_ticket_evento_no_se_modifica_ni_se_borra_desde_la_aplicacion(sesion_cliente, maestro, catalogo):
    _crear(sesion_cliente, maestro, catalogo)
    evento = TicketEvento.objects.get(ticket_id=Ticket.objects.get().pk)

    with pytest.raises(OperacionNoPermitida):
        evento.save()
    with pytest.raises(OperacionNoPermitida):
        evento.delete()
    with pytest.raises(OperacionNoPermitida):
        TicketEvento.objects.filter(pk=evento.pk).update(estado_nuevo="cerrado")
    with pytest.raises(OperacionNoPermitida):
        TicketEvento.objects.filter(pk=evento.pk).delete()


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE ticket_evento SET estado_nuevo = 'aceptado' WHERE id = %s",
        "DELETE FROM ticket_evento WHERE id = %s",
        "TRUNCATE ticket_evento",
    ],
)
def test_los_triggers_de_ticket_evento_rechazan_update_delete_y_truncate(sesion_cliente, maestro, catalogo, sentencia):
    _crear(sesion_cliente, maestro, catalogo)
    evento = TicketEvento.objects.get(ticket_id=Ticket.objects.get().pk)

    with pytest.raises(Exception, match="no admite"), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sentencia, [evento.pk] if "%s" in sentencia else None)

    assert TicketEvento.objects.filter(pk=evento.pk, estado_nuevo="pendiente").exists()


@pytest.mark.parametrize(
    ("sql", "restriccion"),
    [
        ("INSERT INTO ticket_evento (ticket_id, fecha, estado_nuevo, autor_tipo) VALUES (1, now(), 'pendiente', "
         "'usuario')", "ticket_evento_autor_coherente"),
        ("INSERT INTO ticket_evento (ticket_id, fecha, estado_nuevo, autor_tipo) VALUES (1, now(), 'cerrado', "
         "'sistema')", "ticket_evento_motivo_solo_al_cerrar"),
        ("INSERT INTO ticket_evento (ticket_id, fecha, estado_nuevo, autor_tipo) VALUES (1, now(), 'borrado', "
         "'sistema')", "ticket_evento_estado_nuevo_valido"),
    ],
)
def test_los_check_de_ticket_evento(sql, restriccion):
    with pytest.raises(IntegrityError, match=restriccion), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql)


@pytest.mark.parametrize(
    ("cambios", "restriccion"),
    [
        ({"enviado_en": "inicio_en - interval '4 hours'"}, "ticket_anticipacion_minima"),
        ({"vence_en": "vence_en + interval '1 second'"}, "ticket_vence_en_formula"),
        ({"motivo_cierre": "'vencido_plazo'"}, "ticket_motivo_solo_si_cerrado"),
        ({"estado": "'aceptado'"}, "ticket_fechas_segun_estado"),
        ({"estado": "'borrado'"}, "ticket_estado_valido"),
        ({"direccion": "'   '"}, "ticket_direccion_no_vacia"),
        ({"materiales": "NULL"}, "materiales"),
        ({"inicio_min": "fin_min"}, "ticket_rango_valido"),
        ({"monto_publicado": "0"}, "ticket_monto_publicado_valido"),
        ({"estado": "'aceptado'", "aceptado_en": "vence_en"}, "ticket_aceptado_en_plazo"),
    ],
)
def test_los_check_de_defensa_de_ticket(cliente, maestro, catalogo, cambios, restriccion):
    ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00")
    asignaciones = ", ".join(f"{columna} = {valor}" for columna, valor in cambios.items())

    with pytest.raises(IntegrityError, match=restriccion), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"UPDATE ticket SET {asignaciones} WHERE id = %s", [ticket.pk])


def test_ningun_mensaje_nuevo_tiene_texto_de_programador(sesion_cliente, maestro, catalogo):
    respuestas = [
        tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, materiales=None, descripcion=None, direccion=None)),
        tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, fecha=tk.HOY.isoformat(), inicio="12:00",
                                            fin="16:00")),
        tk.enviar(sesion_cliente, tk.pedido(maestro, catalogo, comuna=str(ay.LEBU))),
    ]
    for respuesta in respuestas:
        texto = respuesta.content.decode("utf-8")
        assert not [t for t in TEXTO_PROHIBIDO if t in texto], texto
        assert "ticket" not in texto.lower() and "bloque" not in respuesta.json()["mensaje"].lower()
