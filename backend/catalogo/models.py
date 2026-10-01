"""Catálogo administrable de oficios, servicios y precios de referencia (RF-36, HU-20; ADR-017, punto 1; ADR-018).

- ``Oficio``: la carga inicial viene del CSV versionado (``catalogo.carga``,
  solo inserción, ADR-018 punto 3). Desde el S3 lo administra comercial
  (``catalogo.servicios``). ``regulado`` indica que el oficio exige licencia
  SEC (RF-33, RNF-25); es obligatorio al crear y no se cambia desde la
  aplicación (ADR-018, punto 2).
- ``Servicio``: servicio de un oficio que el maestro puede declarar (RF-05, CA-20.1).
- ``ServicioModalidad``: modalidades que admite un servicio, de la lista
  cerrada {por trabajo, por hora}, con su precio de referencia (ADR-018,
  punto 1). Todo servicio tiene al menos una (invariante del servicio de
  dominio ``catalogo.servicios``).

``ref`` es el identificador público (ADR-011). Sin borrado físico de oficios
ni servicios: las bajas son ``activo=False`` (ADR-018, punto 4). ``version``
detecta ediciones simultáneas (409).
"""
import uuid

from django.db import models
from django.db.models import Q

# Tope técnico de montos en pesos (ADR-019, punto 1: validación de entrada, no
# regla de negocio). Se usa también para el precio de referencia (supuesto).
MONTO_MAXIMO = 10_000_000


class Modalidad(models.TextChoices):
    """Lista cerrada de modalidades de precio (RF-05; ADR-018, punto 1)."""

    POR_TRABAJO = "por_trabajo", "Por trabajo"
    POR_HORA = "por_hora", "Por hora"


class Oficio(models.Model):
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=100)
    regulado = models.BooleanField()
    # Orden en que se muestra la lista.
    orden = models.PositiveSmallIntegerField()
    activo = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "oficio"
        ordering = ["orden", "codigo"]

    def __str__(self):
        return self.nombre


class Servicio(models.Model):
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    oficio = models.ForeignKey(Oficio, on_delete=models.PROTECT, related_name="servicios", db_column="oficio_id")
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "servicio"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["oficio", "nombre"], name="servicio_oficio_nombre_unico"),
            models.CheckConstraint(condition=Q(nombre__regex=r"\S"), name="servicio_nombre_no_vacio"),
        ]

    def __str__(self):
        return self.nombre


class ServicioModalidad(models.Model):
    servicio = models.ForeignKey(
        Servicio, on_delete=models.PROTECT, related_name="modalidades", db_column="servicio_id", db_index=False
    )
    modalidad = models.CharField(max_length=20, choices=Modalidad.choices)
    precio_referencia = models.PositiveIntegerField()

    class Meta:
        db_table = "servicio_modalidad"
        ordering = ["modalidad"]
        constraints = [
            models.UniqueConstraint(fields=["servicio", "modalidad"], name="servicio_modalidad_unica"),
            models.CheckConstraint(
                condition=Q(modalidad__in=Modalidad.values),
                name="servicio_modalidad_valida",
            ),
            models.CheckConstraint(
                condition=Q(precio_referencia__gt=0) & Q(precio_referencia__lte=MONTO_MAXIMO),
                name="servicio_modalidad_precio_valido",
            ),
        ]

    def __str__(self):
        return f"Modalidad {self.modalidad} del servicio {self.servicio_id}"
