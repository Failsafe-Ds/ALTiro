"""Catálogo territorial: lista cerrada de regiones, provincias y comunas (RF-01, ADR-012).

Claves = Códigos Únicos Territoriales (CUT 2018). Solo lectura desde la
aplicación: lo carga la migración ``0002_carga_cut_2018`` desde
``territorio/datos/cut_2018.csv`` y no hay endpoints de escritura.
"""
from django.db import models


class Region(models.Model):
    codigo = models.PositiveSmallIntegerField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    # Orden de norte a sur para mostrar la lista (el código CUT no lo sigue).
    orden = models.PositiveSmallIntegerField(unique=True)

    class Meta:
        db_table = "region"
        ordering = ["orden"]

    def __str__(self):
        return self.nombre


class Provincia(models.Model):
    codigo = models.PositiveSmallIntegerField(primary_key=True)
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="provincias", db_column="region_codigo"
    )
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = "provincia"
        constraints = [
            models.UniqueConstraint(fields=["region", "nombre"], name="provincia_nombre_unico_en_region"),
        ]

    def __str__(self):
        return self.nombre


class Comuna(models.Model):
    codigo = models.PositiveIntegerField(primary_key=True)
    provincia = models.ForeignKey(
        Provincia, on_delete=models.PROTECT, related_name="comunas", db_column="provincia_codigo"
    )
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = "comuna"
        constraints = [
            models.UniqueConstraint(fields=["provincia", "nombre"], name="comuna_nombre_unico_en_provincia"),
        ]

    def __str__(self):
        return self.nombre
