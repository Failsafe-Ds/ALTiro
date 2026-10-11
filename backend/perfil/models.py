"""Perfil público y servicios del maestro (RF-05, HU-12; ADR-019; ADR-021).

- ``PerfilPublico``: uno por ``perfil_maestro`` (invariante verificado por
  ``identidad.servicios.verificar_invariantes``), creado en la misma
  transacción que el perfil (``perfil.servicios.crear_perfil_publico_para``).
  ``ref`` es la referencia pública propia, distinta de la del expediente
  (ADR-019, punto 5). ``foto`` es el nombre UUID de la foto (ADR-021): sus
  variantes están en ``settings.ALTIRO_FOTOS_DIR`` (``perfil.fotos``).
  ``descripcion`` es el «Sobre mí» opcional (DA-30).
- ``ServicioMaestro``: servicio del catálogo que el maestro ofrece, con su
  modalidad y monto (ADR-019, punto 1). Uno activo por (maestro, servicio);
  baja lógica con ``retirado_en``. Sin FK hacia ``oficio_maestro``: si el
  maestro deja de declarar el oficio, el servicio deja de ser visible por
  cálculo (``perfil.publicacion``). No se guarda ninguna marca de visibilidad
  (ADR-019, punto 2).
- ``Cobertura``: comunas que atiende el maestro, con una comuna base
  (RF-06, CA-13.1; ADR-019, punto 4).
- ``Disponibilidad``: bloques semanales de 24 h (RF-07; ADR-020).

Sin borrado en cascada (PROTECT).
"""
import uuid

from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Mod
from django.db.models.lookups import Exact
from django.utils import timezone

from catalogo.models import MONTO_MAXIMO, Modalidad, Servicio
from identidad.models import PerfilMaestro
from territorio.models import Comuna

DESCRIPCION_LARGO_MAXIMO = 500


class PerfilPublico(models.Model):
    perfil_maestro = models.OneToOneField(
        PerfilMaestro, on_delete=models.PROTECT, related_name="perfil_publico", db_column="perfil_maestro_id"
    )
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    foto = models.UUIDField(null=True, blank=True, unique=True)
    foto_actualizada_en = models.DateTimeField(null=True, blank=True)
    # «Sobre mí» (DA-30): texto opcional del maestro, recortado y validado con
    # ``comun.texto``; vacío si no lo escribió. No entra a la búsqueda ni al puntaje.
    descripcion = models.CharField(max_length=DESCRIPCION_LARGO_MAXIMO, blank=True, default="")

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
        indexes = [
            # Búsqueda: servicios activos de un servicio del catálogo (RF-09, RNF-01; ADR-022, punto 7).
            models.Index(
                fields=["servicio", "maestro"],
                condition=Q(retirado_en__isnull=True),
                name="servicio_maestro_activo_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(modalidad__in=Modalidad.values),
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


# --- Cobertura (RF-06, HU-13, CA-13.1; ADR-019, punto 4) ---


class Cobertura(models.Model):
    """Comuna que atiende el maestro; exactamente una es su comuna base (CA-13.1).

    Se reemplaza completa en cada guardado (``perfil.cobertura``). La comuna
    viene del catálogo territorial (ADR-012). "Exactamente una base" lo
    garantizan el servicio (que exige una) y el único parcial (que impide dos).
    """

    # Sin índice propio: lo cubre el UNIQUE (perfil_maestro_id, comuna_codigo).
    maestro = models.ForeignKey(
        PerfilMaestro,
        on_delete=models.PROTECT,
        related_name="coberturas",
        db_column="perfil_maestro_id",
        db_index=False,
    )
    # Sin índice propio: lo cubre cobertura_comuna_maestro_idx (búsqueda por comuna, ADR-022).
    comuna = models.ForeignKey(
        Comuna, on_delete=models.PROTECT, related_name="+", db_column="comuna_codigo", db_index=False
    )
    es_base = models.BooleanField(default=False)

    class Meta:
        db_table = "cobertura"
        indexes = [
            # Búsqueda: maestros que atienden una comuna (RF-09, RNF-01; ADR-022, punto 7).
            models.Index(fields=["comuna", "maestro"], name="cobertura_comuna_maestro_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["maestro", "comuna"], name="cobertura_comuna_unica"),
            models.UniqueConstraint(
                fields=["maestro"], condition=Q(es_base=True), name="cobertura_una_comuna_base"
            ),
        ]

    def __str__(self):
        return f"Cobertura {self.pk}"


# --- Disponibilidad semanal (RF-07, HU-14, CA-14.1, CA-14.2; ADR-020) ---

MINUTOS_DIA = 24 * 60
GRANULARIDAD_MINUTOS = 30


class Disponibilidad(models.Model):
    """Bloque semanal declarado por el maestro (ADR-020, puntos 1, 2 y 4).

    ``dia_semana`` ISO (1 = lunes ... 7 = domingo); minutos desde la
    medianoche, en múltiplos de 30, con ``0 <= inicio < fin <= 1440``: un
    bloque no cruza la medianoche (CA-14.2). Las filas no se modifican: se dan
    de baja con ``retirado_en`` y se crea otra. El solapamiento con otros
    bloques activos lo impide el servicio (``perfil.agenda``).
    """

    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    maestro = models.ForeignKey(
        PerfilMaestro,
        on_delete=models.PROTECT,
        related_name="disponibilidades",
        db_column="perfil_maestro_id",
        db_index=False,
    )
    dia_semana = models.PositiveSmallIntegerField()
    inicio_min = models.PositiveSmallIntegerField()
    fin_min = models.PositiveSmallIntegerField()
    creado_en = models.DateTimeField(default=timezone.now)
    retirado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "disponibilidad"
        indexes = [
            models.Index(
                fields=["maestro", "dia_semana"],
                condition=Q(retirado_en__isnull=True),
                name="disponibilidad_activa_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(dia_semana__gte=1) & Q(dia_semana__lte=7), name="disponibilidad_dia_semana_iso"
            ),
            models.CheckConstraint(
                condition=Q(inicio_min__gte=0) & Q(inicio_min__lt=F("fin_min")) & Q(fin_min__lte=MINUTOS_DIA),
                name="disponibilidad_rango_valido",
            ),
            models.CheckConstraint(
                condition=(
                    Exact(Mod("inicio_min", GRANULARIDAD_MINUTOS), 0) & Exact(Mod("fin_min", GRANULARIDAD_MINUTOS), 0)
                ),
                name="disponibilidad_multiplo_de_30",
            ),
        ]

    def __str__(self):
        return f"Disponibilidad {self.ref}"
