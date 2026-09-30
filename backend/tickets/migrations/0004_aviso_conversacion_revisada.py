"""Aviso ``conversacion_revisada`` (S5, incremento 6; ADR-026, E-4.4; tipo de hasta 30 caracteres)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('identidad', '0003_usuario_rol_asignado_en'),
        ('tickets', '0003_aviso_mensaje_nuevo'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='avisoticket',
            name='aviso_ticket_tipo_valido',
        ),
        migrations.AlterField(
            model_name='avisoticket',
            name='tipo',
            field=models.CharField(choices=[('ticket_nuevo', 'Pedido nuevo'), ('ticket_cerrado', 'Pedido cerrado'), ('ticket_aceptado', 'Pedido aceptado'), ('precio_registrado', 'Precio por aceptar'), ('precio_objetado', 'Precio no aceptado'), ('orden_finalizada', 'Trabajo terminado'), ('mensaje_nuevo', 'Mensaje nuevo'), ('conversacion_revisada', 'Conversación revisada por moderación')], max_length=30),
        ),
        migrations.AddConstraint(
            model_name='avisoticket',
            constraint=models.CheckConstraint(condition=models.Q(('tipo__in', ['ticket_nuevo', 'ticket_cerrado', 'ticket_aceptado', 'precio_registrado', 'precio_objetado', 'orden_finalizada', 'mensaje_nuevo', 'conversacion_revisada'])), name='aviso_ticket_tipo_valido'),
        ),
    ]
