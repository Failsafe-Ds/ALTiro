"""Cuentas y maestros FICTICIOS para la pila de demostración (ADR-028).

Lo llama ``python manage.py cargar_datos_demo --con-cuentas``. Crea, de forma
idempotente y rotulada "(demo)":

- 10 maestros publicados (expediente aprobado, comuna base, cobertura, foto
  sintética, agenda de lunes a sábado y 2 o 3 servicios de oficios **no
  regulados**): 7 en el Gran Concepción y 3 en Santiago. El primero
  (``MAESTRO_CON_INGRESO``) puede ingresar; los demás tienen contraseña
  inutilizable;
- 2 clientes que pueden ingresar (Concepción y Santiago);
- tickets del primer cliente con el maestro que ingresa: uno pendiente y uno
  aceptado (con dos mensajes) en los próximos días, uno finalizado sin
  evaluar y uno cerrado por rechazo, cada uno con su historial.

Credenciales (ADR-028, punto 3): **nunca** una contraseña fija en el código.
Las cuentas nuevas reciben una contraseña aleatoria (``secrets``) que cumple
ADR-013; quien llama la muestra una sola vez en la consola. Las cuentas que ya
existen conservan su contraseña salvo ``restablecer=True``.

Reglas compartidas con el volumen de prueba en ``busqueda.ficticios``. No
escribe la bitácora (ADR-010) ni avisos.
"""
import datetime
import random
import secrets
import uuid
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from busqueda import ficticios
from catalogo.models import Modalidad
from expediente import vigencia
from identidad import servicios as identidad
from identidad.models import PerfilMaestro, Usuario
from mensajeria.models import Mensaje
from perfil import ocurrencias
from perfil.models import Cobertura, Disponibilidad, ServicioMaestro
from tickets.models import EstadoTicket, MotivoCierre, Ticket, TicketEvento

MOTIVO = "Datos ficticios de demostración (ADR-028)."
# RUT sintéticos 49.990.001 en adelante: no chocan con generar_volumen_prueba (50.000.000 a 59.999.999).
RUT_BASE_DEMO = 49_990_000
CORREO_MAESTRO = "maestro.demo@example.com"
SERVICIOS_POR_MAESTRO = 3
# Lunes a sábado, 09:00-13:00 y 14:00-18:00 (minutos múltiplos de 30, ADR-020).
AGENDA = [(dia, inicio, fin) for dia in range(1, 7) for inicio, fin in ((540, 780), (840, 1080))]
# (nombre, comuna base, otras comunas de cobertura). CUT 2018 (ADR-012).
MAESTROS = (
    ("Maestro Demo Uno (demo)", 8101, [8110, 8108, 8103]),
    ("Maestra Demo Dos (demo)", 8101, [8103]),
    ("Maestro Demo Tres (demo)", 8110, [8101, 8112]),
    ("Maestra Demo Cuatro (demo)", 8108, [8101, 8102]),
    ("Maestro Demo Cinco (demo)", 8103, [8101, 8108]),
    ("Maestra Demo Seis (demo)", 8102, [8108]),
    ("Maestro Demo Siete (demo)", 8101, [8110]),
    ("Maestra Demo Ocho (demo)", 13101, [13123, 13120]),
    ("Maestro Demo Nueve (demo)", 13123, [13101, 13114]),
    ("Maestra Demo Diez (demo)", 13120, [13101, 13119]),
)
MAESTRO_CON_INGRESO = 0
# (correo, nombre, teléfono, comuna)
CLIENTES = (
    ("cliente.demo.1@example.com", "Clienta Demo Uno (demo)", "+56 9 0002 0101", "8101"),
    ("cliente.demo.2@example.com", "Cliente Demo Dos (demo)", "+56 9 0002 0102", "13101"),
)
_ALFABETO = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"


@dataclass
class Cuenta:
    """Cuenta con ingreso. ``contrasena`` es ``None`` si se conservó la que tenía."""

    rol: str
    identificador: str
    contrasena: str | None
    nueva: bool


def contrasena_aleatoria():
    """16 caracteres al azar (``secrets``) en 4 grupos, sin letras ambiguas; cumple ADR-013."""
    texto = "".join(secrets.choice(_ALFABETO) for _ in range(16))
    contrasena = "-".join(texto[i:i + 4] for i in range(0, 16, 4))
    identidad.validar_contrasena_nueva(contrasena)
    return contrasena


def rut_demo(numero):
    return ficticios.rut_con_dv(RUT_BASE_DEMO + numero + 1)


