"""Genera el volumen de prueba de RNF-01 y RNF-03 con datos **FICTICIOS** (propuesta del S4, §2; ADR-022, punto 8).

**Úsese solo en una pila aparte**, nunca en la de la demostración::

    ALTIRO_HTTP_PORT=8080 ALTIRO_HTTPS_PORT=8443 \
    DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost:8443,https://127.0.0.1:8443 \
    docker compose -p altiro-volumen up -d --build
    docker compose -p altiro-volumen exec app \
        python manage.py generar_volumen_prueba --semilla 42 --confirmo-datos-ficticios

Qué crea (informe §3 del CLAUDE.md, "volumen de prueba"):

- 100 maestros con expediente ``aprobado``, comuna base y cobertura en el
  Gran Concepción (provincia de Concepción y, a veces, Arauco), foto (JPEG
  sintético de un color, procesado con ``perfil.fotos``) y agenda semanal;
- 300 servicios publicados (3 por maestro), solo de oficios **no regulados**:
  los regulados exigirían licencias SEC con archivo cifrado, que este comando
  no fabrica (supuesto de este incremento);
- los servicios del catálogo de demostración que falten
  (``catalogo.management.commands.cargar_datos_demo``, también ficticios);
- **1.000 tickets** (10 por maestro, S4 incremento 4) con 200 clientes
  ficticios (2 por maestro): en cada maestro, un ticket aceptado y dos
  pendientes en sus próximos 14 días, y siete pasados (finalizados o
  cerrados con alguno de los cinco motivos) de los últimos 60 días, cada uno
  con su historial en ``ticket_evento``. Los aceptados ocupan agenda, así la
  búsqueda se mide con ocupación real. Sin avisos (nadie entra con estas
  cuentas). S5 incremento 8: 5.000 mensajes (50 por maestro) y evaluaciones en parte de los finalizados.

Rotulado y resguardos:

- Nombres "Maestro Ficticio NNN (datos de prueba)" y "Cliente Ficticio NNN
  (datos de prueba)"; RUT sintéticos a partir
  de 50.000.000 y teléfonos "+56 9 0000 0NNN" para los maestros (sin correo);
  "cliente.ficticio.SEMILLA.NNN@example.com" y "+56 9 0001 NNNN" para los clientes.
- Contraseñas **inutilizables** (``set_unusable_password``): nadie puede
  entrar con estas cuentas.
- Se niega a correr sin ``--confirmo-datos-ficticios``.
- Idempotente por semilla: cada maestro se identifica por su RUT y cada
  cliente por su correo, derivados de
  la semilla y de su número; si ya existe, no se toca. Cada maestro se crea en
  su propia transacción. Los tickets se crean en una sola transacción y solo
  si los clientes de la semilla todavía no tienen ninguno.
- No escribe la bitácora (igual que ``cargar_datos_demo``): no es una acción
  de una persona de la aplicación.
"""
import datetime
import io
import logging
import random
import secrets
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image

from catalogo.management.commands.cargar_datos_demo import cargar_datos_demo
from catalogo.models import Modalidad, Servicio, ServicioModalidad
from evaluaciones.models import Evaluacion, ParteEvaluacion
from expediente import vigencia
from expediente.models import EstadoExpediente, Expediente, OficioMaestro
from identidad import servicios as identidad
from identidad.models import PerfilMaestro, Usuario
from mensajeria.models import Mensaje
from perfil import fotos, ocurrencias
from perfil.models import Cobertura, Disponibilidad, PerfilPublico, ServicioMaestro
from tickets.models import (
    ANTICIPACION_MINIMA,
    PLAZO_RESPUESTA,
    AutorTipo,
    EstadoTicket,
    MotivoCierre,
    Ticket,
    TicketEvento,
)
from tickets.servicios import calcular_vence_en

logger = logging.getLogger(__name__)

