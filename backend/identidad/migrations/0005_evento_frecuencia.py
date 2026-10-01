"""Eventos del limitador de frecuencia (ADR-007, E-1)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('identidad', '0004_solicitud_recuperacion'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventoFrecuencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ambito', models.CharField(max_length=20)),
                ('clave', models.CharField(max_length=64)),
                ('fecha', models.DateTimeField()),
            ],
            options={
                'db_table': 'evento_frecuencia',
                'indexes': [
                    models.Index(fields=['ambito', 'clave', 'fecha'], name='frecuencia_ambito_clave'),
                    models.Index(fields=['fecha'], name='frecuencia_fecha'),
                ],
            },
        ),
    ]
