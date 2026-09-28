"""Modelos de solo inserción (RNF-11, ADR-010, barrera 1).

La aplicación no ofrece ninguna forma de editar ni borrar estas filas:

- ``save()`` solo inserta; sobre una fila ya guardada lanza un error.
- ``delete()`` del modelo lanza un error.
- ``update()`` y ``delete()`` del QuerySet lanzan un error (también cubren
  ``bulk_update``, que usa ``update``).

Los triggers de PostgreSQL de cada tabla son defensa en profundidad (barrera 2).
La purga por retención de ``acceso_denegado`` (M-08) usa SQL directo en
``autorizacion.acceso_denegado.purgar_vencidos`` y el trigger la acota.
"""
from django.db import models


class OperacionNoPermitida(Exception):
    """Intento de editar o borrar una fila de solo inserción desde la aplicación."""


class SoloInsercionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise OperacionNoPermitida("Este registro no se puede modificar.")

    def delete(self):
        raise OperacionNoPermitida("Este registro no se puede borrar.")


class ModeloSoloInsercion(models.Model):
    """Base abstracta: solo se insertan filas nuevas."""

    objects = SoloInsercionQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None or kwargs.get("force_update") or kwargs.get("update_fields"):
            raise OperacionNoPermitida("Este registro no se puede modificar.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise OperacionNoPermitida("Este registro no se puede borrar.")
