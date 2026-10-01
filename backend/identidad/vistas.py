"""Endpoints de identidad (RF-01, RF-02, RF-03; propuesta del S1, §4; ADR-013).

Las respuestas usan listas explícitas de campos: nunca se serializa un modelo
completo (base de RNF-08). Ningún registro inicia sesión (ADR-013, E-8).
"""
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from comun.api import (
    ErroresDeCampo,
    leer_json,
    manejar_errores,
    metodos,
    publica,
    respuesta_error,
)
from identidad import limitador, recuperacion, servicios
from identidad.autenticacion import (
    autenticar,
    buscar_usuario,
    interpretar_identificador,
    validar_contrasena_ingreso,
)
from identidad.errores import ErrorValidacion
from identidad.models import PerfilCliente, PerfilMaestro, UsuarioRol
from identidad.sesion import cerrar_sesion, iniciar_sesion
from identidad.validadores import (
    normalizar_correo,
    normalizar_nombre,
    normalizar_rut,
    normalizar_telefono,
    validar_contrasena_nueva,
)
from territorio.servicios import buscar_comuna

logger = logging.getLogger(__name__)

# ADR-013, punto 4: mismo 401 y mismo mensaje para cuenta inexistente y contraseña incorrecta.
MENSAJE_CREDENCIALES = (
    "No pudimos iniciar sesión. Revisa tu correo o RUT y tu contraseña e inténtalo de nuevo."
)

# Campos permitidos por endpoint y contexto (propuesta del S1, §4; E-2).
CAMPOS_CLIENTE_SIN_SESION = {"nombre", "telefono", "correo", "contrasena", "comuna"}
CAMPOS_CLIENTE_CON_SESION = {"comuna", "correo", "telefono"}
CAMPOS_MAESTRO_SIN_SESION = {"nombre", "telefono", "rut", "contrasena", "correo"}
CAMPOS_MAESTRO_CON_SESION = {"rut", "telefono"}
CAMPOS_SESION = {"identificador", "contrasena"}
# Cambio de credenciales y recuperación (ADR-027).
CAMPOS_CAMBIO_CONTRASENA = {"contrasena", "contrasena_nueva"}
CAMPOS_CAMBIO_CORREO = {"contrasena", "correo"}
CAMPOS_RECUPERACION = {"identificador"}
CAMPOS_RESTABLECER = {"token", "contrasena_nueva"}

MENSAJE_CONTRASENA_ACTUAL = "La contraseña actual no es correcta. Revísala e inténtalo de nuevo."
# ADR-027, punto 3: la misma respuesta exista o no la cuenta.
MENSAJE_RECUPERACION = (
    "Si los datos corresponden a una cuenta con correo, te enviamos un enlace para crear una contraseña nueva. "
    "Revisa tu correo: el enlace sirve una sola vez. Si no tienes correo en tu cuenta, comunícate con AlTiro "
    "para que te ayuden a recuperarla."
)


def _validar_todos(datos, validadores):
    """Aplica cada validador a su campo y reúne todos los errores (RNF-15)."""
    errores = {}
    for campo, validar in validadores.items():
        try:
            validar(datos.get(campo))
        except ErrorValidacion as error:
            errores[error.campo] = error.mensaje
    if errores:
        raise ErroresDeCampo(errores)


def _ejecutar(servicio, *args, **kwargs):
    try:
        return servicio(*args, **kwargs)
    except ErrorValidacion as error:
        raise ErroresDeCampo({error.campo: error.mensaje}) from None


def _opcional(datos, campo):
    return datos[campo] if campo in datos else servicios.AUSENTE


def _respuesta_espera(minutos, plantilla):
    """429 con ``Retry-After`` (RNF-10; ADR-007 y ADR-027). ``plantilla`` recibe "N minutos"."""
    texto = "1 minuto" if minutos == 1 else f"{minutos} minutos"
    respuesta = respuesta_error(429, plantilla.format(texto))
    respuesta["Retry-After"] = str(minutos * 60)
    return respuesta


def datos_cuenta(usuario):
    """Datos propios de la cuenta, con lista explícita de campos. Nunca el hash."""
    perfil_cliente = (
        PerfilCliente.objects.select_related("comuna__provincia__region").filter(usuario=usuario).first()
    )
    perfil_maestro = PerfilMaestro.objects.filter(usuario=usuario).first()
    return {
        "nombre": usuario.nombre,
        "correo": usuario.correo,
        "telefono": usuario.telefono,
        "roles": sorted(UsuarioRol.objects.filter(usuario=usuario).values_list("rol", flat=True)),
        "perfil_cliente": (
            {
                "comuna": {
                    "codigo": perfil_cliente.comuna.codigo,
                    "nombre": perfil_cliente.comuna.nombre,
                },
                "region": {
                    "codigo": perfil_cliente.comuna.provincia.region.codigo,
                    "nombre": perfil_cliente.comuna.provincia.region.nombre,
                },
            }
            if perfil_cliente
            else None
        ),
        "perfil_maestro": {"rut": perfil_maestro.rut} if perfil_maestro else None,
    }


