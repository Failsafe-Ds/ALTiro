"""Cobertura del maestro: comunas que atiende y su comuna base (RF-06, HU-13, CA-13.1; ADR-019, puntos 3 y 4).

``reemplazar_cobertura(usuario, comunas)`` guarda la lista completa en una
transacción: o queda la lista nueva entera, o queda la anterior sin cambios.

``comunas``: lista de objetos ``{"comuna": <código CUT>, "es_base": <bool>}``.
El código es el del catálogo territorial (ADR-012), como número o texto de
dígitos; ``es_base`` es opcional (falso si falta). Exactamente una comuna es
la base (CA-13.1): con cero o con dos, 400 y no se guarda nada.

El maestro edita su cobertura en todo estado salvo ``rechazado`` (409, D-7).
En pantalla la comuna base se llama "comuna principal" (RNF-17).
"""
from django.db import transaction

from expediente.errores import ErroresValidacion
from perfil.models import Cobertura
from perfil.servicios import expediente_editable
from territorio.models import Comuna

CAMPO = "comunas"
# Tope defensivo del tamaño de la lista recibida (Chile tiene 346 comunas).
MAXIMO_COMUNAS = 400
_CLAVES_ELEMENTO = frozenset({"comuna", "es_base"})

MENSAJE_COMUNAS_FALTA = "Elige al menos una comuna donde trabajas y marca cuál es tu comuna principal."
MENSAJE_COMUNAS_ILEGIBLES = "No pudimos leer las comunas elegidas. Vuelve a cargar la página y elígelas de nuevo."
MENSAJE_COMUNA_NO_EXISTE = "Una de las comunas elegidas no está en la lista. Elige tus comunas de la lista."
MENSAJE_COMUNA_REPETIDA = "Elegiste la misma comuna dos veces. Déjala una sola vez."
MENSAJE_SIN_COMUNA_BASE = "Marca cuál de tus comunas es tu comuna principal. Sin ella no puedes guardar."
MENSAJE_DOS_COMUNAS_BASE = "Marca solo una comuna como tu comuna principal."
MENSAJE_RECHAZADO = "Tu postulación no fue aprobada, así que ya no puedes cambiar tus comunas."


def _error(mensaje):
    return ErroresValidacion({CAMPO: mensaje})


def _codigo(valor):
    """Código CUT como entero, o ``None`` si no tiene la forma de un código."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor if 0 < valor < 1_000_000 else None
    if isinstance(valor, str):
        texto = valor.strip()
        if texto.isascii() and texto.isdigit() and 0 < len(texto) <= 6:
            return int(texto)
    return None


def _validar(comunas):
    """Devuelve ``[(Comuna, es_base)]`` o lanza ``ErroresValidacion`` en ``comunas``."""
    if not isinstance(comunas, list) or not comunas:
        raise _error(MENSAJE_COMUNAS_FALTA)
    if len(comunas) > MAXIMO_COMUNAS:
        raise _error(MENSAJE_COMUNAS_ILEGIBLES)
    elegidas = []
    for elemento in comunas:
        if not isinstance(elemento, dict) or set(elemento) - _CLAVES_ELEMENTO or "comuna" not in elemento:
            raise _error(MENSAJE_COMUNAS_ILEGIBLES)
        es_base = elemento.get("es_base", False)
        if not isinstance(es_base, bool):
            raise _error(MENSAJE_COMUNAS_ILEGIBLES)
        codigo = _codigo(elemento["comuna"])
        if codigo is None:
            raise _error(MENSAJE_COMUNA_NO_EXISTE)
        elegidas.append((codigo, es_base))
    codigos = [codigo for codigo, _ in elegidas]
    encontradas = Comuna.objects.in_bulk(codigos)
    if len(encontradas) != len(set(codigos)):
        raise _error(MENSAJE_COMUNA_NO_EXISTE)
    if len(set(codigos)) != len(codigos):
        raise _error(MENSAJE_COMUNA_REPETIDA)
    bases = sum(1 for _, es_base in elegidas if es_base)
    if bases == 0:
        raise _error(MENSAJE_SIN_COMUNA_BASE)
    if bases > 1:
        raise _error(MENSAJE_DOS_COMUNAS_BASE)
    return [(encontradas[codigo], es_base) for codigo, es_base in elegidas]


def reemplazar_cobertura(usuario, comunas):
    """Reemplaza toda la cobertura del maestro ``usuario`` (CA-13.1). Devuelve las filas nuevas."""
    with transaction.atomic():
        expediente_editable(usuario.pk, MENSAJE_RECHAZADO)
        elegidas = _validar(comunas)
        Cobertura.objects.filter(maestro_id=usuario.pk).delete()
        return Cobertura.objects.bulk_create(
            [Cobertura(maestro_id=usuario.pk, comuna=comuna, es_base=es_base) for comuna, es_base in elegidas]
        )


def cobertura_de(maestro_id):
    """Comunas del maestro, por nombre (el orden no revela cuál es la base)."""
    return (
        Cobertura.objects.filter(maestro_id=maestro_id)
        .select_related("comuna__provincia__region")
        .order_by("comuna__nombre", "comuna_id")
    )
