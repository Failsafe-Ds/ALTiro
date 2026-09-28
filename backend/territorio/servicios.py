"""Consultas del catálogo territorial usadas por otros módulos (RF-01, CA-01.1)."""
from identidad.errores import ErrorValidacion
from territorio.models import Comuna

_MENSAJE_FALTA = "Elige tu comuna para continuar."
_MENSAJE_NO_EXISTE = "Esa comuna no está en la lista. Elige tu región y luego tu comuna."


def buscar_comuna(valor):
    """Devuelve la ``Comuna`` de código ``valor`` (texto de dígitos o entero) o lanza ``ErrorValidacion``."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ErrorValidacion("comuna", _MENSAJE_FALTA)
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ErrorValidacion("comuna", _MENSAJE_NO_EXISTE)
    texto = str(valor).strip()
    if not texto.isascii() or not texto.isdigit() or len(texto) > 6:
        raise ErrorValidacion("comuna", _MENSAJE_NO_EXISTE)
    comuna = Comuna.objects.filter(codigo=int(texto)).first()
    if comuna is None:
        raise ErrorValidacion("comuna", _MENSAJE_NO_EXISTE)
    return comuna
