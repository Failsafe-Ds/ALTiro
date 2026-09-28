"""Recurso ficticio con dueño (solo pruebas; propuesta del S1, §8: "política de control sobre un recurso ficticio")."""
import uuid

from django.db import models

from identidad.models import Usuario


class RecursoPrueba(models.Model):
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    dueno = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = "recurso_prueba"
