"""Purga por retención de ``acceso_denegado`` (M-08; ADR-010, «Decisión», punto 3).

Borra las filas con más de 90 días. El planificador del actor Sistema la corre
cada hora (``autorizacion.tareas``; ADR-016); también se puede ejecutar a mano:

    python manage.py purgar_accesos_denegados
"""
from django.core.management.base import BaseCommand

from autorizacion.acceso_denegado import purgar_vencidos


class Command(BaseCommand):
    help = "Borra los registros de accesos denegados con más de 90 días (retención, M-08)."

    def handle(self, *args, **opciones):
        borradas = purgar_vencidos()
        self.stdout.write(f"Registros de accesos denegados eliminados por retención: {borradas}.")
