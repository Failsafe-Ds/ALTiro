"""Validación y recodificación de fotos de documentos (ADR-015, D-5; NTI-09).

``recodificar(datos)`` recibe los bytes subidos y devuelve un JPEG nuevo:

- Solo JPEG y PNG, detectados por el contenido con Pillow (nunca por la
  extensión ni por el Content-Type que declara el navegador).
- Hasta ``settings.ALTIRO_DOCUMENTO_MAXIMO_BYTES`` (8 MB) por archivo.
- Hasta ``MAXIMO_PIXELES``: se revisa en la cabecera, antes de decodificar.
  Pillow además lanza ``DecompressionBombError`` o ``DecompressionBombWarning``
  por su propio límite; ambos son un error de validación.
- Se decodifica la imagen completa (un archivo truncado o corrupto es error).
- Se recodifica a JPEG **sin metadatos**: sin EXIF (ni GPS), sin comentarios,
  sin XMP y sin perfil de color ICC. La orientación EXIF se aplica a los
  píxeles antes de descartarla, para que la foto no quede girada.
  Sin ICC: el perfil no es necesario para leer un documento, puede traer
  datos arbitrarios (hasta varios cientos de KB) y las fotos de teléfono son
  sRGB o casi; una foto en Display P3 se verá con colores algo más apagados,
  sin afectar su lectura.
- Nunca se devuelven los bytes originales: la salida siempre es una imagen
  nueva generada desde los píxeles, lo que también neutraliza archivos
  políglotas (por ejemplo, HTML escondido en una imagen).
"""
import io
import warnings

from django.conf import settings
from PIL import Image, ImageOps

# Límite de píxeles (ADR-015, D-5, no fija el valor). 25 megapíxeles admiten
# la foto completa de casi cualquier teléfono aunque la compresión del cliente
# falle (4000 x 3000 = 12 MP; 6000 x 4000 = 24 MP) y acotan la memoria de una
# decodificación a unos 75 MB en RGB (RNF-04: 2 GB para todo el sistema).
MAXIMO_PIXELES = 25_000_000
# Calidad JPEG: legible para revisar un documento con un peso moderado.
CALIDAD_JPEG = 85
_FORMATOS = ("JPEG", "PNG")
# El JPEG "MPO" (varias imágenes, común en algunos teléfonos) es JPEG: se usa la primera.
_FORMATOS_ACEPTADOS = frozenset({"JPEG", "MPO", "PNG"})


class ImagenInvalida(Exception):
    """La foto no se acepta. ``mensaje`` se muestra a la persona (RNF-15)."""

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


MENSAJE_FORMATO = "Envía una foto. Este archivo no es una foto que podamos leer."
MENSAJE_PESO = "La foto es muy pesada. Toma la foto de nuevo o elige otra."
MENSAJE_PIXELES = "La foto es demasiado grande. Elige otra o tómala de nuevo."
MENSAJE_VACIA = "La foto llegó vacía. Elígela de nuevo e inténtalo otra vez."


def _aplanar(imagen):
    """Devuelve la imagen en RGB o L, con la transparencia sobre fondo blanco."""
    if imagen.mode in ("RGB", "L"):
        return imagen
    if imagen.mode in ("RGBA", "LA", "PA") or (imagen.mode == "P" and "transparency" in imagen.info):
        rgba = imagen.convert("RGBA")
        fondo = Image.new("RGB", rgba.size, (255, 255, 255))
        fondo.paste(rgba, mask=rgba.getchannel("A"))
        return fondo
    if imagen.mode in ("I;16", "I;16B", "I;16L", "I"):
        return imagen.convert("I").point(lambda v: v / 256).convert("L")
    return imagen.convert("RGB")


def recodificar(datos):
    """Valida ``datos`` (bytes) y devuelve un JPEG nuevo sin metadatos. ``ImagenInvalida`` si no se acepta."""
    if not datos:
        raise ImagenInvalida(MENSAJE_VACIA)
    if len(datos) > settings.ALTIRO_DOCUMENTO_MAXIMO_BYTES:
        raise ImagenInvalida(MENSAJE_PESO)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(datos), formats=_FORMATOS) as original:
                if original.format not in _FORMATOS_ACEPTADOS:
                    raise ImagenInvalida(MENSAJE_FORMATO)
                ancho, alto = original.size
                if ancho < 1 or alto < 1:
                    raise ImagenInvalida(MENSAJE_FORMATO)
                if ancho * alto > MAXIMO_PIXELES:
                    raise ImagenInvalida(MENSAJE_PIXELES)
                original.load()
                # Aplica la orientación EXIF a los píxeles (la etiqueta se descarta después).
                imagen = _aplanar(ImageOps.exif_transpose(original))
                # Imagen nueva sin ``info``: ningún metadato de la original llega al guardar.
                limpia = Image.new(imagen.mode, imagen.size)
                limpia.paste(imagen)
    except ImagenInvalida:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImagenInvalida(MENSAJE_PIXELES) from None
    except (Image.UnidentifiedImageError, OSError, SyntaxError, ValueError, TypeError, EOFError):
        raise ImagenInvalida(MENSAJE_FORMATO) from None
    salida = io.BytesIO()
    limpia.save(salida, format="JPEG", quality=CALIDAD_JPEG, optimize=True)
    return salida.getvalue()
