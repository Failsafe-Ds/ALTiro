"""Servicios de dominio de identidad (ADR-013, puntos 2, 5 a 9; Enmiendas E-1, E-2, E-3, E-6 y E-7).

No son endpoints. Cada vía de creación:
- valida y normaliza todos los datos recibidos antes de escribir;
- crea perfil y rol, y completa el correo o el teléfono faltante, en la misma
  transacción;
- verifica los invariantes que cruzan tablas (``verificar_invariantes``)
  antes de confirmar (E-6);
- nunca une cuentas por coincidencia de correo, teléfono o RUT: los perfiles
  solo se agregan a la instancia de ``Usuario`` que recibe (la de la sesión).

``AUSENTE`` distingue "el dato no vino" de cualquier valor recibido, incluido
``None`` o ``""``: todo valor recibido se valida (E-2, E-7). Nunca se
convierte en silencio un valor recibido en NULL.

Contraseña: toda cuenta nueva la recibe, se valida con la política de ADR-013
(punto 3, E-4) y se guarda con el hasher de ADR-004. Comuna de
``perfil_cliente``: código del catálogo territorial (ADR-012).
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from expediente import servicios as expedientes
from perfil import servicios as perfiles_publicos
from perfil.models import PerfilPublico
from expediente.models import Expediente
from identidad.errores import ErrorValidacion, InvarianteVioladaError
from identidad.models import (
    ROLES_ADMINISTRATIVOS,
    PerfilCliente,
    PerfilMaestro,
    Rol,
    SolicitudRecuperacion,
    Usuario,
    UsuarioRol,
)
from identidad.validadores import (
    normalizar_correo,
    normalizar_nombre,
    normalizar_rut,
    normalizar_telefono,
    validar_contrasena_nueva,
)
from territorio.servicios import buscar_comuna

# Centinela: el dato no vino en la petición.
AUSENTE = object()

_MENSAJE_CORREO_EN_USO = (
    "Este correo ya está registrado. Si es tuyo, inicia sesión con ese correo y continúa desde tu cuenta."
)
_MENSAJE_RUT_EN_USO = "Ese RUT ya tiene una postulación. Si es tuyo, inicia sesión con tu RUT."  # CA-11.3
# Mensajes al agregar cliente o maestro a una cuenta existente (RNF-15, RNF-17):
# sin "perfil" ni "solicitud". ``{para}`` dice para qué se pide el dato.
PARA_CLIENTE = "pedir trabajos"
PARA_MAESTRO = "postular como maestro"
_MENSAJES_DATO_DE_CONTACTO = {
    "telefono": (
        "Para {para} necesitamos tu teléfono: escríbelo.",
        "Tu cuenta ya tiene teléfono, así que no hace falta escribirlo. Bórralo e inténtalo de nuevo.",
    ),
    "correo": (
        "Para {para} necesitamos tu correo: escríbelo.",
        "Tu cuenta ya tiene correo, así que no hace falta escribirlo. Bórralo e inténtalo de nuevo.",
    ),
}
MENSAJE_YA_ES_CLIENTE = "Tu cuenta ya puede pedir trabajos."
MENSAJE_YA_ES_MAESTRO = "Ya postulaste como maestro con esta cuenta."
MENSAJE_CONTRASENA_IGUAL = "Elige una contraseña distinta de la actual."
MENSAJE_MISMO_CORREO = "Ese ya es tu correo. Escribe el correo nuevo que quieres usar."


# --- Invariantes (ADR-013, punto 9) ---

def verificar_invariantes(usuario):
    """Devuelve la lista de invariantes incumplidos por ``usuario`` (vacía si cumple)."""
    roles = set(UsuarioRol.objects.filter(usuario=usuario).values_list("rol", flat=True))
    tiene_cliente = PerfilCliente.objects.filter(usuario=usuario).exists()
    tiene_maestro = PerfilMaestro.objects.filter(usuario=usuario).exists()
    violaciones = []

    if (Rol.CLIENTE in roles) != tiene_cliente:
        violaciones.append("rol cliente sin perfil_cliente o perfil_cliente sin rol cliente")
    if (Rol.MAESTRO in roles) != tiene_maestro:
        violaciones.append("rol maestro sin perfil_maestro o perfil_maestro sin rol maestro")
    if tiene_cliente and (usuario.correo is None or usuario.telefono is None):
        violaciones.append("perfil_cliente exige correo y teléfono")
    if tiene_maestro and usuario.telefono is None:
        violaciones.append("perfil_maestro exige teléfono")
    if usuario.correo is None and not tiene_maestro:
        violaciones.append("cuenta sin correo y sin perfil_maestro: sin identificador de acceso")
    if roles & ROLES_ADMINISTRATIVOS and not tiene_maestro and usuario.correo is None:
        violaciones.append("cuenta administrativa sin perfil_maestro exige correo")
    if usuario.telefono is None and not (roles and roles <= ROLES_ADMINISTRATIVOS):
        violaciones.append("teléfono NULL solo en cuentas exclusivamente administrativas")
    # ADR-017, punto 2: el expediente nace junto con perfil_maestro. La FK
    # impide un expediente sin perfil, así que basta revisar este sentido.
    if tiene_maestro and not Expediente.objects.filter(perfil_maestro_id=usuario.pk).exists():
        violaciones.append("perfil_maestro sin expediente")
    # ADR-019 (propuesta del S3, §3): el perfil público nace junto con perfil_maestro.
    if tiene_maestro and not PerfilPublico.objects.filter(perfil_maestro_id=usuario.pk).exists():
        violaciones.append("perfil_maestro sin perfil público")
    return violaciones


def _exigir_invariantes(usuario):
    violaciones = verificar_invariantes(usuario)
    if violaciones:
        raise InvarianteVioladaError(violaciones)


# --- Ayudas internas ---

def _restriccion_violada(error):
    causa = getattr(error, "__cause__", None)
    diagnostico = getattr(causa, "diag", None)
    return getattr(diagnostico, "constraint_name", None)


def _guardar(instancia, **kwargs):
    """Guarda traduciendo la unicidad de correo y RUT a errores por campo.

    La BD es la garantía final (carreras entre peticiones simultáneas).
    Cualquier otra violación (por ejemplo ``usuario_telefono_formato``) se
    relanza: sería un error de programación, porque el servicio ya normalizó.
    """
    try:
        with transaction.atomic():
            instancia.save(**kwargs)
    except IntegrityError as error:
        restriccion = _restriccion_violada(error)
        if restriccion == "usuario_correo_unico":
            raise ErrorValidacion("correo", _MENSAJE_CORREO_EN_USO) from None
        if restriccion == "perfil_maestro_rut_unico":
            raise ErrorValidacion("rut", _MENSAJE_RUT_EN_USO) from None
        raise


def _asignar_rol(usuario, rol):
    UsuarioRol.objects.create(usuario=usuario, rol=rol)


def _crear_usuario(*, nombre, telefono, correo, contrasena):
    usuario = Usuario(nombre=nombre, telefono=telefono, correo=correo)
    usuario.set_password(contrasena)
    _guardar(usuario, force_insert=True)
    return usuario


def _correo_libre(correo):
    if Usuario.objects.filter(correo=correo).exists():
        raise ErrorValidacion("correo", _MENSAJE_CORREO_EN_USO)


def _rut_libre(rut):
    if PerfilMaestro.objects.filter(rut=rut).exists():
        raise ErrorValidacion("rut", _MENSAJE_RUT_EN_USO)


def _bloquear(usuario):
    """Recarga y bloquea la fila del usuario hasta el fin de la transacción.

    Serializa dos altas simultáneas de perfil sobre la misma cuenta.
    """
    return Usuario.objects.select_for_update().get(pk=usuario.pk)


def _dato_faltante(usuario, campo, valor, normalizar, para):
    """Dato de contacto al agregar un perfil (E-1, E-2, punto 7).

    - La cuenta no lo tiene: es obligatorio y se devuelve normalizado.
    - La cuenta ya lo tiene: no debe venir; se devuelve ``AUSENTE`` (sin cambios).
    """
    falta, sobra = _MENSAJES_DATO_DE_CONTACTO[campo]
    if getattr(usuario, campo) is None:
        if valor is AUSENTE:
            raise ErrorValidacion(campo, falta.format(para=para))
        return normalizar(valor)
    if valor is not AUSENTE:
        raise ErrorValidacion(campo, sobra)
    return AUSENTE


def _completar_usuario(usuario, **datos):
    """Guarda en una sola escritura los datos de contacto que faltaban."""
    campos = [campo for campo, valor in datos.items() if valor is not AUSENTE]
    for campo in campos:
        setattr(usuario, campo, datos[campo])
    if campos:
        _guardar(usuario, update_fields=campos)


def _crear_perfil_maestro(usuario, rut):
    """Perfil, rol, expediente ``en_revision`` y perfil público en la misma transacción.

    ADR-013, punto 2; ADR-017, punto 2; ADR-019 (perfil público con ``ref`` propia).

    Única vía de creación de ``perfil_maestro``: la usan ``crear_cuenta_maestro``
    y ``agregar_perfil_maestro``.
    """
    _rut_libre(rut)
    perfil = PerfilMaestro(usuario=usuario, rut=rut)
    _guardar(perfil, force_insert=True)
    _asignar_rol(usuario, Rol.MAESTRO)
    expedientes.crear_para(perfil)
    perfiles_publicos.crear_perfil_publico_para(perfil)


# --- Vías de creación sin sesión (cuenta nueva) ---

@transaction.atomic
def crear_cuenta_cliente(*, nombre, telefono, correo, contrasena, comuna):
    """Cuenta nueva con ``perfil_cliente`` y rol ``cliente`` (RF-01).

    Nombre, teléfono, correo, contraseña y comuna obligatorios.
    """
    nombre = normalizar_nombre(nombre)
    correo = normalizar_correo(correo)
    telefono = normalizar_telefono(telefono)
    validar_contrasena_nueva(contrasena)
    comuna = buscar_comuna(comuna)
    _correo_libre(correo)
    usuario = _crear_usuario(nombre=nombre, telefono=telefono, correo=correo, contrasena=contrasena)
    _guardar(PerfilCliente(usuario=usuario, comuna=comuna), force_insert=True)
    _asignar_rol(usuario, Rol.CLIENTE)
    _exigir_invariantes(usuario)
    return usuario


@transaction.atomic
def crear_cuenta_maestro(*, nombre, telefono, rut, contrasena, correo=AUSENTE):
    """Cuenta nueva con ``perfil_maestro`` y rol ``maestro`` (RF-03, paso 1).

    RUT, nombre, teléfono y contraseña obligatorios. Correo opcional (§3.4,
    E-7): ``AUSENTE`` deja el correo NULL; cualquier valor recibido, incluidos
    ``None``, ``""`` o solo espacios, se valida como correo.
    """
    nombre = normalizar_nombre(nombre)
    rut = normalizar_rut(rut)
    correo = None if correo is AUSENTE else normalizar_correo(correo)
    telefono = normalizar_telefono(telefono)
    validar_contrasena_nueva(contrasena)
    _rut_libre(rut)
    if correo is not None:
        _correo_libre(correo)
    usuario = _crear_usuario(nombre=nombre, telefono=telefono, correo=correo, contrasena=contrasena)
    _crear_perfil_maestro(usuario, rut)
    _exigir_invariantes(usuario)
    return usuario


@transaction.atomic
def crear_cuenta_administrativa(*, nombre, correo, roles, contrasena, telefono=AUSENTE):
    """Cuenta exclusivamente administrativa (ADR-013, punto 8).

    Correo y contraseña obligatorios; teléfono opcional (si viene, se
    normaliza); solo roles administrativos, al menos uno.
    """
    nombre = normalizar_nombre(nombre)
    correo = normalizar_correo(correo)
    roles = _roles_administrativos(roles)
    telefono = None if telefono is AUSENTE else normalizar_telefono(telefono)
    validar_contrasena_nueva(contrasena)
    _correo_libre(correo)
    usuario = _crear_usuario(nombre=nombre, telefono=telefono, correo=correo, contrasena=contrasena)
    for rol in sorted(roles):
        _asignar_rol(usuario, rol)
    _exigir_invariantes(usuario)
    return usuario


def _roles_administrativos(roles):
    roles = set(roles)
    if not roles:
        raise ErrorValidacion("roles", "Indica al menos un rol administrativo.")
    if not roles <= ROLES_ADMINISTRATIVOS:
        raise ErrorValidacion(
            "roles",
            "Solo se asignan roles administrativos: curatoria, comercial, moderacion o control_gestion.",
        )
    return roles


# --- Vías sobre una cuenta existente (con sesión) ---

@transaction.atomic
def agregar_perfil_cliente(usuario, *, comuna, correo=AUSENTE, telefono=AUSENTE):
    """Agrega ``perfil_cliente`` y el rol ``cliente`` (ADR-013, puntos 2 y 7; E-1, E-2).

    Comuna obligatoria. Teléfono y correo: si la cuenta no los tiene, son
    obligatorios y se guardan en la misma transacción; si ya los tiene, no
    deben venir.
    """
    usuario = _bloquear(usuario)
    if PerfilCliente.objects.filter(usuario=usuario).exists():
        raise ErrorValidacion("perfil", MENSAJE_YA_ES_CLIENTE)
    telefono = _dato_faltante(usuario, "telefono", telefono, normalizar_telefono, PARA_CLIENTE)
    correo = _dato_faltante(usuario, "correo", correo, normalizar_correo, PARA_CLIENTE)
    comuna = buscar_comuna(comuna)
    if correo is not AUSENTE:
        _correo_libre(correo)
    _completar_usuario(usuario, telefono=telefono, correo=correo)
    _guardar(PerfilCliente(usuario=usuario, comuna=comuna), force_insert=True)
    _asignar_rol(usuario, Rol.CLIENTE)
    _exigir_invariantes(usuario)
    return usuario


@transaction.atomic
def agregar_perfil_maestro(usuario, *, rut, telefono=AUSENTE):
    """Agrega ``perfil_maestro`` y el rol ``maestro`` (ADR-013, punto 2; E-1, E-2).

    Teléfono: si la cuenta no lo tiene, es obligatorio y se guarda en la misma
    transacción; si ya lo tiene, no debe venir.
    """
    usuario = _bloquear(usuario)
    if PerfilMaestro.objects.filter(usuario=usuario).exists():
        raise ErrorValidacion("perfil", MENSAJE_YA_ES_MAESTRO)
    rut = normalizar_rut(rut)
    telefono = _dato_faltante(usuario, "telefono", telefono, normalizar_telefono, PARA_MAESTRO)
    _rut_libre(rut)
    _completar_usuario(usuario, telefono=telefono)
    _crear_perfil_maestro(usuario, rut)
    _exigir_invariantes(usuario)
    return usuario


@transaction.atomic
def asignar_rol_administrativo(usuario, rol):
    """Agrega un rol administrativo a una cuenta existente.

    ``cliente`` y ``maestro`` solo nacen con su perfil (invariante 9).
    """
    usuario = _bloquear(usuario)
    (rol,) = _roles_administrativos([rol])
    if UsuarioRol.objects.filter(usuario=usuario, rol=rol).exists():
        raise ErrorValidacion("roles", "La cuenta ya tiene ese rol.")
    _asignar_rol(usuario, rol)
    _exigir_invariantes(usuario)
    return usuario


# --- Cambio de credenciales (ADR-027, puntos 1 a 3) ---
# La reautenticación (RNF-09) la hace quien llama: la vista con la contraseña
# actual, o la recuperación con un enlace válido.

def anular_enlaces_de_recuperacion(usuario):
    """Ningún enlace de recuperación pendiente de la cuenta sigue sirviendo."""
    SolicitudRecuperacion.objects.filter(
        usuario=usuario, token_hash__isnull=False, usada_en__isnull=True, anulada_en__isnull=True
    ).update(anulada_en=timezone.now())


@transaction.atomic
def cambiar_contrasena(usuario, contrasena_nueva):
    """Guarda la contraseña nueva con la política de ADR-013 (errores en ``contrasena_nueva``).

    Cambia ``get_session_auth_hash()``: todas las sesiones abiertas de la cuenta
    dejan de valer (ADR-005); quien llama renueva la propia si corresponde.
    """
    usuario = _bloquear(usuario)
    try:
        validar_contrasena_nueva(contrasena_nueva)
    except ErrorValidacion as error:
        raise ErrorValidacion("contrasena_nueva", error.mensaje) from None
    if usuario.check_password(contrasena_nueva):
        raise ErrorValidacion("contrasena_nueva", MENSAJE_CONTRASENA_IGUAL)
    usuario.set_password(contrasena_nueva)
    usuario.save(update_fields=["password"])
    anular_enlaces_de_recuperacion(usuario)
    return usuario


@transaction.atomic
def cambiar_correo(usuario, correo):
    """Cambia el correo, o agrega el primero (ADR-027, punto 2; enmienda a ADR-013, punto 7).

    Devuelve ``(usuario, correo_anterior)``; el anterior puede ser ``None``.
    """
    usuario = _bloquear(usuario)
    correo = normalizar_correo(correo)
    if correo == usuario.correo:
        raise ErrorValidacion("correo", MENSAJE_MISMO_CORREO)
    _correo_libre(correo)
    anterior = usuario.correo
    usuario.correo = correo
    _guardar(usuario, update_fields=["correo"])
    _exigir_invariantes(usuario)
    return usuario, anterior
