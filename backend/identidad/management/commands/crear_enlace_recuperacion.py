"""Recuperación asistida de contraseña (ADR-027, punto 3).

Para quien no tiene correo en su cuenta, por ejemplo un maestro que ingresa con
su RUT. **Antes de ejecutarlo**, quien lo usa verifica la identidad de la
persona fuera del sistema (por ejemplo, la llama al teléfono registrado y le
pregunta su RUT). Después le hace llegar el enlace, que sirve una sola vez y
vence en ``ALTIRO_RECUPERACION_MINUTOS``.

Igual que ``crear_usuario_administrativo`` (ADR-010), no escribe la bitácora
administrativa ni se atribuye al actor Sistema: emite un evento de aplicación
con el id de la cuenta, sin el enlace ni datos personales.

Uso dentro del contenedor:
    python manage.py crear_enlace_recuperacion --cuenta 12.345.678-5
"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from identidad import recuperacion
from identidad.autenticacion import buscar_usuario, interpretar_identificador
from identidad.errores import ErrorValidacion

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Crea un enlace de un solo uso para que una persona cree una contraseña nueva."

    def add_arguments(self, parser):
        parser.add_argument("--cuenta", required=True, metavar="CORREO_O_RUT", help="Correo o RUT de la cuenta.")

    def handle(self, *args, **opciones):
        try:
            usuario = buscar_usuario(*interpretar_identificador(opciones["cuenta"]))
        except ErrorValidacion as error:
            raise CommandError(error.mensaje) from None
        if usuario is None:
            raise CommandError("No existe una cuenta con ese correo o RUT.")
        enlace = recuperacion.crear_enlace_asistido(usuario)
        logger.info("Enlace de recuperación asistida creado por comando de consola: usuario %s.", usuario.pk)
        self.stdout.write(
            f"Enlace para el usuario {usuario.pk} (sirve una vez, durante "
            f"{settings.ALTIRO_RECUPERACION_MINUTOS} minutos):\n{enlace}\n"
            "Entrégalo solo a la persona dueña de la cuenta, después de verificar su identidad."
        )
