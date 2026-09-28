"""Modelo de identidad: usuario, usuario_rol, perfil_cliente y perfil_maestro.

ADR-001: usuario propio sobre ``AbstractBaseUser`` sin ``PermissionsMixin``.
ADR-013: una persona, una cuenta; roles múltiples; cliente y maestro son
perfiles del mismo usuario.

La base de datos garantiza lo que ADR-013 (punto 9 y Enmienda E-6) le asigna:
UNIQUE del correo (admite varios NULL), correo distinto de cadena vacía, UNIQUE
y forma canónica del RUT, forma canónica del teléfono cuando existe, un rol por
usuario una sola vez y los roles permitidos. No hay CHECK de minúsculas del
correo (E-6): lo normaliza el servicio. Los invariantes que cruzan tablas (rol <=> perfil, correo/teléfono exigidos por
cada perfil, cuenta sin correo => perfil_maestro) se verifican en
``identidad.servicios`` dentro de la misma transacción.

No se modelan estados de cuenta (ADR-013, punto 1.7). Las sesiones las guarda
``django.contrib.sessions`` (ADR-005).
"""
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.utils import timezone

from identidad.validadores import (
    CORREO_LARGO_MAXIMO,
    NOMBRE_LARGO_MAXIMO,
    RUT_LARGO_MAXIMO,
    TELEFONO_LARGO_MAXIMO,
)
from territorio.models import Comuna


class Rol(models.TextChoices):
    """Roles guardados (ADR-013, puntos 2 y 8). Visitante y Sistema no son roles."""

    CLIENTE = "cliente", "Cliente"
    MAESTRO = "maestro", "Maestro"
    CURATORIA = "curatoria", "Administrador de curatoría"
    COMERCIAL = "comercial", "Administrador comercial"
    MODERACION = "moderacion", "Moderación"
    CONTROL_GESTION = "control_gestion", "Control de gestión"


ROLES_CON_PERFIL = frozenset({Rol.CLIENTE, Rol.MAESTRO})
ROLES_ADMINISTRATIVOS = frozenset(set(Rol) - ROLES_CON_PERFIL)


class Usuario(AbstractBaseUser):
    """Una persona, una cuenta (ADR-013, punto 2).

    - ``correo``: NULL = sin correo; nunca cadena vacía; guardado normalizado
      (el servicio lo recorta y pasa a minúsculas); único cuando existe.
    - ``telefono``: no único; forma canónica "+56" + 9 dígitos (ADR-013, E-3),
      con CHECK en la BD (E-6); NULL solo en cuentas exclusivamente
      administrativas (invariante de servicio).
    - ``password``: hash (heredado). Algoritmo y parámetros: ADR-004 (Borrador).
    """

    nombre = models.CharField(max_length=NOMBRE_LARGO_MAXIMO)
    telefono = models.CharField(max_length=TELEFONO_LARGO_MAXIMO, null=True, blank=True)
    correo = models.EmailField(max_length=CORREO_LARGO_MAXIMO, null=True, blank=True)

    # Django exige USERNAME_FIELD. No define el inicio de sesión: el
    # identificador (correo o RUT) lo resuelve el backend de autenticación
    # propio (ADR-013, punto 1.6), pendiente de RF-02.
    USERNAME_FIELD = "correo"
    REQUIRED_FIELDS = []

    objects = BaseUserManager()

    class Meta:
        db_table = "usuario"
        constraints = [
            models.UniqueConstraint(fields=["correo"], name="usuario_correo_unico"),
            models.CheckConstraint(condition=~Q(correo=""), name="usuario_correo_no_vacio"),
            models.CheckConstraint(
                condition=Q(telefono__isnull=True) | Q(telefono__regex=r"^\+56[0-9]{9}$"),
                name="usuario_telefono_formato",
            ),
        ]

    def clean(self):
        # AbstractBaseUser.clean() aplica NFKC al USERNAME_FIELD (el correo) y lo
        # modificaría en silencio. El tratamiento Unicode del correo no está
        # decidido (HQ-11); la única normalización es la de
        # identidad.validadores.normalizar_correo.
        models.Model.clean(self)

    def __str__(self):
        # Sin datos personales: este texto puede terminar en registros.
        return f"Usuario {self.pk}"


