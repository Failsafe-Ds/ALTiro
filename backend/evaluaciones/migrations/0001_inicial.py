"""Evaluación y denuncia (S5, incrementos 5 y 6; ADR-026, E-3 y E-4; propuesta del S5, §3.1)."""

import django.db.models.deletion
import django.db.models.functions.text
import django.db.models.lookups
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('identidad', '0003_usuario_rol_asignado_en'),
        ('tickets', '0003_aviso_mensaje_nuevo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Evaluacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('parte', models.CharField(choices=[('cliente', 'Cliente'), ('maestro', 'Maestro')], max_length=10)),
                ('puntualidad', models.PositiveSmallIntegerField()),
                ('trabajo', models.PositiveSmallIntegerField()),
                ('cordialidad', models.PositiveSmallIntegerField()),
                ('comentario', models.CharField(blank=True, default='', max_length=500)),
                ('creada_en', models.DateTimeField(default=django.utils.timezone.now)),
                ('estado', models.CharField(choices=[('publicada', 'Publicada'), ('retirada', 'Retirada por moderación')], default='publicada', max_length=10)),
                ('autor', models.ForeignKey(db_column='autor_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='identidad.usuario')),
                ('evaluado', models.ForeignKey(db_column='evaluado_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='identidad.usuario')),
                ('ticket', models.ForeignKey(db_column='ticket_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='tickets.ticket')),
            ],
            options={
                'db_table': 'evaluacion',
            },
        ),
        migrations.CreateModel(
            name='Denuncia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('motivo', models.CharField(max_length=500)),
                ('creada_en', models.DateTimeField(default=django.utils.timezone.now)),
                ('estado', models.CharField(choices=[('abierta', 'En revisión'), ('resuelta', 'Resuelta')], default='abierta', max_length=10)),
                ('decision', models.CharField(blank=True, choices=[('mantener', 'Se mantiene la evaluación'), ('retirar', 'Se retira la evaluación')], max_length=10, null=True)),
                ('motivo_resolucion', models.CharField(blank=True, max_length=500, null=True)),
                ('resuelta_en', models.DateTimeField(blank=True, null=True)),
                ('denunciante', models.ForeignKey(db_column='denunciante_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='identidad.usuario')),
                ('resuelta_por', models.ForeignKey(blank=True, db_column='resuelta_por_id', db_index=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='identidad.usuario')),
                ('evaluacion', models.ForeignKey(db_column='evaluacion_id', db_index=False, on_delete=django.db.models.deletion.PROTECT, related_name='denuncias', to='evaluaciones.evaluacion')),
            ],
            options={
                'db_table': 'denuncia',
            },
        ),
        migrations.AddIndex(
            model_name='evaluacion',
            index=models.Index(fields=['evaluado', 'parte', 'estado'], name='evaluacion_evaluado_idx'),
        ),
        migrations.AddConstraint(
            model_name='evaluacion',
            constraint=models.UniqueConstraint(fields=('ticket', 'parte'), name='evaluacion_una_por_parte'),
        ),
        migrations.AddConstraint(
            model_name='evaluacion',
            constraint=models.CheckConstraint(condition=models.Q(('parte__in', ['cliente', 'maestro'])), name='evaluacion_parte_valida'),
        ),
        migrations.AddConstraint(
            model_name='evaluacion',
            constraint=models.CheckConstraint(condition=models.Q(('estado__in', ['publicada', 'retirada'])), name='evaluacion_estado_valido'),
        ),
        migrations.AddConstraint(
            model_name='evaluacion',
            constraint=models.CheckConstraint(condition=models.Q(('autor', models.F('evaluado')), _negated=True), name='evaluacion_autor_no_evaluado'),
        ),
        migrations.AddConstraint(
            model_name='evaluacion',
            constraint=models.CheckConstraint(condition=models.Q(('puntualidad__gte', 1), ('puntualidad__lte', 5), ('trabajo__gte', 1), ('trabajo__lte', 5), ('cordialidad__gte', 1), ('cordialidad__lte', 5)), name='evaluacion_notas_validas'),
        ),
        migrations.AddConstraint(
            model_name='evaluacion',
            constraint=models.CheckConstraint(condition=django.db.models.lookups.LessThanOrEqual(django.db.models.functions.text.Length('comentario'), 500), name='evaluacion_comentario_largo'),
        ),
        migrations.AddIndex(
            model_name='denuncia',
            index=models.Index(condition=models.Q(('estado', 'abierta')), fields=['creada_en'], name='denuncia_abierta_idx'),
        ),
        migrations.AddConstraint(
            model_name='denuncia',
            constraint=models.UniqueConstraint(fields=('evaluacion', 'denunciante'), name='denuncia_una_por_denunciante'),
        ),
        migrations.AddConstraint(
            model_name='denuncia',
            constraint=models.CheckConstraint(condition=models.Q(('estado__in', ['abierta', 'resuelta'])), name='denuncia_estado_valido'),
        ),
        migrations.AddConstraint(
            model_name='denuncia',
            constraint=models.CheckConstraint(condition=models.Q(('decision__isnull', True), ('decision__in', ['mantener', 'retirar']), _connector='OR'), name='denuncia_decision_valida'),
        ),
        migrations.AddConstraint(
            model_name='denuncia',
            constraint=models.CheckConstraint(condition=models.Q(django.db.models.lookups.GreaterThanOrEqual(django.db.models.functions.text.Length('motivo'), 1), django.db.models.lookups.LessThanOrEqual(django.db.models.functions.text.Length('motivo'), 500)), name='denuncia_motivo_largo'),
        ),
        migrations.AddConstraint(
            model_name='denuncia',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('decision__isnull', False), ('estado', 'resuelta'), ('motivo_resolucion__isnull', False), ('resuelta_en__isnull', False), ('resuelta_por__isnull', False), models.Q(('motivo_resolucion', ''), _negated=True)), models.Q(('decision__isnull', True), ('estado', 'abierta'), ('motivo_resolucion__isnull', True), ('resuelta_en__isnull', True), ('resuelta_por__isnull', True)), _connector='OR'), name='denuncia_resolucion_completa'),
        ),
    ]
