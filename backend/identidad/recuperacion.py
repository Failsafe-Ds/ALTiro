"""Recuperación de contraseña y avisos por correo (ADR-027, puntos 3 a 5).

- El token tiene 256 bits y solo se guarda su SHA-256. Vence a los
  ``ALTIRO_RECUPERACION_MINUTOS``, sirve una vez y uno nuevo anula los anteriores.
- Pedir un enlace siempre tiene el mismo resultado visible, exista o no la
  cuenta: lo único que cambia es si se escribe un correo en el buzón.
- Límites: 5 solicitudes por origen en 15 minutos (``DemasiadasSolicitudes``)
  y 3 enlaces por cuenta en una hora (lo que pase de eso no se envía).
- Los correos se escriben en el buzón local (``ALTIRO_BUZON_DIR``). Nunca se
  registran el token, la contraseña ni el correo (CLAUDE.md §8).
- Carreras (ADR-027, E-1): la solicitud toma un bloqueo consultivo por origen y
  bloquea la fila del usuario; dos solicitudes simultáneas no superan los
  límites ni dejan dos enlaces vigentes.
- Tiempo de respuesta (ADR-027, E-1): el correo del enlace se escribe en un
  hilo aparte, después de confirmar la transacción, para que la respuesta no
  espere la escritura y cueste lo mismo exista o no la cuenta.
"""
import hashlib
import logging
import math
import secrets
import threading
from datetime import timedelta

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.db import transaction
from django.utils import timezone

from identidad import frecuencia, servicios
from identidad.errores import ErrorValidacion
from identidad.models import SolicitudRecuperacion, Usuario, ViaRecuperacion

logger = logging.getLogger(__name__)

LIMITE_POR_ORIGEN = 5
VENTANA_ORIGEN = timedelta(minutes=15)
LIMITE_POR_CUENTA = 3
VENTANA_CUENTA = timedelta(hours=1)
RETENCION = timedelta(hours=24)
# Origen de los enlaces creados desde la consola (recuperación asistida).
ORIGEN_CONSOLA = "0.0.0.0"
TOKEN_LARGO_MAXIMO = 100

MENSAJE_ENLACE_INVALIDO = (
    "Este enlace ya no sirve: venció o ya se usó. Pide uno nuevo desde «Olvidé mi contraseña»."
)


class DemasiadasSolicitudes(Exception):
    def __init__(self, minutos):
        super().__init__(minutos)
        self.minutos = minutos


