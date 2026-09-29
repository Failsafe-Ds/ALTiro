"""Rangos ocupados de la agenda de los maestros (CA-14.3; ADR-022, punto 1; ADR-023, punto 4).

Un bloque está **ocupado** si se cruza con un ticket ``aceptado`` o
``finalizado`` del mismo maestro (ADR-023, punto 4; D-12: "mismo bloque"
significa que los rangos se cruzan).

La app ``tickets`` llega en el incremento 4 del S4. Hasta entonces no existe
ningún ticket y esta función devuelve un diccionario vacío: todas las
ocurrencias están libres. El incremento 4 la completa con **una** consulta en
lote sobre ``ticket`` (estado en ``aceptado``/``finalizado``, maestro en
``maestro_ids`` e ``inicio_en < hasta`` y ``fin_en > desde``), sin cambiar su
firma, para que la búsqueda y la ficha sigan con un número de consultas
constante (RNF-01).
"""


def rangos_ocupados(maestro_ids, desde, hasta):
    """``{maestro_id: [(inicio_en, fin_en), ...]}`` de los tickets que ocupan agenda entre ``desde`` y ``hasta``.

    Hoy (antes de la app ``tickets``) siempre vacío. Ver el docstring del módulo.
    """
    return {}
