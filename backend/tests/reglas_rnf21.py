"""Catálogo de reglas de negocio críticas para medir RNF-21 (propuesta del S4, §7; ADR-022, punto 8; D-18).

RNF-21: "Al menos el 60% de las reglas de filtros, puntaje, cierre de tickets
y control de acceso cubiertas por pruebas automáticas". Se mide **por reglas**
y **por grupo**: una regla está cubierta si al menos una prueba de
``tests/test_*.py`` la cita con ``@pytest.mark.regla("ID")``
(``tests/test_rnf21_cobertura_de_reglas.py``).

``GRUPOS_ACTIVOS``: grupos que la prueba de control ya exige. ``acceso`` entra
en el incremento 4 (A-01, A-03, A-04 y A-05) y A-02 con las acciones del
incremento 5. ``cierre`` entra en el incremento 6 (C-01 a C-08; C-08, fórmula de
``vence_en``, ya se cubría en el 4). La meta del sprint es el 100 %. En el S5,
incremento 1, el precio final agrega C-09 a C-15 y A-06 a A-08; en el
incremento 3, la operación agrega el grupo ``operacion`` (O-01 a O-04); en el
incremento 4, la conversación agrega A-09 a A-15; en los incrementos 5 y 6,
la evaluación y la moderación agregan P-12 a P-14, C-16, C-17 y A-16 a A-24.
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
        "P-12": "RF-30: el promedio mostrado coincide con el cálculo sobre las evaluaciones publicadas del cliente",
        "P-13": "ADR-026, E-4.6: una evaluación retirada queda excluida del promedio sin borrarse",
        "P-14": "CA-05.2: sin evaluaciones, la ficha dice 'Todavía no tiene evaluaciones' en lugar de un cero",
    },
    "cierre": {
        "C-01": "RF-21: cierre a las 24 horas desde el envío (vencido_plazo)",
        "C-02": "RF-22: cierre 4 horas antes del inicio (vencido_proximidad)",
        "C-03": "CA-23.6: a las 28 horas exactas cuenta como proximidad",
        "C-04": "RF-23: cierre por el cliente; no se puede aceptar después",
        "C-05": "RF-20: rechazo del maestro deja el bloque libre",
        "C-06": "RF-19: aceptar cierra los pendientes que se cruzan (bloque_tomado)",
        "C-07": "RF-24: los cinco motivos de cierre se registran de forma distinguible",
        "C-08": "ADR-023, punto 1: vence_en = LEAST(enviado + 24 h, inicio - 4 h), también a las 28 horas exactas",
        "C-09": "RF-27: por trabajo con el monto publicado, el precio final finaliza la orden sin aceptación",
        "C-10": "CA-16.2: por trabajo con otro monto, la orden no finaliza hasta que el cliente acepta",
        "C-11": "RF-27: por hora, el precio final siempre exige la aceptación del cliente",
        "C-12": "ADR-026, E-1.4: aceptar un monto distinto del vigente da 409",
        "C-13": "CA-16.3: una orden finalizada no cambia de precio",
        "C-14": "ADR-026, E-1.8: la base rechaza un finalizado sin precio o sin la aceptación exigida",
        "C-15": "ADR-026, E-1.6 (P-27): el precio final no se registra antes del inicio del horario",
        "C-16": "CA-09.1 / CA-18.1: solo se evalúa una orden finalizada; ambas partes pueden hacerlo",
        "C-17": "CA-09.2 / RF-29: la segunda evaluación de la misma parte da 409 y la base lo impide",
    },
    "acceso": {
        "A-01": "CA-25.1: un tercero recibe el 404 idéntico con registro al abrir un ticket",
        "A-02": "ADR-023: la parte equivocada de una acción recibe 403 registrado",
        "A-03": "RF-17 / RNF-08: el maestro no recibe dirección ni teléfono con el ticket pendiente",
        "A-04": "ADR-013 E-9: nadie puede pedirse un trabajo a sí mismo",
        "A-05": "ADR-023: solo el rol cliente crea tickets",
        "A-06": "ADR-026, E-5: la parte equivocada de una ruta de precio final recibe 403 registrado",
        "A-07": "CA-25.1: un tercero recibe el 404 idéntico con registro en las rutas de precio final",
        "A-08": "RF-28: el cliente y el maestro ven el mismo precio final",
        "A-09": "ADR-026, E-2: en un pedido pendiente no hay conversación (leer o escribir, 409)",
        "A-10": "ADR-026, E-2: solo se escribe en aceptado; en finalizado o cerrado, 409",
        "A-11": "CA-07.3: la conversación se lee en finalizado; en cerrado, lista vacía y 'no hubo conversación'",
        "A-12": "CA-25.1 / R-05: un tercero o un rol administrativo recibe el 404 idéntico con registro en la conversación",
        "A-13": "ADR-026, E-2.4: un reenvío con la misma clave_envio devuelve el mismo mensaje sin duplicarlo",
        "A-14": "RNF-11: los mensajes no se editan ni se borran (aplicación y triggers)",
        "A-15": "ADR-005: la consulta periódica de la conversación no renueva la sesión",
        "A-16": "CA-25.1: un tercero o un rol administrativo recibe el 404 idéntico con registro al evaluar o denunciar",
        "A-17": "ADR-026, E-3.5: la ficha muestra los últimos 10 comentarios sin nombre ni ref del autor",
        "A-18": "ADR-026, E-4.2 (P-26): solo la parte evaluada denuncia, y una sola vez",
        "A-19": "HU-25 / CA-25.3: quien no tiene el rol moderación recibe 403 registrado",
        "A-20": "ADR-026, E-4.3: el moderador que es parte del ticket recibe ConflictoDeInteres (403 registrado)",
        "A-21": "ADR-026, E-4.5: el detalle de moderación no trae dirección ni teléfono",
        "A-22": "M-04 / E-4.4: cada consulta de la conversación escribe la bitácora y avisa a ambas partes",
        "A-23": "E-4.1 / E-4.3: sin denuncia abierta, la conversación da el 404 idéntico con registro",
        "A-24": "CA-21.2 / RF-37: la resolución exige motivo y registra decisión, autor, estado anterior y nuevo",
    },
    # S5, incremento 3 (ADR-026, E-8 y E-9).
    "operacion": {
        "O-01": "RNF-26 / E-9.3 (P-30): sin plazo configurado para el tipo, la retención no borra nada y advierte",
        "O-02": "RNF-26 / RF-37: con el plazo cumplido, borra el archivo, marca la fila y escribe la bitácora (Sistema)",
        "O-03": "E-9.2: la retención no toca documentos de un expediente aprobado (ni antes del plazo)",
        "O-04": "RNF-22 / E-8: cada línea del registro trae los campos exigidos y ningún dato personal",
    },
}

GRUPOS_ACTIVOS = frozenset({"filtros", "puntaje", "acceso", "cierre", "operacion"})
UMBRAL = 0.60


def todas():
    return {regla for reglas in REGLAS.values() for regla in reglas}