MAESTROS = 100
SERVICIOS_POR_MAESTRO = 3
RUT_BASE = 50_000_000
# Provincia de Concepción (81xx) y algunas de Arauco (82xx), CUT 2018 (ADR-012).
COMUNAS_BASE = [8101, 8102, 8103, 8104, 8105, 8106, 8107, 8108, 8109, 8110, 8111, 8112]
COMUNAS_EXTRA = COMUNAS_BASE + [8201, 8202, 8203, 8205]
MOTIVO = "Datos ficticios del volumen de prueba (RNF-01, RNF-03)."
# 10 tickets y 2 clientes por maestro: 1.000 tickets y 200 clientes con 100 maestros.
TICKETS_POR_MAESTRO = 10
FUTUROS_POR_MAESTRO = 3  # uno aceptado y dos pendientes
CLIENTES_POR_MAESTRO = 2
DIAS_HISTORIA = 60
# 50 mensajes por maestro: 5.000 con 100 maestros (RNF-03). Evaluaciones en parte de las órdenes finalizadas.
MENSAJES_POR_MAESTRO = 50
PROBABILIDAD_EVAL_CLIENTE = 0.6
PROBABILIDAD_EVAL_MAESTRO = 0.4


def rut_ficticio(semilla, numero):
    """RUT sintético válido, distinto por semilla y número, sin puntos: 5x.xxx.xxx-DV."""
    cuerpo = RUT_BASE + (semilla % 10_000) * 1_000 + numero
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    dv = 11 - suma % 11
    return f"{cuerpo}-{'0' if dv == 11 else 'K' if dv == 10 else dv}"


def _foto(azar):
    salida = io.BytesIO()
    color = tuple(azar.randint(40, 220) for _ in range(3))
    Image.new("RGB", (320, 320), color).save(salida, format="JPEG", quality=80)
    return fotos.variantes(salida.getvalue())


def _servicios_por_oficio():
    """``{oficio: [Servicio]}`` de los oficios **no regulados** activos con servicios activos."""
    por_oficio = {}
    for servicio in Servicio.objects.filter(activo=True, oficio__activo=True, oficio__regulado=False).select_related(
        "oficio"
    ).order_by("oficio__orden", "orden", "pk"):
        if ServicioModalidad.objects.filter(servicio=servicio).exists():
            por_oficio.setdefault(servicio.oficio, []).append(servicio)
    return por_oficio


def _elegir_servicios(azar, por_oficio):
    oficios = list(por_oficio)
    elegidos = azar.sample(oficios, 2)
    while sum(len(por_oficio[o]) for o in elegidos) < SERVICIOS_POR_MAESTRO:
        elegidos.append(azar.choice([o for o in oficios if o not in elegidos]))
    candidatos = [s for o in elegidos for s in por_oficio[o]]
    servicios = azar.sample(candidatos, SERVICIOS_POR_MAESTRO)
    return {s.oficio for s in servicios}, servicios


def _agenda(azar):
    bloques = []
    for dia in sorted(azar.sample(range(1, 8), azar.randint(2, 5))):
        inicio = azar.randint(14, 36) * 30  # 07:00 a 18:00
        fin = min(inicio + azar.randint(4, 12) * 30, 1440)
        bloques.append((dia, inicio, fin))
    return bloques