def _resumen(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def enlace(token):
    """El token va en el fragmento: el navegador no lo envía al servidor ni al proxy."""
    return f"{settings.ALTIRO_URL_PUBLICA}/nueva-contrasena.html#t={token}"


def _emitir(usuario, origen, via, ahora):
    servicios.anular_enlaces_de_recuperacion(usuario)
    token = secrets.token_urlsafe(32)
    SolicitudRecuperacion.objects.create(
        usuario=usuario,
        origen=origen,
        via=via,
        token_hash=_resumen(token),
        creada_en=ahora,
        vence_en=ahora + timedelta(minutes=settings.ALTIRO_RECUPERACION_MINUTOS),
    )
    return token


@transaction.atomic
def _registrar_solicitud(usuario, origen):
    """Registra la solicitud y devuelve el token si corresponde enviar un enlace, o ``None``."""
    # Orden fijo de bloqueos: primero el origen, después la cuenta (sin interbloqueos).
    frecuencia.bloquear("recuperacion", origen)
    if usuario is not None:
        usuario = Usuario.objects.select_for_update().get(pk=usuario.pk)
    ahora = timezone.now()
    SolicitudRecuperacion.objects.filter(creada_en__lt=ahora - RETENCION).delete()
    del_origen = list(
        SolicitudRecuperacion.objects.filter(origen=origen, creada_en__gt=ahora - VENTANA_ORIGEN)
        .order_by("creada_en")
        .values_list("creada_en", flat=True)
    )
    if len(del_origen) >= LIMITE_POR_ORIGEN:
        libre = del_origen[-LIMITE_POR_ORIGEN] + VENTANA_ORIGEN
        raise DemasiadasSolicitudes(max(1, math.ceil((libre - ahora).total_seconds() / 60)))
    enviados = (
        usuario is not None
        and SolicitudRecuperacion.objects.filter(
            usuario=usuario, token_hash__isnull=False, creada_en__gt=ahora - VENTANA_CUENTA
        ).count()
    )
    if usuario is None or usuario.correo is None or enviados >= LIMITE_POR_CUENTA:
        SolicitudRecuperacion.objects.create(usuario=usuario, origen=origen, via=ViaRecuperacion.CORREO, creada_en=ahora)
        return None
    return _emitir(usuario, origen, ViaRecuperacion.CORREO, ahora)


def solicitar(usuario, origen):
    """Pide un enlace para ``usuario`` (puede ser ``None``). Lanza ``DemasiadasSolicitudes``."""
    token = _registrar_solicitud(usuario, origen)
    if token is None:
        return
    minutos = settings.ALTIRO_RECUPERACION_MINUTOS
    _en_segundo_plano(
        enviar_correo,
        usuario.correo,
        "Crea una contraseña nueva para AlTiro",
        "Hola:\n\n"
        "Pediste crear una contraseña nueva para tu cuenta de AlTiro. Abre este enlace y escríbela:\n\n"
        f"{enlace(token)}\n\n"
        f"El enlace sirve una sola vez y durante {minutos} minutos.\n"
        "Si no lo pediste tú, no hagas nada: tu contraseña sigue igual.\n",
    )


def crear_enlace_asistido(usuario):
    """Enlace para la recuperación asistida (comando de consola). Devuelve el enlace."""
    with transaction.atomic():
        usuario = Usuario.objects.select_for_update().get(pk=usuario.pk)
        token = _emitir(usuario, ORIGEN_CONSOLA, ViaRecuperacion.ASISTIDA, timezone.now())
    return enlace(token)


@transaction.atomic
def restablecer(token, contrasena_nueva):
    """Guarda la contraseña nueva con un enlace válido y lo marca usado. No inicia sesión.

    Lanza ``ErrorValidacion`` en ``token`` (enlace inválido) o en ``contrasena_nueva``.
    Si la contraseña no pasa la política, el enlace sigue sirviendo (la transacción se revierte).
    """
    if not isinstance(token, str) or not token or len(token) > TOKEN_LARGO_MAXIMO:
        raise ErrorValidacion("token", MENSAJE_ENLACE_INVALIDO)
    ahora = timezone.now()
    solicitud = (
        SolicitudRecuperacion.objects.select_for_update()
        .filter(token_hash=_resumen(token), usada_en__isnull=True, anulada_en__isnull=True, vence_en__gt=ahora)
        .first()
    )
    if solicitud is None:
        raise ErrorValidacion("token", MENSAJE_ENLACE_INVALIDO)
    solicitud.usada_en = ahora
    solicitud.save(update_fields=["usada_en"])
    return servicios.cambiar_contrasena(solicitud.usuario, contrasena_nueva)


# --- Avisos por correo ---


def _en_segundo_plano(funcion, *args):
    """Ejecuta ``funcion`` en un hilo aparte (ADR-027, E-1). Devuelve el hilo, o ``None`` si fue en línea.

    ``ALTIRO_CORREO_EN_SEGUNDO_PLANO=False`` (solo en las pruebas) la ejecuta en
    línea para que el buzón se pueda leer de inmediato. El hilo no usa la base
    de datos: solo escribe el archivo del correo.
    """
    if not getattr(settings, "ALTIRO_CORREO_EN_SEGUNDO_PLANO", True):
        funcion(*args)
        return None
    hilo = threading.Thread(target=funcion, args=args, name="altiro-correo")
    hilo.start()
    return hilo


def enviar_correo(destino, asunto, cuerpo):
    """Escribe el correo en el buzón. Un error se registra sin datos y no interrumpe la operación."""
    try:
        conexion = get_connection(file_path=str(settings.ALTIRO_BUZON_DIR))
        send_mail(asunto, cuerpo, None, [destino], connection=conexion)
    except Exception:  # noqa: BLE001 — el correo nunca debe deshacer la operación ya hecha.
        logger.error("No se pudo escribir un correo en el buzón (asunto: %s).", asunto)


def avisar_contrasena_cambiada(usuario):
    if usuario.correo is None:
        return
    enviar_correo(
        usuario.correo,
        "Tu contraseña de AlTiro cambió",
        "Hola:\n\n"
        "La contraseña de tu cuenta de AlTiro acaba de cambiar y cerramos las sesiones abiertas.\n"
        "Si no fuiste tú, usa «Olvidé mi contraseña» en la página de ingreso para crear una nueva.\n",
    )


def avisar_correo_cambiado(correo_anterior):
    enviar_correo(
        correo_anterior,
        "Tu correo de AlTiro cambió",
        "Hola:\n\n"
        "Tu cuenta de AlTiro ahora usa otro correo. Desde hoy los avisos llegan allá.\n"
        "Si no fuiste tú, comunícate con AlTiro.\n",
    )
