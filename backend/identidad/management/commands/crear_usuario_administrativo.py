"""Alta de cuentas administrativas y asignación de roles administrativos (ADR-013, punto 8).

Única vía para crear administradores: no hay API para esto (propuesta del S1, §4).
La contraseña se pide con entrada oculta y nunca se recibe como argumento ni
se muestra (CLAUDE.md §8). No se registra en la bitácora administrativa ni se
atribuye al actor Sistema (ADR-010). Cada asignación queda con fecha en
``usuario_rol.asignado_en`` y emite un evento de aplicación con el id del
usuario y el rol, sin datos personales (ADR-010, «Decisión», punto 7).

Uso dentro del contenedor:
    python manage.py crear_usuario_administrativo --nombre "Ana Admin" --correo ana@example.com --rol curatoria
    python manage.py crear_usuario_administrativo --agregar-a ana@example.com --rol comercial
"""
import getpass
import logging

from django.core.management.base import BaseCommand, CommandError

from identidad import servicios
from identidad.autenticacion import interpretar_identificador
from identidad.errores import ErrorValidacion
from identidad.models import ROLES_ADMINISTRATIVOS, PerfilMaestro, Usuario

_ROLES = sorted(ROLES_ADMINISTRATIVOS)

logger = logging.getLogger(__name__)


def _registrar_asignacion(usuario, roles):
    """Evento de aplicación por rol asignado: id de usuario y rol, sin datos personales.

    Lo ejecuta una persona desde la consola, que la aplicación no puede
    identificar: no se inventa un autor ni se usa el actor Sistema (ADR-010).
    """
    for rol in sorted(set(roles)):
        logger.info("Rol administrativo asignado por comando de consola: usuario %s, rol %s.", usuario.pk, rol)


class Command(BaseCommand):
    help = "Crea una cuenta administrativa o agrega un rol administrativo a una cuenta existente."

    def add_arguments(self, parser):
        parser.add_argument("--rol", action="append", required=True, choices=_ROLES, help="Se puede repetir.")
        parser.add_argument("--nombre", help="Nombre de la persona (cuenta nueva).")
        parser.add_argument("--correo", help="Correo de acceso (cuenta nueva, obligatorio).")
        parser.add_argument("--telefono", help="Teléfono (opcional).")
        parser.add_argument(
            "--agregar-a",
            metavar="CORREO_O_RUT",
            help="Agrega los roles a una cuenta existente en vez de crear una nueva.",
        )

    def handle(self, *args, **opciones):
        try:
            if opciones["agregar_a"]:
                self._agregar_roles(opciones)
            else:
                self._crear(opciones)
        except ErrorValidacion as error:
            raise CommandError(f"{error.campo}: {error.mensaje}") from None

    def _crear(self, opciones):
        if opciones["telefono"] is None:
            telefono = servicios.AUSENTE
        else:
            telefono = opciones["telefono"]
        contrasena = self._pedir_contrasena()
        usuario = servicios.crear_cuenta_administrativa(
            nombre=opciones["nombre"],
            correo=opciones["correo"],
            roles=opciones["rol"],
            contrasena=contrasena,
            telefono=telefono,
        )
        _registrar_asignacion(usuario, opciones["rol"])
        self.stdout.write(f"Cuenta administrativa creada (usuario {usuario.pk}, roles: {', '.join(sorted(opciones['rol']))}).")

    def _agregar_roles(self, opciones):
        if opciones["nombre"] or opciones["correo"] or opciones["telefono"]:
            raise CommandError("Con --agregar-a solo se indican los roles: la cuenta ya tiene sus datos.")
        tipo, valor = interpretar_identificador(opciones["agregar_a"])
        if tipo == "correo":
            usuario = Usuario.objects.filter(correo=valor).first()
        else:
            perfil = PerfilMaestro.objects.select_related("usuario").filter(rut=valor).first()
            usuario = perfil.usuario if perfil else None
        if usuario is None:
            raise CommandError("No existe una cuenta con ese correo o RUT.")
        for rol in sorted(set(opciones["rol"])):
            servicios.asignar_rol_administrativo(usuario, rol)
            _registrar_asignacion(usuario, [rol])
        self.stdout.write(f"Roles agregados al usuario {usuario.pk}: {', '.join(sorted(set(opciones['rol'])))}.")

    def _pedir_contrasena(self):
        primera = getpass.getpass("Contraseña (12 a 128 caracteres): ")
        segunda = getpass.getpass("Repite la contraseña: ")
        if primera != segunda:
            raise CommandError("Las contraseñas no coinciden. Vuelve a ejecutar el comando.")
        return primera
