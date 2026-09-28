"""Enlaces firmados de acceso temporal a documentos (RNF-06, base; propuesta del S1, §5, punto 6).

El token liga la referencia del documento y el usuario, y caduca a los 600
segundos (10 minutos, RNF-06). El volumen de documentos y el endpoint de
descarga llegan en S2 (CA-25.2); la autorización del documento la sigue
decidiendo su política, el enlace no la reemplaza.
"""
from django.core.signing import BadSignature, TimestampSigner

VIGENCIA_SEGUNDOS = 600

_SAL = "altiro.enlaces.documento"


class EnlaceInvalido(Exception):
    """Firma inválida, enlace caducado o enlace emitido para otro usuario."""


def firmar(documento_ref, usuario_id):
    return TimestampSigner(salt=_SAL).sign_object({"d": str(documento_ref), "u": usuario_id})


def verificar(token, usuario_id):
    """Devuelve la referencia del documento si el enlace es válido para este usuario."""
    try:
        datos = TimestampSigner(salt=_SAL).unsign_object(token, max_age=VIGENCIA_SEGUNDOS)
    except (BadSignature, TypeError, ValueError):
        raise EnlaceInvalido() from None
    if not isinstance(datos, dict) or datos.get("u") != usuario_id or not isinstance(datos.get("d"), str):
        raise EnlaceInvalido()
    return datos["d"]
