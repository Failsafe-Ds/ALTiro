"""Registro de aplicación en JSON, una línea por evento (RNF-22; ADR-026, E-8).

- ``FormatoJson``: formatter de ``logging`` (librería estándar, sin dependencias).
  Cada línea lleva ``nivel``, ``marca_tiempo`` (UTC, ISO 8601), ``usuario`` y
  ``operacion``; las de una petición, además, ``estado`` y ``duracion_ms``.
  Un evento escrito durante una petición lleva el usuario de esa petición (id
  interno o ``anonimo`` si aún no hay sesión); solo los que no vienen de una
  petición (planificador, arranque) llevan ``usuario: "sistema"`` (DEF-QA-015).
  Los eventos sueltos llevan ``operacion`` con el nombre del logger y ``mensaje``.
- ``RegistroOperacionMiddleware``: escribe una línea por petición en el logger
  ``altiro.operacion``. ``operacion`` es el nombre de la ruta (o su patrón, con
  ``<uuid:ref>`` sin el valor) y el método. Nunca la ruta real, el cuerpo, los
  parámetros, las cookies ni las cabeceras.
- De ``django.request`` (solo ERROR, ver ``settings.LOGGING``) se conserva el
  motivo ("Internal Server Error") y se descarta la ruta con ``ref``.

Este módulo lo importa ``dictConfig`` antes de ``apps.populate()``: no importa modelos.
"""
import contextvars
import json
import logging
import time
from datetime import datetime, timezone

LOGGER_OPERACION = "altiro.operacion"
USUARIO_ANONIMO = "anonimo"
USUARIO_SISTEMA = "sistema"

# Rutas de verificación de salud: cada 10 s desde el healthcheck; en DEBUG
# para no llenar el registro (root está en INFO).
RUTAS_SALUD = frozenset({"salud"})

logger_operacion = logging.getLogger(LOGGER_OPERACION)

# Petición en curso (una por hilo o tarea); ``None`` fuera de peticiones.
_peticion_actual = contextvars.ContextVar("altiro_peticion_actual", default=None)


def _marca_tiempo(record):
    instante = datetime.fromtimestamp(record.created, tz=timezone.utc)
    return instante.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _mensaje(record):
    if record.name == "django.request":
        # "%s: %s" con (motivo, ruta): la ruta puede llevar un ref (E-8, punto 2).
        if isinstance(record.args, tuple) and record.args:
            return str(record.args[0])
    return record.getMessage()


class FormatoJson(logging.Formatter):
    """Una línea JSON por registro. Solo campos de una lista positiva."""

    def format(self, record):
        datos = {
            "nivel": record.levelname,
            "marca_tiempo": _marca_tiempo(record),
            "usuario": getattr(record, "usuario", None) or _usuario_del_contexto(),
            "operacion": getattr(record, "operacion", record.name),
        }
        if hasattr(record, "estado"):
            datos["estado"] = record.estado
            datos["duracion_ms"] = record.duracion_ms
        else:
            datos["mensaje"] = _mensaje(record)
        # La traza ya viene segura desde ``comun.registros.FiltroTrazasSeguras``.
        if record.exc_text:
            datos["traza"] = record.exc_text
        elif record.exc_info:
            datos["traza"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False)


def _operacion(request):
    coincidencia = getattr(request, "resolver_match", None)
    if coincidencia is None:
        nombre = "sin_ruta"
    else:
        nombre = coincidencia.view_name or coincidencia.route or "sin_nombre"
    return f"{nombre} {request.method}"


def _usuario(request):
    usuario = getattr(request, "usuario", None)
    return str(usuario.pk) if usuario is not None and usuario.pk is not None else USUARIO_ANONIMO


def _usuario_del_contexto():
    request = _peticion_actual.get()
    return USUARIO_SISTEMA if request is None else _usuario(request)


def _nivel(estado):
    if estado >= 500:
        return logging.ERROR
    if estado >= 400:
        return logging.WARNING
    return logging.INFO


class RegistroOperacionMiddleware:
    """Registra cada petición: usuario, operación, estado y duración (RNF-22)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inicio = time.monotonic()
        marca = _peticion_actual.set(request)
        try:
            respuesta = self.get_response(request)
        finally:
            _peticion_actual.reset(marca)
        duracion_ms = round((time.monotonic() - inicio) * 1000, 1)
        coincidencia = getattr(request, "resolver_match", None)
        nivel = _nivel(respuesta.status_code)
        if coincidencia is not None and coincidencia.url_name in RUTAS_SALUD and nivel == logging.INFO:
            nivel = logging.DEBUG
        logger_operacion.log(
            nivel,
            "operacion",
            extra={
                "usuario": _usuario(request),
                "operacion": _operacion(request),
                "estado": respuesta.status_code,
                "duracion_ms": duracion_ms,
            },
        )
        return respuesta