def crear_maestro(semilla, numero, por_oficio):
    """Crea el maestro ficticio ``numero``; devuelve ``False`` si ya existía."""
    rut = rut_ficticio(semilla, numero)
    if PerfilMaestro.objects.filter(rut=rut.replace("-", "")).exists():
        return False
    azar = random.Random(f"{semilla}-{numero}")
    variantes = _foto(azar)
    nombre_foto = fotos.guardar(variantes)
    try:
        with transaction.atomic():
            usuario = identidad.crear_cuenta_maestro(
                nombre=f"Maestro Ficticio {numero + 1:03d} (datos de prueba)",
                telefono=f"+56 9 0000 {numero:04d}",
                rut=rut,
                contrasena=secrets.token_urlsafe(24),
            )
            usuario.set_unusable_password()
            usuario.save(update_fields=["password"])
            oficios, servicios = _elegir_servicios(azar, por_oficio)
            OficioMaestro.objects.bulk_create([OficioMaestro(maestro_id=usuario.pk, oficio=o) for o in oficios])
            ServicioMaestro.objects.bulk_create(
                [
                    ServicioMaestro(
                        maestro_id=usuario.pk,
                        servicio=s,
                        modalidad=ServicioModalidad.objects.filter(servicio=s).order_by("modalidad").first().modalidad,
                        monto=azar.randint(10, 120) * 1000,
                    )
                    for s in servicios
                ]
            )
            base = azar.choice(COMUNAS_BASE)
            extra = azar.sample([c for c in COMUNAS_EXTRA if c != base], azar.randint(1, 4))
            Cobertura.objects.bulk_create(
                [Cobertura(maestro_id=usuario.pk, comuna_id=base, es_base=True)]
                + [Cobertura(maestro_id=usuario.pk, comuna_id=c, es_base=False) for c in extra]
            )
            Disponibilidad.objects.bulk_create(
                [
                    Disponibilidad(maestro_id=usuario.pk, dia_semana=d, inicio_min=i, fin_min=f)
                    for d, i, f in _agenda(azar)
                ]
            )
            PerfilPublico.objects.filter(perfil_maestro_id=usuario.pk).update(
                foto=nombre_foto, foto_actualizada_en=timezone.now()
            )
            Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(
                estado=EstadoExpediente.APROBADO, estado_motivo=MOTIVO, estado_cambiado_en=timezone.now()
            )
    except BaseException:
        fotos.borrar(nombre_foto)
        raise
    return True


# --- Tickets ficticios (S4, incremento 4; RNF-01 con 1.000 tickets, RNF-03) ---


def correo_cliente(semilla, numero):
    return f"cliente.ficticio.{semilla}.{numero:03d}@example.com"


def crear_cliente(semilla, numero):
    """Cliente ficticio ``numero`` (idempotente por correo), con contraseña inutilizable."""
    correo = correo_cliente(semilla, numero)
    existente = Usuario.objects.filter(correo=correo).first()
    if existente is not None:
        return existente
    azar = random.Random(f"{semilla}-cliente-{numero}")
    with transaction.atomic():
        usuario = identidad.crear_cuenta_cliente(
            nombre=f"Cliente Ficticio {numero + 1:03d} (datos de prueba)",
            telefono=f"+56 9 0001 {numero:04d}",
            correo=correo,
            contrasena=secrets.token_urlsafe(24),
            comuna=str(azar.choice(COMUNAS_BASE)),
        )
        usuario.set_unusable_password()
        usuario.save(update_fields=["password"])
    return usuario


def _evento(ticket, fecha, anterior, nuevo, autor_id=None, motivo=None):
    return TicketEvento(
        ticket_id=ticket.pk,
        fecha=fecha,
        estado_anterior=anterior,
        estado_nuevo=nuevo,
        motivo=motivo,
        autor_tipo=AutorTipo.SISTEMA if autor_id is None else AutorTipo.USUARIO,
        autor_id=autor_id,
    )


def _entre(azar, desde, hasta):
    """Instante al azar en ``[desde, hasta)``, con segundos enteros."""
    segundos = max(1, int((hasta - desde).total_seconds()))
    return desde + datetime.timedelta(seconds=azar.randrange(segundos))


def _ticket(azar, perfil, cliente, servicios, comunas, una, estado, enviado_en):
    servicio = azar.choice(servicios)
    return Ticket(
        cliente_id=cliente.pk,
        perfil_maestro_id=perfil.pk,
        servicio_maestro=servicio,
        modalidad=servicio.modalidad,
        monto_publicado=servicio.monto,
        fecha=una.fecha,
        inicio_min=una.inicio_min,
        fin_min=una.fin_min,
        inicio_en=una.inicio_en,
        fin_en=una.fin_en,
        comuna_id=azar.choice(comunas),
        direccion=f"Calle Ficticia {azar.randint(1, 999)} (datos de prueba)",
        descripcion="Trabajo ficticio del volumen de prueba.",
        materiales=azar.random() < 0.5,
        estado=estado,
        enviado_en=enviado_en,
        vence_en=calcular_vence_en(enviado_en, una.inicio_en),
    )