def _servicios_de(numero, por_oficio):
    """2 oficios por maestro, rotando el catálogo no regulado, y hasta 3 servicios de ellos."""
    oficios = list(por_oficio)
    elegidos = [oficios[numero % len(oficios)], oficios[(numero + 2) % len(oficios)]]
    candidatos = [s for o in elegidos for s in por_oficio[o]]
    return candidatos[:SERVICIOS_POR_MAESTRO]


def _crear_maestros(por_oficio, contrasena):
    """Crea los maestros que faltan; devuelve ``(creados, cuenta_con_ingreso | None si ya existía)``."""
    creados, cuenta = 0, None
    for numero, (nombre, base, extra) in enumerate(MAESTROS):
        rut = rut_demo(numero)
        if PerfilMaestro.objects.filter(rut=rut.replace("-", "")).exists():
            continue
        azar = random.Random(f"demo-maestro-{numero}")
        servicios = _servicios_de(numero, por_oficio)
        con_ingreso = numero == MAESTRO_CON_INGRESO
        ficticios.crear_maestro_publicado(
            nombre=nombre,
            telefono=f"+56 9 0002 {numero + 1:04d}",
            rut=rut,
            correo=CORREO_MAESTRO if con_ingreso else identidad.AUSENTE,
            contrasena=contrasena if con_ingreso else None,
            servicios=servicios,
            montos=[azar.randint(15, 80) * 1000 for _ in servicios],
            base=base,
            extra=extra,
            agenda=AGENDA,
            foto=ficticios.foto_sintetica(azar),
            motivo=MOTIVO,
        )
        creados += 1
        if con_ingreso:
            cuenta = Cuenta("maestro", f"{rut} o {CORREO_MAESTRO}", contrasena, True)
    return creados, cuenta


def _crear_clientes(contrasena):
    cuentas = []
    for correo, nombre, telefono, comuna in CLIENTES:
        if Usuario.objects.filter(correo=correo).exists():
            continue
        identidad.crear_cuenta_cliente(
            nombre=nombre, telefono=telefono, correo=correo, contrasena=contrasena, comuna=comuna
        )
        cuentas.append(Cuenta("cliente", correo, contrasena, True))
    return cuentas


def _usuarios_con_ingreso():
    """``[(rol, identificador, Usuario)]`` de las cuentas demo con ingreso que existen."""
    resultado = []
    perfil = PerfilMaestro.objects.select_related("usuario").filter(
        rut=rut_demo(MAESTRO_CON_INGRESO).replace("-", "")
    ).first()
    if perfil is not None:
        resultado.append(("maestro", f"{rut_demo(MAESTRO_CON_INGRESO)} o {CORREO_MAESTRO}", perfil.usuario))
    for correo, *_ in CLIENTES:
        usuario = Usuario.objects.filter(correo=correo).first()
        if usuario is not None:
            resultado.append(("cliente", correo, usuario))
    return resultado


