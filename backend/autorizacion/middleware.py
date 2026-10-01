"""Traduce las denegaciones de autorización a respuestas (RNF-07, CA-25.3; ADR-010, ADR-011).

- ``RecursoNoEncontrado`` -> 404 neutro, sin registro.
- ``AccesoDenegado`` -> se registra en ``acceso_denegado`` y responde
  exactamente el mismo 404 (ADR-011, punto 2).
- ``RolRequerido`` -> se registra con ``entidad_ref`` NULL y responde 403 con
  un mensaje accionable.
- ``ConflictoDeInteres`` -> se registra con la entidad y la referencia del
  recurso y responde 403 con un mensaje accionable (ADR-011, E-2).
- ``ParteEquivocada`` -> se registra igual y responde 403 con el mensaje de la
  excepción (ADR-023, punto 6).

Ningún 403 de este middleware lleva la cabecera ``AlTiro-Rechazo``: no se
reintentan (ADR-011, E-1 y E-2).

Solo se registra si hay un usuario autenticado (``request.usuario``). El
recurso es el método más el **patrón** de la ruta, nunca la ruta cruda ni la
cadena de consulta (ADR-011, punto 4).

Frecuencia (ADR-007, E-1): cada denegación de un usuario autenticado, y cada
referencia inexistente que pide, cuenta en ``identidad.frecuencia`` (ámbito
``denegado``). Con ``REGLAS_DENEGADO`` alcanzado responde 429 **en lugar** de
cualquiera de estas respuestas y no inserta en ``acceso_denegado``: así la
tabla no crece sin límite y el 429 es igual para un recurso ajeno y uno
inexistente (no revela existencia). El conteo no lee ``acceso_denegado`` (M-08).
"""
from autorizacion import acceso_denegado
from autorizacion.excepciones import (
    AccesoDenegado,
    ConflictoDeInteres,
    ParteEquivocada,
    RecursoNoEncontrado,
    RolRequerido,
)
from comun.api import respuesta_error, respuesta_no_encontrado
from identidad import frecuencia

MENSAJE_SIN_ROL = (
    "No tienes permiso para esta sección. Vuelve al inicio o ingresa con una cuenta que tenga acceso."
)

# Conflicto de interés del expediente (HU-19, CA-19.4; ADR-011, E-2); otras políticas traen su mensaje.
MENSAJE_CONFLICTO = (
    "No puedes revisar ni resolver tu propio expediente. Otra persona de curatoría debe hacerlo."
)

# Entidad registrada cuando falta el rol: lo denegado es la ruta, no un recurso.
ENTIDAD_RUTA = "ruta"

MENSAJE_DEMASIADAS_DENEGACIONES = (
    "Abriste muchas páginas que no existen o no son tuyas. Por seguridad, espera {} y vuelve al inicio."
)

_DENEGACIONES = (RecursoNoEncontrado, AccesoDenegado, RolRequerido, ConflictoDeInteres, ParteEquivocada)


def _respuesta_espera(espera):
    minutos = frecuencia.minutos(espera)
    texto = "1 minuto" if minutos == 1 else f"{minutos} minutos"
    respuesta = respuesta_error(429, MENSAJE_DEMASIADAS_DENEGACIONES.format(texto))
    respuesta["Retry-After"] = str(minutos * 60)
    return respuesta


def _recurso(request):
    coincidencia = getattr(request, "resolver_match", None)
    patron = getattr(coincidencia, "route", None) or "(sin patrón)"
    return f"{request.method} {patron}"


class AutorizacionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, excepcion):
        usuario = getattr(request, "usuario", None)
        if usuario is not None and isinstance(excepcion, _DENEGACIONES):
            espera = frecuencia.consumir("denegado", usuario.pk, frecuencia.REGLAS_DENEGADO)
            if espera is not None:
                return _respuesta_espera(espera)
        if isinstance(excepcion, RecursoNoEncontrado):
            return respuesta_no_encontrado()
        if isinstance(excepcion, AccesoDenegado):
            if usuario is not None:
                acceso_denegado.registrar(usuario, _recurso(request), excepcion.entidad, excepcion.ref)
            return respuesta_no_encontrado()
        if isinstance(excepcion, RolRequerido):
            if usuario is not None:
                acceso_denegado.registrar(usuario, _recurso(request), ENTIDAD_RUTA)
            return respuesta_error(403, MENSAJE_SIN_ROL)
        if isinstance(excepcion, ConflictoDeInteres):
            if usuario is not None:
                acceso_denegado.registrar(usuario, _recurso(request), excepcion.entidad, excepcion.ref)
            return respuesta_error(403, excepcion.mensaje or MENSAJE_CONFLICTO)
        if isinstance(excepcion, ParteEquivocada):
            if usuario is not None:
                acceso_denegado.registrar(usuario, _recurso(request), excepcion.entidad, excepcion.ref)
            return respuesta_error(403, excepcion.mensaje)
        return None
