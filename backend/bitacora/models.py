"""Bitácora administrativa (RNF-11, RF-37, CA-19.3, HU-19; ADR-010).

Alcance: acciones administrativas sobre expedientes, evaluaciones y catálogo
(RF-37). No registra actividad general de la persona (M-03), ni la asignación
de roles administrativos, ni los accesos denegados (``acceso_denegado``).

La tabla se crea con SQL explícito en la migración (``managed=False``,
ADR-010, «Decisión», punto 4): sin FK hacia ``usuario``, con CHECK de
coherencia del autor y triggers que rechazan UPDATE, DELETE y TRUNCATE. Sin
purga. No hay rutas de la API para esta tabla.
"""
from django.db import models

from comun.solo_insercion import ModeloSoloInsercion


class AutorTipo(models.TextChoices):
    """``sistema`` se reserva para tareas programadas del actor Sistema (§3.1)."""

    USUARIO = "usuario", "Usuario"
    SISTEMA = "sistema", "Sistema"


class Bitacora(ModeloSoloInsercion):
    id = models.BigAutoField(primary_key=True)
    fecha = models.DateTimeField()
    autor_tipo = models.CharField(max_length=10, choices=AutorTipo.choices)
    # Sin FK (ADR-010, «Decisión», punto 4).
    autor_id = models.BigIntegerField(null=True)
    accion = models.CharField(max_length=60)
    entidad = models.CharField(max_length=40)
    entidad_ref = models.CharField(max_length=64)
    valor_anterior = models.JSONField(null=True)
    valor_nuevo = models.JSONField(null=True)
    motivo = models.TextField()

    class Meta:
        managed = False
        db_table = "bitacora"

    def __str__(self):
        return f"Entrada de bitácora {self.pk}"
