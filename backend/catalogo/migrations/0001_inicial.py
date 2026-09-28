"""Catálogo mínimo de oficios, de solo lectura (ADR-017, punto 1). Generada por Django 5.2.17."""

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Oficio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=40, unique=True)),
                ('nombre', models.CharField(max_length=100)),
                ('regulado', models.BooleanField()),
                ('orden', models.PositiveSmallIntegerField()),
            ],
            options={
                'db_table': 'oficio',
                'ordering': ['orden', 'codigo'],
            },
        ),
    ]
