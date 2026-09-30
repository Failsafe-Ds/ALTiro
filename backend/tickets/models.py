"""Ticket y orden, historial y avisos (RF-15 a RF-24, RNF-07, RNF-08; ADR-023, puntos 1, 2 y 4; ADR-024, punto 1).

- ``Ticket``: el **mismo registro lógico** del ticket y de la orden (informe
  §2.3). ``id`` es el número visible, pero nunca va en una URL ni se acepta
  como entrada: las URL usan ``ref`` (ADR-011). Guarda copias de la modalidad
  y el monto publicados (RF-15) y del bloque pedido (``fecha``,
  ``inicio_min``, ``fin_min``), con sus instantes ``inicio_en`` y ``fin_en``
  (ADR-020, E-1). ``vence_en = LEAST(enviado_en + 24 h, inicio_en - 4 h)``.
  La base tiene CHECK de defensa (anticipación de RF-16, fórmula de
  ``vence_en``, rango, coherencia entre estado, motivo y fechas y
  ``cliente <> maestro`` de ADR-013, E-9) y dos únicos parciales (D-9, D-10).
- ``TicketEvento``: historial de estados, de **solo inserción** (patrón de
  ADR-010): tabla con SQL explícito, ``managed=False``, triggers que rechazan
  UPDATE, DELETE y TRUNCATE, y sin FK (ni de autor ni de ticket: una FK
  impediría el vaciado de las pruebas ``transaction=True``, igual que en
  ``bitacora``). No es la bitácora administrativa (RF-37, M-03).
- Precio final (RF-26 a RF-28; ADR-026, E-1): el valor vigente en ``ticket``
  (``monto_final``, su fecha y autor, y ``precio_aceptado_en``) y cada acción
  en ``PrecioFinalEvento``, de solo inserción con el mismo patrón de ADR-010.
- ``AvisoTicket``: avisos dentro de la aplicación (ADR-024). No guarda datos
  personales: el texto se arma al mostrarlo, con la serialización de quien lo lee.

Sin borrado en cascada (PROTECT).
"""
import datetime
import uuid

from django.db import models
from django.db.models import F, Q, Value
from django.db.models.functions import Cast, Least
from django.utils import timezone

from catalogo.models import MONTO_MAXIMO, Modalidad
from comun.solo_insercion import ModeloSoloInsercion
from identidad.models import PerfilCliente, PerfilMaestro, Usuario
from perfil.models import MINUTOS_DIA, ServicioMaestro
from territorio.models import Comuna

# ADR-023, punto 1. Los mismos literales están en el SQL de ``ticket_evento``.
PLAZO_RESPUESTA = datetime.timedelta(hours=24)  # RF-21
ANTICIPACION_MINIMA = datetime.timedelta(hours=4)  # RF-16, RF-22
LARGO_DIRECCION = 200
LARGO_DESCRIPCION = 1000