# --- CSRF (ADR-006) ---


@publica
@metodos("GET")
@ensure_csrf_cookie
def csrf(request):
    """Entrega la cookie CSRF que el frontend envía en ``X-CSRFToken``."""
    respuesta = HttpResponse(status=204)
    respuesta["Cache-Control"] = "no-store"
    return respuesta


# --- Sesión (RF-02) ---


@publica
@metodos("POST", "DELETE")
@manejar_errores
def sesion(request):
    if request.method == "DELETE":
        return _cerrar_sesion(request)
    return _iniciar_sesion(request)


def _cerrar_sesion(request):
    if request.usuario is None:
        return respuesta_error(401, "No hay una sesión iniciada.")
    cerrar_sesion(request)
    return HttpResponse(status=204)


def _iniciar_sesion(request):
    datos = leer_json(request, CAMPOS_SESION)
    errores = {}
    tipo = valor = None
    try:
        tipo, valor = interpretar_identificador(datos.get("identificador"))
    except ErrorValidacion as error:
        errores[error.campo] = error.mensaje
    try:
        validar_contrasena_ingreso(datos.get("contrasena"))
    except ErrorValidacion as error:
        errores[error.campo] = error.mensaje
    if errores:
        # Los 400 no cuentan como intento fallido (ADR-007, punto 8).
        raise ErroresDeCampo(errores)

    origen = limitador.origen_de(request)
    clave = limitador.clave_de(tipo, valor)
    minutos = limitador.minutos_de_bloqueo(origen, clave)
    if minutos:
        # RNF-10: bloqueado aunque la contraseña sea correcta. No se cuenta (punto 2).
        return _respuesta_espera(minutos, "Hubo varios intentos fallidos. Por seguridad, espera {} e inténtalo de nuevo.")

    usuario = autenticar(tipo, valor, datos["contrasena"])
    if usuario is None:
        limitador.registrar_fallo(origen, clave)
        logger.info("Inicio de sesión fallido.")
        return respuesta_error(401, MENSAJE_CREDENCIALES)

    iniciar_sesion(request, usuario)
    logger.info("Inicio de sesión correcto del usuario %s.", usuario.pk)
    return JsonResponse({"cuenta": datos_cuenta(usuario)})


# --- Cuenta ---


@metodos("GET")
def cuenta(request):
    """Datos de la propia cuenta. Sin identificador en la ruta (ADR-011, patrón "me")."""
    respuesta = JsonResponse({"cuenta": datos_cuenta(request.usuario)})
    respuesta["Cache-Control"] = "no-store"
    return respuesta


# --- Cambio de contraseña y de correo (RNF-09; ADR-027, puntos 1 y 2) ---


def _reautenticar(request, contrasena):
    """Exige la contraseña actual (RNF-09) con el limitador de RNF-10.

    Devuelve un 429 si la cuenta está bloqueada desde este origen, o ``None``
    si la contraseña es correcta. Si no lo es, cuenta el fallo y responde 400
    en ``contrasena``. Un 400 de formato no cuenta (ADR-007, punto 8).
    """
    _ejecutar(validar_contrasena_ingreso, contrasena)
    origen = limitador.origen_de(request)
    clave = limitador.clave_de("cuenta", str(request.usuario.pk))
    minutos = limitador.minutos_de_bloqueo(origen, clave)
    if minutos:
        return _respuesta_espera(
            minutos, "Hubo varios intentos con una contraseña equivocada. Por seguridad, espera {} e inténtalo de nuevo."
        )
    if not request.usuario.check_password(contrasena):
        limitador.registrar_fallo(origen, clave)
        logger.info("Reautenticación fallida.")
        raise ErroresDeCampo({"contrasena": MENSAJE_CONTRASENA_ACTUAL})
    return None


@metodos("POST")
@manejar_errores
def cuenta_contrasena(request):
    datos = leer_json(request, CAMPOS_CAMBIO_CONTRASENA)
    bloqueo = _reautenticar(request, datos.get("contrasena"))
    if bloqueo:
        return bloqueo
    usuario = _ejecutar(servicios.cambiar_contrasena, request.usuario, datos.get("contrasena_nueva"))
    # Las demás sesiones ya no valen (cambió el hash); esta sigue, con un ID y un token CSRF nuevos.
    iniciar_sesion(request, usuario)
    recuperacion.avisar_contrasena_cambiada(usuario)
    logger.info("Contraseña cambiada por el usuario %s.", usuario.pk)
    return JsonResponse(
        {"mensaje": "Listo: tu contraseña cambió. Cerramos tu sesión en los otros teléfonos o computadores."}
    )


