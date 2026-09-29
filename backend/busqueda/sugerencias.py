"""Sugerencias cuando no hay resultados (RF-12, CA-04.2, CA-04.3; ADR-022, punto 6).

Solo se calculan si no hay resultados principales. Se relaja **un** filtro a
la vez y cada sugerencia indica el único criterio que incumple:

1. ``bloque``: cumple oficio, publicación y comuna, pero no tiene libre el
   horario pedido (solo si se pidió un horario);
2. ``comuna``: cumple oficio, publicación y horario (si se pidió), pero no
   atiende la comuna pedida; sí atiende otra comuna de la **misma provincia**
   (ADR-012).

Nunca se relaja el oficio ni la regla de publicación: los candidatos ya
pasaron la regla única (``busqueda.servicios.cargar_candidatos``). Como
máximo ``MAXIMO`` sugerencias. Si no hay ninguna razonable, la lista queda
vacía y la pantalla muestra solo el mensaje (HU-04, reglas).
"""
from busqueda import servicios

MAXIMO = 5
INCUMPLE_BLOQUE = "bloque"
INCUMPLE_COMUNA = "comuna"
TEXTOS = {
    INCUMPLE_BLOQUE: "No tiene libre el horario que elegiste.",
    INCUMPLE_COMUNA: "No trabaja en la comuna que elegiste, pero sí en otra de la misma provincia.",
}


def sugerir(candidatos, comuna_codigo, bloque, hoy):
    """``[(Candidato, incumple)]``, primero los que solo incumplen el horario y después la comuna."""
    visibles = [c for c in candidatos if c.servicio_visible]
    sin_bloque = []
    if bloque is not None:
        sin_bloque = [
            c for c in visibles
            if servicios.cumple_comuna(c, comuna_codigo) and not servicios.cumple_bloque(c, bloque)
        ]
        # Sin filtro de bloque para ordenar: la disponibilidad se evalúa como en CA-03.4.
        sin_bloque = servicios.ordenar(sin_bloque, comuna_codigo, None, hoy)
    otra_comuna = [
        c for c in visibles
        if not servicios.cumple_comuna(c, comuna_codigo) and servicios.cumple_bloque(c, bloque)
    ]
    otra_comuna = servicios.ordenar(otra_comuna, comuna_codigo, bloque, hoy, en_cobertura=False)
    propuestas = [(c, INCUMPLE_BLOQUE) for c in sin_bloque] + [(c, INCUMPLE_COMUNA) for c in otra_comuna]
    return propuestas[:MAXIMO]
