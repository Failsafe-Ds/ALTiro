"""Solicitudes de recuperación de contraseña (ADR-027, punto 3)."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('identidad', '0003_usuario_rol_asignado_en'),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitudRecuperacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origen', models.GenericIPAddressField()),
                ('via', models.CharField(choices=[('correo', 'Por correo'), ('asistida', 'Asistida por un administrador')], max_length=10)),
                ('token_hash', models.CharField(blank=True, max_length=64, null=True)),
                ('creada_en', models.DateTimeField()),
                ('vence_en', models.DateTimeField(blank=True, null=True)),
                ('usada_en', models.DateTimeField(blank=True, null=True)),
                ('anulada_en', models.DateTimeField(blank=True, null=True)),
                ('usuario', models.ForeignKey(blank=True, db_column='usuario_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='identidad.usuario')),
            ],
            options={
                'db_table': 'solicitud_recuperacion',
                'indexes': [models.Index(fields=['origen', 'creada_en'], name='recuperacion_origen_fecha'), models.Index(fields=['creada_en'], name='recuperacion_fecha')],
                'constraints': [models.UniqueConstraint(fields=('token_hash',), name='solicitud_recuperacion_token_unico'), models.CheckConstraint(condition=models.Q(('via__in', ['correo', 'asistida'])), name='solicitud_recuperacion_via_valida'), models.CheckConstraint(condition=models.Q(('token_hash__isnull', True), models.Q(('usuario__isnull', False), ('vence_en__isnull', False)), _connector='OR'), name='solicitud_recuperacion_enlace_completo')],
            },
        ),
    ]