def _cerrar(azar, ticket):
    """Cierre coherente con ADR-023, punto 3 (el autor y la fecha según el motivo)."""
    motivo = azar.choice(["vencido", MotivoCierre.CANCELADO_CLIENTE, MotivoCierre.RECHAZADO_MAESTRO,
                          MotivoCierre.BLOQUE_TOMADO])
    if motivo == "vencido":
        proximidad = ticket.inicio_en.astimezone(datetime.timezone.utc) - ANTICIPACION_MINIMA <= ticket.enviado_en + PLAZO_RESPUESTA
        motivo = MotivoCierre.VENCIDO_PROXIMIDAD if proximidad else MotivoCierre.VENCIDO_PLAZO
        ticket.cerrado_en, autor = ticket.vence_en, None
    else:
        ticket.cerrado_en = _entre(azar, ticket.enviado_en, ticket.vence_en)
        autor = ticket.cliente_id if motivo == MotivoCierre.CANCELADO_CLIENTE else ticket.perfil_maestro_id
    ticket.estado, ticket.motivo_cierre = EstadoTicket.CERRADO, motivo
    return autor


def _tickets_de(azar, perfil, clientes, ahora, hoy):
    """``TICKETS_POR_MAESTRO`` tickets del maestro: pasados (finalizados o cerrados) y futuros
    (uno aceptado y pendientes). Cada ocurrencia se usa una sola vez, así nunca se cruzan dos aceptados."""
    servicios = list(ServicioMaestro.objects.filter(maestro=perfil, retirado_en__isnull=True))
    comunas = list(Cobertura.objects.filter(maestro=perfil).values_list("comuna_id", flat=True))
    patrones = list(Disponibilidad.objects.filter(maestro=perfil, retirado_en__isnull=True))
    pasadas = [
        o for o in ocurrencias.ocurrencias(patrones, hoy - datetime.timedelta(days=DIAS_HISTORIA), DIAS_HISTORIA)
        if o.fin_en < ahora
    ]
    futuras = [
        o for o in ocurrencias.ocurrencias(patrones, hoy, ocurrencias.HORIZONTE_DIAS)
        if ocurrencias.empieza_con_anticipacion(o, ahora)
    ]
    futuras = azar.sample(futuras, min(len(futuras), FUTUROS_POR_MAESTRO))
    pasadas = azar.sample(pasadas, min(len(pasadas), TICKETS_POR_MAESTRO - len(futuras)))
    resultado = []  # (ticket, [(fecha, anterior, nuevo, autor, motivo)])
    for indice, una in enumerate(futuras):
        cliente = azar.choice(clientes)
        enviado = ahora - datetime.timedelta(minutes=azar.randint(1, 600))
        if indice == 0:
            ticket = _ticket(azar, perfil, cliente, servicios, comunas, una, EstadoTicket.ACEPTADO, enviado)
            ticket.aceptado_en = _entre(azar, enviado, ahora)
            pasos = [(ticket.aceptado_en, EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO, perfil.pk, None)]
        else:
            ticket = _ticket(azar, perfil, cliente, servicios, comunas, una, EstadoTicket.PENDIENTE, enviado)
            pasos = []
        resultado.append((ticket, pasos))
    for una in pasadas:
        cliente = azar.choice(clientes)
        enviado = una.inicio_en - datetime.timedelta(hours=azar.randint(5, 72))
        if azar.random() < 0.6:
            ticket = _ticket(azar, perfil, cliente, servicios, comunas, una, EstadoTicket.FINALIZADO, enviado)
            ticket.aceptado_en = _entre(azar, enviado, ticket.vence_en)
            ticket.finalizado_en = una.fin_en + datetime.timedelta(hours=1)
            # Precio final coherente con el CHECK de ADR-026, E-1: el monto publicado, aceptado si es por hora.
            ticket.monto_final, ticket.monto_final_en = ticket.monto_publicado, ticket.finalizado_en
            ticket.monto_final_autor_id = perfil.pk
            if ticket.modalidad == Modalidad.POR_HORA:
                ticket.precio_aceptado_en = ticket.finalizado_en
            pasos = [
                (ticket.aceptado_en, EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO, perfil.pk, None),
                (ticket.finalizado_en, EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO, perfil.pk, None),
            ]
        else:
            ticket = _ticket(azar, perfil, cliente, servicios, comunas, una, EstadoTicket.PENDIENTE, enviado)
            autor = _cerrar(azar, ticket)
            pasos = [(ticket.cerrado_en, EstadoTicket.PENDIENTE, EstadoTicket.CERRADO, autor, ticket.motivo_cierre)]
        resultado.append((ticket, pasos))
    return resultado


