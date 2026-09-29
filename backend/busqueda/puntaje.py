"""Puntaje y orden de la búsqueda (RF-10, RF-11, CA-03.1 a CA-03.4; informe §3.3.2; ADR-022, puntos 2 y 3).

Módulo **puro**. Fórmula del informe: ``0,6 × Disponibilidad + 0,4 × Cercanía``,
que se calcula en enteros como ``6·D + 4·C`` (10 veces el valor del informe,
sin decimales). Ejemplo de CA-03.2: 6·60 + 4·60 = 600 (60 puntos) frente a
6·30 + 4·100 = 580 (58 puntos).

- Disponibilidad (D):
  - con filtro de bloque, 100 (todos los que pasan el filtro lo tienen libre);
  - sin filtro de bloque (CA-03.4, horizonte de tres días): 60 si tiene una
    ocurrencia ofrecible hoy, 30 si la tiene entre hoy+1 y hoy+3, 0 si no.
- Cercanía (C): 100 si la comuna pedida es su comuna base, 60 si está en su
  cobertura. Fuera de cobertura vale 0 (solo en sugerencias; el filtro ya los
  descartó de los resultados principales).
- Desempate (RF-11): mayor calificación promedio, después más evaluaciones
  (hasta el S5 valen ``None`` y 0) y al final un sorteo diario determinista
  ``sha256(ref pública + fecha de hoy)`` (ADR-022, punto 3).

**El puntaje y sus componentes nunca van en la respuesta** (ADR-022, punto 2):
la cercanía revelaría la comuna base (ADR-019, D-14).
"""
import datetime
import hashlib

D_BLOQUE = 100
D_HOY = 60
D_PROXIMOS = 30
D_NADA = 0
C_BASE = 100
C_COBERTURA = 60
C_FUERA = 0
# CA-03.4: "los próximos tres días".
DIAS_PROXIMOS = 3


def disponibilidad(fechas_ofrecibles, hoy, con_bloque):
    """D según la escala del informe. ``fechas_ofrecibles``: fechas con alguna ocurrencia ofrecible."""
    if con_bloque:
        return D_BLOQUE
    if hoy in fechas_ofrecibles:
        return D_HOY
    proximos = {hoy + datetime.timedelta(days=n) for n in range(1, DIAS_PROXIMOS + 1)}
    if proximos & set(fechas_ofrecibles):
        return D_PROXIMOS
    return D_NADA


def cercania(es_base, en_cobertura=True):
    if not en_cobertura:
        return C_FUERA
    return C_BASE if es_base else C_COBERTURA


def puntaje(d, c):
    """10 × (0,6·D + 0,4·C), en enteros."""
    return 6 * d + 4 * c


def sorteo(ref, hoy):
    """Sorteo diario determinista dentro del día (ADR-022, punto 3)."""
    return hashlib.sha256(f"{ref}{hoy.isoformat()}".encode("ascii")).hexdigest()


def clave_orden(puntaje_total, calificacion, cantidad, ref, hoy):
    """Clave para ``sorted``: puntaje de mayor a menor, luego RF-11 y el sorteo.

    Una calificación ``None`` (sin evaluaciones) queda después de cualquier número.
    """
    return (
        -puntaje_total,
        calificacion is None,
        -(calificacion or 0),
        -(cantidad or 0),
        sorteo(ref, hoy),
    )
