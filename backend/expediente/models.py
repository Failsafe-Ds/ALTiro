"""Expediente del maestro y oficios declarados (ADR-017; propuesta del S2, §3).

- ``Expediente``: uno por ``perfil_maestro`` (invariante perfil_maestro <=>
  expediente, verificado por ``identidad.servicios.verificar_invariantes``).
  Se crea en la misma transacción que el perfil (``expediente.servicios.crear_para``).
  ``ref`` es el identificador público (ADR-011); la clave numérica es interna.
- ``OficioMaestro``: oficios que el maestro declara; editable solo en
  ``en_revision`` u ``observado`` (``expediente.servicios.declarar_oficios``).

Sin borrado en cascada (PROTECT): la trazabilidad del expediente no se pierde
al borrar un perfil o un usuario.
"""
import uuid

from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.utils import timezone

from catalogo.models import Oficio
from identidad.models import PerfilMaestro, Usuario


class EstadoExpediente(models.TextChoices):
    """ADR-017, punto 2. ``rechazado`` es terminal."""

    EN_REVISION = "en_revision", "En revisión"
    OBSERVADO = "observado", "Observado"
    APROBADO = "aprobado", "Aprobado"
    RECHAZADO = "rechazado", "Rechazado"
    SUSPENDIDO = "suspendido", "Suspendido"


# Estados en que el maestro puede cambiar su declaración de oficios (propuesta del S2, §3).
ESTADOS_EDITABLES = frozenset({EstadoExpediente.EN_REVISION, EstadoExpediente.OBSERVADO})


class Expediente(models.Model):
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    perfil_maestro = models.OneToOneField(
        PerfilMaestro,
        on_delete=models.PROTECT,
        related_name="expediente",
        db_column="perfil_maestro_id",
    )
    estado = models.CharField(
        max_length=20, choices=EstadoExpediente.choices, default=EstadoExpediente.EN_REVISION
    )
    # Motivo del último cambio de estado (CA-19.1). Vacío mientras nadie lo cambió.
    estado_motivo = models.TextField(default="", blank=True)
    estado_cambiado_en = models.DateTimeField(null=True, blank=True)
    # Quién cambió el estado (curatoría). Nunca se entrega al maestro (ADR-010, E-1).
    estado_cambiado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="estado_cambiado_por_id",
    )
    creado_en = models.DateTimeField(default=timezone.now, db_default=Now())

    class Meta:
        db_table = "expediente"
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=[valor for valor, _ in EstadoExpediente.choices]),
                name="expediente_estado_valido",
            ),
            # Todo cambio de estado con autor exige un motivo escrito (RF-32, CA-19.1).
            models.CheckConstraint(
                condition=Q(estado_cambiado_por__isnull=True) | Q(estado_motivo__regex=r"\S"),
                name="expediente_motivo_con_autor",
            ),
        ]

    def __str__(self):
        # Sin datos personales: este texto puede terminar en registros.
        return f"Expediente {self.ref}"


class OficioMaestro(models.Model):
    """Oficio declarado por un maestro. Un oficio no se repite para un maestro."""

    # Sin índice propio: lo cubre oficio_maestro_unico (perfil_maestro_id, oficio_id).
    maestro = models.ForeignKey(
        PerfilMaestro,
        on_delete=models.PROTECT,
        related_name="oficios",
        db_column="perfil_maestro_id",
        db_index=False,
    )
    oficio = models.ForeignKey(Oficio, on_delete=models.PROTECT, related_name="+", db_column="oficio_id")

    class Meta:
        db_table = "oficio_maestro"
        constraints = [
            models.UniqueConstraint(fields=["maestro", "oficio"], name="oficio_maestro_unico"),
        ]

    def __str__(self):
        return f"Oficio {self.oficio_id} del maestro {self.maestro_id}"
