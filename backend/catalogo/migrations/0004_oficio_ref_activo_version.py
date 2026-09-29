"""Oficio: agrega ``ref`` (nulo por ahora), ``activo`` y ``version`` (ADR-018; ADR-011).

Paso 1 de 3 para ``ref``. No se usa ``AddField(UUIDField(default=uuid4))``:
Django evaluaría el valor por defecto una sola vez y asignaría el **mismo**
UUID a todas las filas existentes. ``0005`` llena un UUID distinto por fila y
``0006`` lo deja único y no nulo. Cada paso va en su propia migración (su
propia transacción) para no mezclar la actualización de filas con el cambio
de esquema.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0003_renombra_oficios_de_ejemplo")]

    operations = [
        migrations.AddField(model_name="oficio", name="ref", field=models.UUIDField(null=True, editable=False)),
        migrations.AddField(model_name="oficio", name="activo", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="oficio", name="version", field=models.PositiveIntegerField(default=1)),
    ]