def _crear_tickets(ahora):
    """Tickets del cliente 1 con el maestro con ingreso; solo si ese cliente aún no tiene ninguno."""
    cliente = Usuario.objects.filter(correo=CLIENTES[0][0]).first()
    perfil = PerfilMaestro.objects.filter(rut=rut_demo(MAESTRO_CON_INGRESO).replace("-", "")).first()
    if cliente is None or perfil is None or Ticket.objects.filter(cliente_id=cliente.pk).exists():
        return 0
    servicios = list(ServicioMaestro.objects.filter(maestro=perfil, retirado_en__isnull=True).order_by("pk"))
    patrones = list(Disponibilidad.objects.filter(maestro=perfil, retirado_en__isnull=True))
    base = Cobertura.objects.get(maestro=perfil, es_base=True).comuna_id
    hoy = vigencia.hoy_negocio(ahora)
    futuras = [o for o in ocurrencias.ocurrencias(patrones, hoy, ocurrencias.HORIZONTE_DIAS)
               if ocurrencias.empieza_con_anticipacion(o, ahora)]
    pasadas = [o for o in ocurrencias.ocurrencias(patrones, hoy - datetime.timedelta(days=14), 14)
               if o.fin_en < ahora]
    if len(futuras) < 4 or len(pasadas) < 3:
        return 0
    h = datetime.timedelta(hours=1)

    def nuevo(una, servicio, estado, enviado, descripcion):
        return ficticios.ticket(
            perfil=perfil, cliente=cliente, servicio=servicio, comuna=base, una=una, estado=estado,
            enviado_en=enviado, direccion="Calle Ficticia 123 (demo)", descripcion=descripcion, materiales=False,
        )

    pendiente = nuevo(futuras[1], servicios[0], EstadoTicket.PENDIENTE, ahora - h / 2,
                      "Pedido de demostración pendiente de respuesta.")
    aceptado = nuevo(futuras[3], servicios[-1], EstadoTicket.ACEPTADO, ahora - 2 * h,
                     "Pedido de demostración aceptado.")
    aceptado.aceptado_en = ahora - h
    finalizado = nuevo(pasadas[-1], servicios[0], EstadoTicket.FINALIZADO, pasadas[-1].inicio_en - 30 * h,
                       "Trabajo de demostración terminado, sin evaluar.")
    finalizado.aceptado_en = finalizado.enviado_en + 2 * h
    finalizado.finalizado_en = min(pasadas[-1].fin_en + h, ahora)
    finalizado.monto_final, finalizado.monto_final_en = finalizado.monto_publicado, finalizado.finalizado_en
    finalizado.monto_final_autor_id = perfil.pk
    if finalizado.modalidad == Modalidad.POR_HORA:
        finalizado.precio_aceptado_en = finalizado.finalizado_en
    cerrado = nuevo(pasadas[0], servicios[-1], EstadoTicket.CERRADO, pasadas[0].inicio_en - 30 * h,
                    "Pedido de demostración que el maestro no pudo tomar.")
    cerrado.cerrado_en, cerrado.motivo_cierre = cerrado.enviado_en + 3 * h, MotivoCierre.RECHAZADO_MAESTRO

    pasos = {
        "aceptado": [(aceptado.aceptado_en, EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO, perfil.pk, None)],
        "finalizado": [
            (finalizado.aceptado_en, EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO, perfil.pk, None),
            (finalizado.finalizado_en, EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO, perfil.pk, None),
        ],
        "cerrado": [(cerrado.cerrado_en, EstadoTicket.PENDIENTE, EstadoTicket.CERRADO, perfil.pk,
                     MotivoCierre.RECHAZADO_MAESTRO)],
    }
    with transaction.atomic():
        tickets = Ticket.objects.bulk_create([pendiente, aceptado, finalizado, cerrado])
        eventos = [ficticios.evento(t, t.enviado_en, None, EstadoTicket.PENDIENTE, cliente.pk) for t in tickets]
        for clave, t in (("aceptado", aceptado), ("finalizado", finalizado), ("cerrado", cerrado)):
            eventos += [ficticios.evento(t, *paso) for paso in pasos[clave]]
        TicketEvento.objects.bulk_create(eventos)
        Mensaje.objects.bulk_create([
            Mensaje(ticket_id=aceptado.pk, autor_id=cliente.pk, enviado_en=ahora - h / 2, clave_envio=uuid.uuid4(),
                    texto="Hola, ¿puede venir a la hora acordada? (mensaje de demostración)"),
            Mensaje(ticket_id=aceptado.pk, autor_id=perfil.pk, enviado_en=ahora - h / 4, clave_envio=uuid.uuid4(),
                    texto="Sí, llego a la hora. (mensaje de demostración)"),
        ])
    return len(tickets)


def cargar_cuentas_demo(*, restablecer=False, ahora=None):
    """Crea lo que falte de la demostración. Devuelve ``(maestros_nuevos, tickets_nuevos, [Cuenta])``.

    Una sola contraseña aleatoria por ejecución para las cuentas nuevas (y, con
    ``restablecer``, también para las existentes). Las demás cuentas aparecen con
    ``contrasena=None``.
    """
    ahora = ahora or timezone.now()
    por_oficio = ficticios.servicios_por_oficio()
    if len(por_oficio) < 2:
        raise ValueError("El catálogo no tiene servicios suficientes de oficios no regulados.")
    contrasena = contrasena_aleatoria()
    maestros, cuenta_maestro = _crear_maestros(por_oficio, contrasena)
    nuevas = ([cuenta_maestro] if cuenta_maestro else []) + _crear_clientes(contrasena)
    con_nueva = {c.identificador for c in nuevas}
    cuentas = list(nuevas)
    for rol, identificador, usuario in _usuarios_con_ingreso():
        if identificador in con_nueva:
            continue
        if restablecer:
            identidad.cambiar_contrasena(usuario, contrasena)
            cuentas.append(Cuenta(rol, identificador, contrasena, False))
        else:
            cuentas.append(Cuenta(rol, identificador, None, False))
    tickets = _crear_tickets(ahora)
    orden = {"maestro": 0, "cliente": 1}
    cuentas.sort(key=lambda c: (orden[c.rol], c.identificador))
    return maestros, tickets, cuentas