def generar_tickets(semilla, maestros, ahora=None):
    """Tickets ficticios de los maestros de la semilla: ``TICKETS_POR_MAESTRO`` por maestro (1.000 para 100).

    Crea antes ``CLIENTES_POR_MAESTRO`` clientes ficticios por maestro. Idempotente:
    si los clientes de la semilla ya tienen tickets, no crea nada. Cada ticket
    lleva su historial coherente en ``ticket_evento``. Sin avisos: nadie entra
    con estas cuentas. Devuelve cuántos tickets creó.
    """
    ahora = ahora or timezone.now()
    hoy = vigencia.hoy_negocio(ahora)
    ruts = [rut_ficticio(semilla, numero).replace("-", "") for numero in range(maestros)]
    perfiles = list(PerfilMaestro.objects.filter(rut__in=ruts).order_by("rut"))
    if not perfiles:
        return 0
    clientes = [crear_cliente(semilla, numero) for numero in range(CLIENTES_POR_MAESTRO * len(perfiles))]
    if Ticket.objects.filter(cliente_id__in=[c.pk for c in clientes]).exists():
        return 0
    azar = random.Random(f"{semilla}-tickets")
    planes = [plan for perfil in perfiles for plan in _tickets_de(azar, perfil, clientes, ahora, hoy)]
    with transaction.atomic():
        creados = Ticket.objects.bulk_create([ticket for ticket, _ in planes])
        eventos = []
        for ticket, pasos in planes:
            eventos.append(_evento(ticket, ticket.enviado_en, None, EstadoTicket.PENDIENTE, ticket.cliente_id))
            eventos += [_evento(ticket, fecha, anterior, nuevo, autor, motivo)
                        for fecha, anterior, nuevo, autor, motivo in pasos]
        TicketEvento.objects.bulk_create(eventos)
    return len(creados)


