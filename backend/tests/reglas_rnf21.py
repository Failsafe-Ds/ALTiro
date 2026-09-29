"""Catálogo de reglas de negocio críticas para medir RNF-21 (propuesta del S4, §7; ADR-022, punto 8; D-18).

RNF-21: "Al menos el 60% de las reglas de filtros, puntaje, cierre de tickets
y control de acceso cubiertas por pruebas automáticas". Se mide **por reglas**
y **por grupo**: una regla está cubierta si al menos una prueba de
``tests/test_*.py`` la cita con ``@pytest.mark.regla("ID")``
(``tests/test_rnf21_cobertura_de_reglas.py``).

``GRUPOS_ACTIVOS``: grupos que la prueba de control ya exige. Los de cierre
(incremento 6) y acceso de tickets (incrementos 4 y 5) se agregan a medida que
llegan las funciones; la meta del sprint es el 100 %.
"""

REGLAS = {
    "filtros": {
        "F-01": "CA-02.1: con filtro de comuna, no aparece quien no la declaró en su cobertura",
        "F-02": "CA-02.2: con filtro de oficio, no aparece quien no tiene el expediente aprobado",
        "F-03": "CA-02.3: con filtro de bloque, no aparece quien no declaró ese bloque",
        "F-04": "CA-02.4: con varios filtros, todos los resultados cumplen las tres condiciones",
        "F-05": "CA-13.2: al quitar una comuna de la cobertura, deja de aparecer en ella",
        "F-06": "RF-06: un maestro sin comuna base no aparece",
        "F-07": "CA-24.4 / RNF-25: sin licencia vigente no aparece por el oficio regulado, sí por los no regulados",
        "F-08": "ADR-019: suspendido o sin foto no aparece",
        "F-09": "RF-16: un bloque que empieza en 4 horas o menos no cuenta como libre",
        "F-10": "CA-14.3: un bloque que se cruza con un ticket aceptado o finalizado no cuenta como libre",
        "F-11": "ADR-022, D-3: la ocurrencia debe contener el rango pedido",
        "F-12": "ADR-022: la búsqueda coincide con la regla única aplicada maestro por maestro",
        "F-13": "ADR-022: parámetros desconocidos o inválidos se rechazan en el servidor",
        "F-14": "ADR-020, E-1: una hora que no existe por el horario de verano no se ofrece",
    },
    "puntaje": {
        "P-01": "RF-10: con filtro de bloque, disponibilidad 100",
        "P-02": "RF-10: sin filtro, disponibilidad 60 si tiene libre hoy",
        "P-03": "RF-10: sin filtro, disponibilidad 30 si tiene libre entre hoy+1 y hoy+3",
        "P-04": "RF-10: sin filtro, disponibilidad 0 si no tiene nada en el horizonte",
        "P-05": "RF-10: cercanía 100 en la comuna base y 60 en la cobertura",
        "P-06": "CA-03.2: 60 puntos (hoy, comuna secundaria) antes que 58 (tres días, comuna base)",
        "P-07": "CA-03.4: sin filtro, la disponibilidad se evalúa en los próximos tres días",
        "P-08": "CA-03.1: la lista se ordena de mayor a menor puntaje",
        "P-09": "CA-03.3 / RF-11: empate por calificación promedio y luego por cantidad de evaluaciones",
        "P-10": "ADR-022, punto 3: el desempate final es un sorteo diario determinista",
        "P-11": "ADR-022, punto 2: el puntaje y sus componentes no van en la respuesta",
    },
    "cierre": {
        "C-01": "RF-21: cierre a las 24 horas desde el envío (vencido_plazo)",
        "C-02": "RF-22: cierre 4 horas antes del inicio (vencido_proximidad)",
        "C-03": "CA-23.6: a las 28 horas exactas cuenta como proximidad",
        "C-04": "RF-23: cierre por el cliente; no se puede aceptar después",
        "C-05": "RF-20: rechazo del maestro deja el bloque libre",
        "C-06": "RF-19: aceptar cierra los pendientes que se cruzan (bloque_tomado)",
        "C-07": "RF-24: los cinco motivos de cierre se registran de forma distinguible",
    },
    "acceso": {
        "A-01": "CA-25.1: un tercero recibe el 404 idéntico con registro al abrir un ticket",
        "A-02": "ADR-023: la parte equivocada de una acción recibe 403 registrado",
        "A-03": "RF-17 / RNF-08: el maestro no recibe dirección ni teléfono con el ticket pendiente",
        "A-04": "ADR-013 E-9: nadie puede pedirse un trabajo a sí mismo",
        "A-05": "ADR-023: solo el rol cliente crea tickets",
    },
}

GRUPOS_ACTIVOS = frozenset({"filtros", "puntaje"})
UMBRAL = 0.60


def todas():
    return {regla for reglas in REGLAS.values() for regla in reglas}
