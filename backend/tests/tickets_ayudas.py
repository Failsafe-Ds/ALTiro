"""Ayudas para las pruebas de tickets (S4, incremento 4). Datos ficticios: @example.com, RUT sintéticos, +56 9 1000 000N.

Reloj de ``busqueda_ayudas``: miércoles 7 de octubre de 2026, 08:00 en Santiago.
El maestro de ``maestro_con_agenda`` tiene los horarios:

- miércoles (hoy) 12:00-16:00: empieza exactamente en 4 horas (borde de RF-16);
- jueves 08:00-12:00 (24 h), 12:00-16:00 (28 h) y viernes 08:00-12:00 (48 h).
"""
import datetime

from django.test import Client

from identidad import servicios as servicios_identidad
from perfil import agenda, ocurrencias
from perfil.models import ServicioMaestro
from tests import busqueda_ayudas as ay
from tests.ayudas import CONTRASENA, TEL_B, crear_cliente, iniciar_sesion, post_json
from tickets.models import EstadoTicket, MotivoCierre, Ticket
from tickets.servicios import calcular_vence_en

URL = "/api/tickets"
URL_CLIENTE = "/api/clientes/tickets"
URL_MAESTRO = "/api/maestros/tickets"
URL_AVISOS = "/api/avisos"
URL_VISTOS = "/api/avisos/vistos"

AHORA = ay.AHORA
HOY = ay.HOY
JUEVES = HOY + datetime.timedelta(days=1)
VIERNES = HOY + datetime.timedelta(days=2)
CORREO_CLIENTE = "ana.prueba@example.com"
NOMBRE_CLIENTE = "Ana Prueba"
TELEFONO_CLIENTE = "+56910000002"  # TEL_B en forma canónica
DIRECCION = "Pasaje Ficticio 123, depto 45"
BLOQUES = ((3, "12:00", "16:00"), (4, "08:00", "12:00"), (4, "12:00", "16:00"), (5, "08:00", "12:00"))


def maestro_con_agenda(catalogo, n=1, **cambios):
    datos = {
        "servicios": ("pintura",),
        "comunas": ((ay.CONCEPCION, True), (ay.CORONEL, False)),
        "bloques": BLOQUES,
    }
    datos.update(cambios)
    return ay.maestro(n, catalogo, **datos)


def cliente(correo=CORREO_CLIENTE, telefono=TEL_B):
    return crear_cliente(correo=correo, telefono=telefono)


def administrativo(rol, correo):
    return servicios_identidad.crear_cuenta_administrativa(
        nombre="Admin Prueba", correo=correo, roles=[rol], contrasena=CONTRASENA
    )


def sesion(identificador):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


def pedido(del_maestro, catalogo, **cambios):
    datos = {
        "maestro": ay.ref(del_maestro),
        "servicio": str(catalogo["pintura"].ref),
        "comuna": str(ay.CONCEPCION),
        "fecha": JUEVES.isoformat(),
        "inicio": "08:00",
        "fin": "12:00",
        "direccion": DIRECCION,
        "descripcion": "Pintar una pieza de 3 x 4 metros, dos manos.",
        "materiales": True,
    }
    datos.update(cambios)
    return {clave: valor for clave, valor in datos.items() if valor is not None}


def enviar(client, datos):
    return post_json(client, URL, datos)


def ticket_directo(cliente_usuario, maestro, fecha, inicio, fin, estado=EstadoTicket.PENDIENTE,
                   enviado_en=None, motivo=None):
    """Ticket creado por ORM, coherente con los CHECK (simula los incrementos 5 y 6)."""
    enviado_en = enviado_en or AHORA
    servicio_maestro = ServicioMaestro.objects.filter(maestro_id=maestro.pk).first()
    inicio_min, fin_min = agenda.minutos_de_hora(inicio), agenda.minutos_de_hora(fin)
    inicio_en = ocurrencias.instante(fecha, inicio_min)
    campos = {
        "cliente_id": cliente_usuario.pk,
        "perfil_maestro_id": maestro.pk,
        "servicio_maestro": servicio_maestro,
        "modalidad": servicio_maestro.modalidad,
        "monto_publicado": servicio_maestro.monto,
        "fecha": fecha,
        "inicio_min": inicio_min,
        "fin_min": fin_min,
        "inicio_en": inicio_en,
        "fin_en": ocurrencias.instante(fecha, fin_min),
        "comuna_id": ay.CONCEPCION,
        "direccion": DIRECCION,
        "descripcion": "Trabajo de prueba",
        "materiales": False,
        "estado": estado,
        "enviado_en": enviado_en,
        "vence_en": calcular_vence_en(enviado_en, inicio_en),
    }
    if estado in (EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO):
        campos["aceptado_en"] = enviado_en
    if estado == EstadoTicket.FINALIZADO:
        # CHECK de finalización (ADR-026, E-1): el monto publicado y, si es por hora, aceptado.
        campos.update(finalizado_en=enviado_en, monto_final=servicio_maestro.monto, monto_final_en=enviado_en,
                      monto_final_autor_id=maestro.pk)
        if servicio_maestro.modalidad == "por_hora":
            campos["precio_aceptado_en"] = enviado_en
    if estado == EstadoTicket.CERRADO:
        campos["cerrado_en"] = enviado_en
        campos["motivo_cierre"] = motivo or MotivoCierre.RECHAZADO_MAESTRO
    return Ticket.objects.create(**campos)