class EstadoTicket(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    ACEPTADO = "aceptado", "Aceptado"
    FINALIZADO = "finalizado", "Finalizado"
    CERRADO = "cerrado", "Cerrado"


# Estados que ocupan la agenda del maestro (CA-14.3; ADR-023, punto 4).
ESTADOS_QUE_OCUPAN = (EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO)


class MotivoCierre(models.TextChoices):
    """Los cinco motivos de cierre desde ``pendiente``, distinguibles (RF-24; ADR-023, punto 1)."""

    VENCIDO_PLAZO = "vencido_plazo", "Venció el plazo de respuesta"
    VENCIDO_PROXIMIDAD = "vencido_proximidad", "Faltaban 4 horas o menos"
    CANCELADO_CLIENTE = "cancelado_cliente", "Cancelado por el cliente"
    RECHAZADO_MAESTRO = "rechazado_maestro", "Rechazado por el maestro"
    BLOQUE_TOMADO = "bloque_tomado", "El maestro tomó otro trabajo en ese horario"


class AutorTipo(models.TextChoices):
    USUARIO = "usuario", "Usuario"
    SISTEMA = "sistema", "Sistema"


def _horas(delta):
    """Intervalo en **horas** para los CHECK (``'24 hours'``, no ``'1 day'``).

    En PostgreSQL, ``timestamptz + '1 day'`` suma un día de calendario en la
    zona de la sesión y no siempre equivale a 24 horas (horario de verano). Los
    plazos de ADR-020, E-1 son de tiempo real transcurrido.
    """
    return Cast(Value(f"{int(delta.total_seconds() // 3600)} hours"), models.DurationField())


def _valores(opciones):
    return [valor for valor, _ in opciones.choices]


class Ticket(models.Model):
    id = models.BigAutoField(primary_key=True)
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # Sin índices propios: los cubren los índices compuestos de Meta.
    cliente = models.ForeignKey(
        PerfilCliente, on_delete=models.PROTECT, related_name="+", db_column="cliente_id", db_index=False
    )
    perfil_maestro = models.ForeignKey(
        PerfilMaestro, on_delete=models.PROTECT, related_name="+", db_column="perfil_maestro_id", db_index=False
    )
    # El servicio publicado que el cliente eligió (ADR-023, punto 3; D-11).
    servicio_maestro = models.ForeignKey(
        ServicioMaestro, on_delete=models.PROTECT, related_name="+", db_column="servicio_maestro_id"
    )
    # Copias al enviar (RF-15): no cambian si el maestro cambia su publicación.
    modalidad = models.CharField(max_length=20, choices=Modalidad.choices)
    monto_publicado = models.PositiveIntegerField()
    # Copia del bloque (ADR-020) y sus instantes reales (ADR-020, E-1).
    fecha = models.DateField()
    inicio_min = models.PositiveSmallIntegerField()
    fin_min = models.PositiveSmallIntegerField()
    inicio_en = models.DateTimeField()
    fin_en = models.DateTimeField()
    # Datos del pedido (HU-06, CA-06.1, CA-06.4). ``materiales`` sin valor por defecto.
    comuna = models.ForeignKey(
        Comuna, on_delete=models.PROTECT, related_name="+", db_column="comuna_codigo", db_index=False
    )
    direccion = models.CharField(max_length=LARGO_DIRECCION)
    descripcion = models.CharField(max_length=LARGO_DESCRIPCION)
    materiales = models.BooleanField()
    estado = models.CharField(max_length=12, choices=EstadoTicket.choices)
    motivo_cierre = models.CharField(max_length=20, choices=MotivoCierre.choices, null=True, blank=True)
    enviado_en = models.DateTimeField()
    vence_en = models.DateTimeField()
    aceptado_en = models.DateTimeField(null=True, blank=True)
    finalizado_en = models.DateTimeField(null=True, blank=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    # Precio final vigente (RF-26, RF-27; ADR-026, E-1). El historial va en ``precio_final_evento``.
    monto_final = models.PositiveIntegerField(null=True, blank=True)
    monto_final_en = models.DateTimeField(null=True, blank=True)
    monto_final_autor = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name="+", db_column="monto_final_autor_id",
        null=True, blank=True, db_index=False,
    )
    precio_aceptado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ticket"
        indexes = [
            # "Mis pedidos" del cliente y "mis trabajos" del maestro, del más nuevo al más antiguo.
            models.Index(F("cliente"), F("enviado_en").desc(), name="ticket_cliente_enviado_idx"),
            models.Index(F("perfil_maestro"), F("enviado_en").desc(), name="ticket_maestro_enviado_idx"),
            # Tarea de cierre de pendientes vencidos (RF-21, RF-22; incremento 6).
            models.Index(
                fields=["vence_en"], condition=Q(estado=EstadoTicket.PENDIENTE), name="ticket_pendiente_vence_idx"
            ),
        ]
        constraints = [
            # ADR-013, E-9: nadie se pide un trabajo a sí mismo.
            models.CheckConstraint(condition=~Q(cliente=F("perfil_maestro")), name="ticket_cliente_no_es_maestro"),
            models.CheckConstraint(condition=Q(estado__in=_valores(EstadoTicket)), name="ticket_estado_valido"),
            models.CheckConstraint(
                condition=Q(motivo_cierre__isnull=True) | Q(motivo_cierre__in=_valores(MotivoCierre)),
                name="ticket_motivo_cierre_valido",
            ),
            # El motivo existe si y solo si el estado es cerrado (ADR-023, punto 1).
            models.CheckConstraint(
                condition=(Q(estado=EstadoTicket.CERRADO) & Q(motivo_cierre__isnull=False))
                | (~Q(estado=EstadoTicket.CERRADO) & Q(motivo_cierre__isnull=True)),
                name="ticket_motivo_solo_si_cerrado",
            ),
            models.CheckConstraint(condition=Q(modalidad__in=_valores(Modalidad)), name="ticket_modalidad_valida"),
            models.CheckConstraint(
                condition=Q(monto_publicado__gt=0) & Q(monto_publicado__lte=MONTO_MAXIMO),
                name="ticket_monto_publicado_valido",
            ),
            models.CheckConstraint(
                condition=Q(inicio_min__gte=0) & Q(inicio_min__lt=F("fin_min")) & Q(fin_min__lte=MINUTOS_DIA),
                name="ticket_rango_valido",
            ),
            models.CheckConstraint(condition=Q(inicio_en__lt=F("fin_en")), name="ticket_inicio_antes_de_fin"),
            # RF-16: el bloque empieza en más de 4 horas desde el envío.
            models.CheckConstraint(
                condition=Q(inicio_en__gt=F("enviado_en") + _horas(ANTICIPACION_MINIMA)),
                name="ticket_anticipacion_minima",
            ),
            # ADR-023, punto 1: vence_en = LEAST(enviado_en + 24 h, inicio_en - 4 h).
            models.CheckConstraint(
                condition=Q(
                    vence_en=Least(
                        F("enviado_en") + _horas(PLAZO_RESPUESTA), F("inicio_en") - _horas(ANTICIPACION_MINIMA)
                    )
                ),
                name="ticket_vence_en_formula",
            ),
            models.CheckConstraint(condition=Q(direccion__regex=r"\S"), name="ticket_direccion_no_vacia"),
            models.CheckConstraint(condition=Q(descripcion__regex=r"\S"), name="ticket_descripcion_no_vacia"),
            # Coherencia entre estado y fechas (ADR-023, punto 1). "cerrado" solo llega desde "pendiente".
            models.CheckConstraint(
                condition=(
                    Q(estado=EstadoTicket.PENDIENTE, aceptado_en__isnull=True, finalizado_en__isnull=True,
                      cerrado_en__isnull=True)
                    | Q(estado=EstadoTicket.ACEPTADO, aceptado_en__isnull=False, finalizado_en__isnull=True,
                        cerrado_en__isnull=True)
                    | Q(estado=EstadoTicket.FINALIZADO, aceptado_en__isnull=False, finalizado_en__isnull=False,
                        cerrado_en__isnull=True)
                    | Q(estado=EstadoTicket.CERRADO, aceptado_en__isnull=True, finalizado_en__isnull=True,
                        cerrado_en__isnull=False)
                ),
                name="ticket_fechas_segun_estado",
            ),
            # Se acepta antes del vencimiento (ADR-023, punto 3), después del envío.
            models.CheckConstraint(
                condition=Q(aceptado_en__isnull=True)
                | (Q(aceptado_en__gte=F("enviado_en")) & Q(aceptado_en__lt=F("vence_en"))),
                name="ticket_aceptado_en_plazo",
            ),
            models.CheckConstraint(
                condition=Q(cerrado_en__isnull=True) | Q(cerrado_en__gte=F("enviado_en")),
                name="ticket_cerrado_despues_de_enviado",
            ),
            models.CheckConstraint(
                condition=Q(finalizado_en__isnull=True) | Q(finalizado_en__gte=F("aceptado_en")),
                name="ticket_finalizado_despues_de_aceptado",
            ),
            # Precio final (ADR-026, E-1; propuesta del S5, §3.1).
            models.CheckConstraint(
                condition=Q(monto_final__isnull=True) | (Q(monto_final__gt=0) & Q(monto_final__lte=MONTO_MAXIMO)),
                name="ticket_monto_final_valido",
            ),
            # Monto, fecha y autor se registran juntos.
            models.CheckConstraint(
                condition=Q(monto_final__isnull=True, monto_final_en__isnull=True, monto_final_autor__isnull=True)
                | Q(monto_final__isnull=False, monto_final_en__isnull=False, monto_final_autor__isnull=False),
                name="ticket_monto_final_con_fecha_y_autor",
            ),
            models.CheckConstraint(
                condition=Q(precio_aceptado_en__isnull=True) | Q(monto_final__isnull=False),
                name="ticket_aceptacion_exige_monto_final",
            ),
            models.CheckConstraint(
                condition=Q(monto_final__isnull=True) | Q(estado__in=ESTADOS_QUE_OCUPAN),
                name="ticket_monto_final_solo_aceptado_o_finalizado",
            ),
            # RF-27, CA-16.2: finalizado exige monto final y, si no es el mismo monto por trabajo, la aceptación.
            models.CheckConstraint(
                condition=~Q(estado=EstadoTicket.FINALIZADO)
                | (
                    Q(monto_final__isnull=False)
                    & (
                        Q(modalidad=Modalidad.POR_TRABAJO, monto_final=F("monto_publicado"))
                        | Q(precio_aceptado_en__isnull=False)
                    )
                ),
                name="ticket_finalizado_con_precio",
            ),
            # D-9: un bloque aceptado o finalizado por maestro e inicio (el cruce de rangos lo
            # protege el bloqueo por maestro, ADR-023, punto 4; sin EXCLUDE gist).
            models.UniqueConstraint(
                fields=["perfil_maestro", "inicio_en"],
                condition=Q(estado__in=ESTADOS_QUE_OCUPAN),
                name="ticket_bloque_ocupado_unico",
            ),
            # D-10: un pendiente por cliente, maestro e inicio.
            models.UniqueConstraint(
                fields=["cliente", "perfil_maestro", "inicio_en"],
                condition=Q(estado=EstadoTicket.PENDIENTE),
                name="ticket_pendiente_unico",
            ),
        ]

    def __str__(self):
        # Sin datos personales: este texto puede terminar en registros.
        return f"Ticket {self.ref}"


class TicketEvento(ModeloSoloInsercion):
    """Cambio de estado de un ticket (ADR-023, punto 2). ``estado_anterior`` es NULL al crearlo."""

    id = models.BigAutoField(primary_key=True)
    # Sin FK (ver el docstring del módulo).
    ticket_id = models.BigIntegerField()
    fecha = models.DateTimeField()
    estado_anterior = models.CharField(max_length=12, null=True)
    estado_nuevo = models.CharField(max_length=12)
    motivo = models.CharField(max_length=20, null=True)
    autor_tipo = models.CharField(max_length=10, choices=AutorTipo.choices)
    autor_id = models.BigIntegerField(null=True)

    class Meta:
        managed = False
        db_table = "ticket_evento"

    def __str__(self):
        return f"Evento de ticket {self.pk}"


class AccionPrecio(models.TextChoices):
    REGISTRADO = "registrado", "Registrado por el maestro"
    ACEPTADO = "aceptado", "Aceptado por el cliente"
    OBJETADO = "objetado", "Objetado por el cliente"


class PrecioFinalEvento(ModeloSoloInsercion):
    """Cada acción sobre el precio final de un ticket (CA-16.1; ADR-026, E-1). Sin FK (patrón de ADR-010)."""

    id = models.BigAutoField(primary_key=True)
    ticket_id = models.BigIntegerField()
    accion = models.CharField(max_length=12, choices=AccionPrecio.choices)
    monto = models.PositiveIntegerField()
    autor_id = models.BigIntegerField()
    fecha = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "precio_final_evento"

    def __str__(self):
        return f"Evento de precio {self.pk}"


class TipoAvisoTicket(models.TextChoices):
    """ADR-024, punto 2; propuesta del S5, §3.1."""

    TICKET_NUEVO = "ticket_nuevo", "Pedido nuevo"
    TICKET_CERRADO = "ticket_cerrado", "Pedido cerrado"
    TICKET_ACEPTADO = "ticket_aceptado", "Pedido aceptado"
    PRECIO_REGISTRADO = "precio_registrado", "Precio por aceptar"
    PRECIO_OBJETADO = "precio_objetado", "Precio no aceptado"
    ORDEN_FINALIZADA = "orden_finalizada", "Trabajo terminado"
    MENSAJE_NUEVO = "mensaje_nuevo", "Mensaje nuevo"


class AvisoTicket(models.Model):
    """Aviso de un ticket para una de sus partes (ADR-024). Una sola emisión por (ticket, destinatario, tipo)."""

    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="+", db_column="ticket_id")
    # Sin índice propio: lo cubre aviso_ticket_destinatario_idx.
    destinatario = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name="+", db_column="destinatario_id", db_index=False
    )
    tipo = models.CharField(max_length=20, choices=TipoAvisoTicket.choices)
    creado_en = models.DateTimeField(default=timezone.now)
    visto_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "aviso_ticket"
        indexes = [
            models.Index(F("destinatario"), F("creado_en").desc(), name="aviso_ticket_destinatario_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(tipo__in=_valores(TipoAvisoTicket)), name="aviso_ticket_tipo_valido"),
            models.CheckConstraint(
                condition=Q(visto_en__isnull=True) | Q(visto_en__gte=F("creado_en")),
                name="aviso_ticket_visto_despues_de_creado",
            ),
            models.UniqueConstraint(fields=["ticket", "destinatario", "tipo"], name="aviso_ticket_una_vez"),
        ]

    def __str__(self):
        return f"Aviso de ticket {self.ref}"
