"""Tarea del actor Sistema sobre ``acceso_denegado`` (ADR-010, punto 3; ADR-016, punto 1; cierra DA-06).

Vive en ``autorizacion`` porque ningún módulo de fuera usa este registro (M-08;
lo verifica ``tests/test_acceso_denegado.py``). La ejecuta el planificador
(``expediente/management/commands/planificador.py``) junto con las tareas de
``expediente.tareas``.
"""
from autorizacion.acceso_denegado import purgar_vencidos


def purgar_accesos_denegados(ahora):
    """Borra las filas con más de 90 días y devuelve cuántas borró. Idempotente.

    ``ahora`` se recibe por uniformidad con las demás tareas, pero no interviene:
    la condición usa ``now()`` de SQL, igual que el trigger que solo permite
    borrar esas filas (ADR-010, punto 3). ``purgar_vencidos`` deja el evento
    con el conteo, sin datos personales (RNF-22, en parte).
    """
    return purgar_vencidos()