@metodos("POST")
@manejar_errores
def cuenta_correo(request):
    datos = leer_json(request, CAMPOS_CAMBIO_CORREO)
    bloqueo = _reautenticar(request, datos.get("contrasena"))
    if bloqueo:
        return bloqueo
    usuario, anterior = _ejecutar(servicios.cambiar_correo, request.usuario, datos.get("correo"))
    if anterior is not None:
        recuperacion.avisar_correo_cambiado(anterior)
    logger.info("Correo cambiado por el usuario %s.", usuario.pk)
    return JsonResponse({"mensaje": "Listo: guardamos tu correo nuevo.", "cuenta": datos_cuenta(usuario)})


# --- Recuperación de contraseña (ADR-027, punto 3) ---


@publica
@metodos("POST")
@manejar_errores
def recuperacion_solicitud(request):
    datos = leer_json(request, CAMPOS_RECUPERACION)
    tipo, valor = _ejecutar(interpretar_identificador, datos.get("identificador"))
    try:
        recuperacion.solicitar(buscar_usuario(tipo, valor), limitador.origen_de(request))
    except recuperacion.DemasiadasSolicitudes as error:
        return _respuesta_espera(error.minutos, "Pediste varios enlaces seguidos. Espera {} e inténtalo de nuevo.")
    return JsonResponse({"mensaje": MENSAJE_RECUPERACION}, status=202)


@publica
@metodos("POST")
@manejar_errores
def recuperacion_contrasena(request):
    datos = leer_json(request, CAMPOS_RESTABLECER)
    usuario = _ejecutar(recuperacion.restablecer, datos.get("token"), datos.get("contrasena_nueva"))
    recuperacion.avisar_contrasena_cambiada(usuario)
    logger.info("Contraseña restablecida con un enlace de recuperación (usuario %s).", usuario.pk)
    return JsonResponse({"mensaje": "Listo: tu contraseña nueva quedó guardada. Ahora ingresa con ella."})


# --- Registro de cliente (RF-01, HU-01) ---


@publica
@metodos("POST")
@manejar_errores
def clientes(request):
    if request.usuario is None:
        datos = leer_json(request, CAMPOS_CLIENTE_SIN_SESION)
        _validar_todos(
            datos,
            {
                "nombre": normalizar_nombre,
                "telefono": normalizar_telefono,
                "correo": normalizar_correo,
                "comuna": buscar_comuna,
                "contrasena": validar_contrasena_nueva,
            },
        )
        _ejecutar(
            servicios.crear_cuenta_cliente,
            nombre=datos["nombre"],
            telefono=datos["telefono"],
            correo=datos["correo"],
            contrasena=datos["contrasena"],
            comuna=datos["comuna"],
        )
        return JsonResponse(
            {"mensaje": "Tu cuenta quedó creada. Ahora inicia sesión con tu correo y tu contraseña."},
            status=201,
        )

    datos = leer_json(request, CAMPOS_CLIENTE_CON_SESION)
    usuario = _ejecutar(
        servicios.agregar_perfil_cliente,
        request.usuario,
        comuna=datos.get("comuna"),
        correo=_opcional(datos, "correo"),
        telefono=_opcional(datos, "telefono"),
    )
    return JsonResponse(
        {"mensaje": "Agregamos el perfil de cliente a tu cuenta.", "cuenta": datos_cuenta(usuario)},
        status=201,
    )


# --- Postulación de maestro, paso 1 (RF-03, HU-11) ---


@publica
@metodos("POST")
@manejar_errores
def postulaciones(request):
    if request.usuario is None:
        datos = leer_json(request, CAMPOS_MAESTRO_SIN_SESION)
        validadores = {
            "rut": normalizar_rut,
            "nombre": normalizar_nombre,
            "telefono": normalizar_telefono,
            "contrasena": validar_contrasena_nueva,
        }
        if "correo" in datos:
            validadores["correo"] = normalizar_correo
        _validar_todos(datos, validadores)
        _ejecutar(
            servicios.crear_cuenta_maestro,
            nombre=datos["nombre"],
            telefono=datos["telefono"],
            rut=datos["rut"],
            contrasena=datos["contrasena"],
            correo=_opcional(datos, "correo"),
        )
        return JsonResponse(
            {"mensaje": "Tu postulación quedó registrada. Ahora inicia sesión con tu RUT y tu contraseña."},
            status=201,
        )

    datos = leer_json(request, CAMPOS_MAESTRO_CON_SESION)
    usuario = _ejecutar(
        servicios.agregar_perfil_maestro,
        request.usuario,
        rut=datos.get("rut"),
        telefono=_opcional(datos, "telefono"),
    )
    return JsonResponse(
        {"mensaje": "Tu postulación como maestro quedó registrada en tu cuenta.", "cuenta": datos_cuenta(usuario)},
        status=201,
    )
