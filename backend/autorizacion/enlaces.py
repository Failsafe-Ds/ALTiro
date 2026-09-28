"""Enlaces firmados de acceso temporal a documentos (RNF-06; ADR-015, D-3).

El token liga la referencia del documento, el usuario y, opcionalmente, la
cara del archivo (``anverso`` o ``reverso``), y caduca a los 600 segundos
(10 minutos, RNF-06). La autorización del documento la sigue decidiendo su
política (``expediente.politicas.PoliticaDocumento``): el enlace no la
reemplaza, la vista de descarga la vuelve a aplicar.

``verificar`` exige que la cara del token sea exactamente la esperada: un
token emitido sin cara no sirve para una cara, y uno de una cara no sirve
para la otra.
"""
from django.core.signing import BadSignature, TimestampSigner

VIGENCIA_SEGUNDOS = 600

_SAL = "altiro.enlaces.documento"


class EnlaceInvalido(Exception):
    """Firma inválida, enlace caducado o enlace emitido para otro usuario o cara."""


def firmar(documento_ref, usuario_id, cara=None):
    datos = {"d": str(documento_ref), "u": usuario_id}
    if cara is not None:
        datos["c"] = cara
    return TimestampSigner(salt=_SAL).sign_object(datos)


def verificar(token, usuario_id, cara=None):
    """Devuelve la referencia del documento si el enlace es válido para este usuario y cara."""
    try:
        datos = TimestampSigner(salt=_SAL).unsign_object(token, max_age=VIGENCIA_SEGUNDOS)
    except (BadSignature, TypeError, ValueError):
        raise EnlaceInvalido() from None
    if (
        not isinstance(datos, dict)
        or datos.get("u") != usuario_id
        or not isinstance(datos.get("d"), str)
        or datos.get("c") != cara
    ):
        raise EnlaceInvalido()
    return datos["d"]