class UsuarioRol(models.Model):
    """Rol de un usuario (N:M). Un mismo rol no se repite para un usuario."""

    # Sin índice propio: lo cubre usuario_rol_unico (usuario_id, rol).
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="roles",
        db_column="usuario_id",
        db_index=False,
    )
    rol = models.CharField(max_length=20, choices=Rol.choices)
    # Fecha de asignación (ADR-010, «Decisión», punto 7). En la BD, DEFAULT now().
    asignado_en = models.DateTimeField(default=timezone.now, db_default=Now())

    class Meta:
        db_table = "usuario_rol"
        constraints = [
            models.UniqueConstraint(fields=["usuario", "rol"], name="usuario_rol_unico"),
            models.CheckConstraint(
                condition=Q(rol__in=[valor for valor, _ in Rol.choices]),
                name="usuario_rol_valido",
            ),
        ]

    def __str__(self):
        return f"Rol {self.rol} del usuario {self.usuario_id}"


class PerfilCliente(models.Model):
    """Perfil de cliente (RF-01). Existe si y solo si el usuario tiene el rol cliente.

    ``comuna``: de la lista cerrada del catálogo territorial (RF-01, CA-01.1,
    ADR-012). Región y provincia se derivan de ella.
    """

    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.PROTECT,
        primary_key=True,
        related_name="perfil_cliente",
        db_column="usuario_id",
    )
    comuna = models.ForeignKey(
        Comuna, on_delete=models.PROTECT, related_name="+", db_column="comuna_codigo"
    )

    class Meta:
        db_table = "perfil_cliente"

    def __str__(self):
        return f"Perfil de cliente del usuario {self.usuario_id}"


class PerfilMaestro(models.Model):
    """Perfil de maestro (RF-03). Existe si y solo si el usuario tiene el rol maestro.

    ``rut`` sin puntos ni guion y con el DV en mayúscula (ADR-013, punto 1),
    único (RF-03), con CHECK de forma canónica (E-6).
    """

    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.PROTECT,
        primary_key=True,
        related_name="perfil_maestro",
        db_column="usuario_id",
    )
    rut = models.CharField(max_length=RUT_LARGO_MAXIMO)

    class Meta:
        db_table = "perfil_maestro"
        constraints = [
            models.UniqueConstraint(fields=["rut"], name="perfil_maestro_rut_unico"),
            # Forma canónica (E-6): 1 a 8 dígitos ASCII y DV 0-9 o K mayúscula,
            # sin puntos ni guion. El dígito verificador lo valida el servicio.
            models.CheckConstraint(
                condition=Q(rut__regex=r"^[0-9]{1,8}[0-9K]$"), name="perfil_maestro_rut_formato"
            ),
        ]

    def __str__(self):
        # Sin el RUT: dato personal.
        return f"Perfil de maestro del usuario {self.usuario_id}"


class IntentoAutenticacion(models.Model):
    """Fallo de inicio de sesión (401) para el limitador (RNF-10, ADR-007).

    No es la bitácora. No guarda contraseña, correo ni RUT: ``clave`` es el
    HMAC del identificador normalizado. Solo lo lee el limitador y nunca se
    usa para deshabilitar una cuenta (M-07, M-08).
    """

    origen = models.GenericIPAddressField()
    clave = models.CharField(max_length=64)
    fecha = models.DateTimeField()

    class Meta:
        db_table = "intento_autenticacion"
        indexes = [
            models.Index(fields=["origen", "fecha"], name="intento_origen_fecha"),
            models.Index(fields=["fecha"], name="intento_fecha"),
        ]

    def __str__(self):
        return f"Intento fallido {self.pk}"
