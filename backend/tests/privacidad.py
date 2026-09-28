"""Verificación de privacidad de respuestas JSON (RNF-08, base; propuesta del S1, §5, punto 5).

``assert_campos_ausentes`` revisa el JSON crudo de la respuesta, ya
decodificado (así detecta también valores escritos con escapes ``\\uXXXX``),
a cualquier profundidad:

- falla si aparece alguna clave de ``campos``;
- falla si algún texto contiene alguno de ``valores``.
"""
import json


def _recorrer(dato, ruta="$"):
    """Produce (ruta, clave o None, valor) para cada elemento del JSON."""
    if isinstance(dato, dict):
        for clave, valor in dato.items():
            yield ruta, clave, None
            yield from _recorrer(valor, f"{ruta}.{clave}")
    elif isinstance(dato, list):
        for indice, valor in enumerate(dato):
            yield from _recorrer(valor, f"{ruta}[{indice}]")
    else:
        yield ruta, None, dato


def assert_campos_ausentes(respuesta, campos, valores=()):
    datos = json.loads(respuesta.content.decode("utf-8"))
    campos = set(campos)
    valores = [v for v in valores if v]
    hallazgos = []
    for ruta, clave, valor in _recorrer(datos):
        if clave is not None and clave in campos:
            hallazgos.append(f"clave {clave!r} en {ruta}")
        if clave is not None and any(v in clave for v in valores):
            hallazgos.append(f"valor prohibido en una clave de {ruta}")
        if isinstance(valor, str) and any(v in valor for v in valores):
            hallazgos.append(f"valor prohibido en {ruta}")
    assert not hallazgos, "La respuesta expone datos que deben estar ausentes: " + "; ".join(hallazgos)
