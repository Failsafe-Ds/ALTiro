"""Comuna del perfil de cliente (RF-01, ADR-012) e intentos fallidos (RNF-10, ADR-007).

``perfil_cliente.comuna_codigo`` es NOT NULL sin valor por defecto: antes de
esta migración ninguna vía creaba perfiles de cliente, así que no hay filas
que completar. Si existieran, la migración falla en vez de inventar una comuna.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identidad", "0001_inicial"),
        ("territorio", "0002_carga_cut_2018"),
    ]

    operations = [
        migrations.AddField(
            model_name="perfilcliente",
            name="comuna",
            field=models.ForeignKey(
                db_column="comuna_codigo",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="territorio.comuna",
            ),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name="IntentoAutenticacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origen", models.GenericIPAddressField()),
                ("clave", models.CharField(max_length=64)),
                ("fecha", models.DateTimeField()),
            ],
            options={
                "db_table": "intento_autenticacion",
                "indexes": [
                    models.Index(fields=["origen", "fecha"], name="intento_origen_fecha"),
                    models.Index(fields=["fecha"], name="intento_fecha"),
                ],
            },
        ),
    ]
