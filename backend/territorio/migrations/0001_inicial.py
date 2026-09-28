import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Region",
            fields=[
                ("codigo", models.PositiveSmallIntegerField(primary_key=True, serialize=False)),
                ("nombre", models.CharField(max_length=100, unique=True)),
                ("orden", models.PositiveSmallIntegerField(unique=True)),
            ],
            options={"db_table": "region", "ordering": ["orden"]},
        ),
        migrations.CreateModel(
            name="Provincia",
            fields=[
                ("codigo", models.PositiveSmallIntegerField(primary_key=True, serialize=False)),
                ("nombre", models.CharField(max_length=100)),
                (
                    "region",
                    models.ForeignKey(
                        db_column="region_codigo",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="provincias",
                        to="territorio.region",
                    ),
                ),
            ],
            options={"db_table": "provincia"},
        ),
        migrations.CreateModel(
            name="Comuna",
            fields=[
                ("codigo", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("nombre", models.CharField(max_length=100)),
                (
                    "provincia",
                    models.ForeignKey(
                        db_column="provincia_codigo",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comunas",
                        to="territorio.provincia",
                    ),
                ),
            ],
            options={"db_table": "comuna"},
        ),
        migrations.AddConstraint(
            model_name="provincia",
            constraint=models.UniqueConstraint(fields=("region", "nombre"), name="provincia_nombre_unico_en_region"),
        ),
        migrations.AddConstraint(
            model_name="comuna",
            constraint=models.UniqueConstraint(fields=("provincia", "nombre"), name="comuna_nombre_unico_en_provincia"),
        ),
    ]
