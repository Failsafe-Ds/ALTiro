"""Agrega el oficio «Otros servicios» (DA-31, PROVISIONAL; ADR-017, punto 1).

Mismo dato que la fila ``otros`` del CSV de oficios: en una base nueva ya lo
insertó ``0002``; en una base existente lo inserta esta migración. No relee el
CSV (ADR-018, punto 3: el CSV es solo la carga inicial), así que los valores
van fijos aquí.

Idempotente: solo inserta si el código no existe; nunca pisa lo que comercial
haya cambiado. Reversible: la reversa borra la fila solo si nadie la usa;
si un maestro ya lo declaró, la reversa falla (PROTECT) y no borra nada.
"""
import uuid

from django.db import migrations

CODIGO = "otros"
NOMBRE = "Otros servicios"
ORDEN = 9


def agregar_oficio(apps, schema_editor):
    Oficio = apps.get_model("catalogo", "Oficio")
    if not Oficio.objects.filter(codigo=CODIGO).exists():
        Oficio.objects.create(codigo=CODIGO, nombre=NOMBRE, regulado=False, orden=ORDEN, ref=uuid.uuid4())


def quitar_oficio(apps, schema_editor):
    Oficio = apps.get_model("catalogo", "Oficio")
    Oficio.objects.filter(codigo=CODIGO).delete()


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0007_servicio")]

    operations = [migrations.RunPython(agregar_oficio, quitar_oficio)]