def generar_conversaciones(semilla, maestros, ahora=None):
    """Mensajes y evaluaciones ficticios sobre los tickets de la semilla (S5, incremento 8; RNF-03).

    ``MENSAJES_POR_MAESTRO`` mensajes por maestro (5.000 para 100), repartidos al azar entre sus tickets
    aceptados y finalizados (las conversaciones quedan de tamaños distintos), entre la aceptación y el
    fin (o ahora). Evaluaciones en parte de los finalizados (del cliente y, a veces, del maestro), con
    notas de 1 a 5 y sin comentario. Idempotente por separado: si alguno de esos tickets ya tiene
    mensajes (o evaluaciones), no crea más de ese tipo. Devuelve ``(mensajes, evaluaciones)`` creados.
    """
    ahora = ahora or timezone.now()
    ruts = [rut_ficticio(semilla, numero).replace("-", "") for numero in range(maestros)]
    perfiles = list(PerfilMaestro.objects.filter(rut__in=ruts).order_by("rut"))
    tickets = list(
        Ticket.objects.filter(
            perfil_maestro_id__in=[p.pk for p in perfiles],
            estado__in=[EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO],
            cliente__usuario__correo__startswith=f"cliente.ficticio.{semilla}.",
        ).order_by("id")
    )
    if not tickets:
        return 0, 0
    azar = random.Random(f"{semilla}-conversaciones")
    ids = [t.pk for t in tickets]
    mensajes = []
    if not Mensaje.objects.filter(ticket_id__in=ids).exists():
        por_maestro = {}
        for t in tickets:
            por_maestro.setdefault(t.perfil_maestro_id, []).append(t)
        for lista in por_maestro.values():
            for n in range(MENSAJES_POR_MAESTRO):
                t = azar.choice(lista)
                fin = min(t.finalizado_en or ahora, ahora)
                mensajes.append(
                    Mensaje(
                        ticket_id=t.pk,
                        autor_id=azar.choice([t.cliente_id, t.perfil_maestro_id]),
                        texto=f"Mensaje ficticio {n + 1} del volumen de prueba.",
                        enviado_en=_entre(azar, t.aceptado_en, max(fin, t.aceptado_en + datetime.timedelta(seconds=1))),
                        clave_envio=uuid.UUID(int=azar.getrandbits(128), version=4),
                    )
                )
    evaluaciones = []
    if not Evaluacion.objects.filter(ticket_id__in=ids).exists():
        for t in tickets:
            if t.estado != EstadoTicket.FINALIZADO:
                continue
            for parte, prob, autor, evaluado in (
                (ParteEvaluacion.CLIENTE, PROBABILIDAD_EVAL_CLIENTE, t.cliente_id, t.perfil_maestro_id),
                (ParteEvaluacion.MAESTRO, PROBABILIDAD_EVAL_MAESTRO, t.perfil_maestro_id, t.cliente_id),
            ):
                if azar.random() < prob:
                    evaluaciones.append(
                        Evaluacion(
                            ticket_id=t.pk, parte=parte, autor_id=autor, evaluado_id=evaluado,
                            puntualidad=azar.randint(3, 5), trabajo=azar.randint(2, 5),
                            cordialidad=azar.randint(3, 5), creada_en=t.finalizado_en,
                        )
                    )
    with transaction.atomic():
        Mensaje.objects.bulk_create(mensajes, batch_size=1000)
        Evaluacion.objects.bulk_create(evaluaciones, batch_size=1000)
    return len(mensajes), len(evaluaciones)


class Command(BaseCommand):
    help = "Genera el volumen de prueba FICTICIO (100 maestros, 300 servicios, 1.000 tickets). Solo para una pila aparte."

    def add_arguments(self, parser):
        parser.add_argument("--semilla", type=int, required=True)
        parser.add_argument("--confirmo-datos-ficticios", action="store_true", dest="confirmo")
        # Solo para las pruebas automáticas; el volumen del informe es 100.
        parser.add_argument("--maestros", type=int, default=MAESTROS, help="Cantidad de maestros (por defecto 100).")

    def handle(self, *args, semilla, confirmo, maestros, **opciones):
        if not confirmo:
            raise CommandError(
                "Este comando crea datos ficticios de volumen. Úsalo solo en una pila aparte "
                "(docker compose -p altiro-volumen) y confírmalo con --confirmo-datos-ficticios."
            )
        if not 1 <= maestros <= 999:
            raise CommandError("La cantidad de maestros debe estar entre 1 y 999.")
        cargar_datos_demo()
        por_oficio = _servicios_por_oficio()
        if len(por_oficio) < 2:
            raise CommandError("El catálogo no tiene servicios suficientes de oficios no regulados.")
        creados = sum(crear_maestro(semilla, numero, por_oficio) for numero in range(maestros))
        tickets = generar_tickets(semilla, maestros)
        mensajes, evaluaciones = generar_conversaciones(semilla, maestros)
        logger.info(
            "Volumen de prueba ficticio generado: %s maestros nuevos, %s tickets, %s mensajes, %s evaluaciones.",
            creados, tickets, mensajes, evaluaciones,
        )
        self.stdout.write(
            f"Maestros ficticios nuevos: {creados} de {maestros} (semilla {semilla}). "
            f"Tickets ficticios nuevos: {tickets}. Mensajes ficticios nuevos: {mensajes}. "
            f"Evaluaciones ficticias nuevas: {evaluaciones}."
        )
