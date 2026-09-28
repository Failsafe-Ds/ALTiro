"""Catálogo mínimo de oficios (ADR-017, punto 1; RF-33; DA-15).

Solo lectura desde la aplicación: lo carga la migración ``0002_carga_oficios``
desde ``catalogo/datos/oficios.csv`` y no hay endpoints de escritura. Es un
adelanto de datos del S3: la administración del catálogo (RF-36) sigue en S3.
``regulado`` indica que el oficio exige licencia SEC para aprobarse (RF-33).
"""
from django.db import models


class Oficio(models.Model):
    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=100)
    regulado = models.BooleanField()
    # Orden en que se muestra la lista.
    orden = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "oficio"
        ordering = ["orden", "codigo"]

    def __str__(self):
        return self.nombre
