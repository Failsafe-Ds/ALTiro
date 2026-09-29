"""Perfil público y servicios del maestro (RF-05, HU-12; ADR-019; ADR-021).

- ``PerfilPublico``: uno por ``perfil_maestro`` (invariante verificado por
  ``identidad.servicios.verificar_invariantes``), creado en la misma
  transacción que el perfil (``perfil.servicios.crear_perfil_publico_para``).
  ``ref`` es la referencia pública propia, distinta de la del expediente
  (ADR-019, punto 5). ``foto`` es el nombre UUID de la foto (ADR-021), que se
  sube en el incremento 5; mientras tanto queda nula.
- ``ServicioMaestro``: servicio del catálogo que el maestro ofrece, con su
  modalidad y monto (ADR-019, punto 1). Uno activo por (maestro, servicio);
  baja lógica con ``retirado_en``. Sin FK hacia ``oficio_maestro``: si el
  maestro deja de declarar el oficio, el servicio deja de ser visible por
  cálculo (``perfil.publicacion``). No se guarda ninguna marca de visibilidad
  (ADR-019, punto 2).

Sin borrado en cascada (PROTECT).
"""
import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from catalogo.models import MONTO_MAXIMO, Modalidad, Servicio
from identidad.models import PerfilMaestro


class PerfilPublico(models.Model):
    perfil_maestro = models.OneToOneField(
        PerfilMaestro, on_delete=models.PROTECT, related_name="perfil_publico", db_column="perfil_maestro_id"
    )
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    foto = models.UUIDField(null=True, blank=True, unique=True)
    foto_actualizada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "perfil_publico"
        constraints = [
            models.CheckConstraint(
                condition=Q(foto__isnull=True) | Q(foto_actualizada_en__isnull=False),
                name="perfil_publico_foto_con_fecha",
            ),
        ]

    def __str__(self):
        # Sin datos personales: este texto puede terminar en registros.
        return f"Perfil público {self.ref}"


class ServicioMaestro(models.Model):
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # Sin índice propio: lo cubre el único parcial (perfil_maestro_id, servicio_id).
    maestro = models.ForeignKey(
        PerfilMaestro,
        on_delete=models.PROTECT,
        related_name="servicios",
        db_column="perfil_maestro_id",
        db_index=False,
    )
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="+", db_column="servicio_id")
    modalidad = models.CharField(max_length=20, choices=Modalidad.choices)
    # Pesos, entero (ADR-019, punto 1).
    monto = models.PositiveIntegerField()
    creado_en = models.DateTimeField(default=timezone.now)
    actualizado_en = models.DateTimeField(default=timezone.now)
    retirado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "servicio_maestro"
        constraints = [
            models.CheckConstraint(
                condition=Q(modalidad__in=[valor for valor, _ in Modalidad.choices]),
                name="servicio_maestro_modalidad_valida",
            ),
            models.CheckConstraint(
                condition=Q(monto__gt=0) & Q(monto__lte=MONTO_MAXIMO), name="servicio_maestro_monto_valido"
            ),
            # Un servicio activo por (maestro, servicio del catálogo) (ADR-019, punto 1).
            models.UniqueConstraint(
                fields=["maestro", "servicio"],
                condition=Q(retirado_en__isnull=True),
                name="servicio_maestro_activo_unico",
            ),
        ]

    def __str__(self):
        return f"Servicio del maestro {self.ref}"
