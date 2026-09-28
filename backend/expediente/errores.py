"""Errores del dominio del expediente.

Los mensajes se muestran a la persona (RNF-15, RNF-17): lenguaje del oficio,
acción correctiva cuando existe, sin nombres internos.
"""


class ErrorEstado(Exception):
    """La operación no está permitida en el estado actual del expediente (409). No se cambió nada."""

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


class ErroresValidacion(Exception):
    """Datos recibidos inválidos, por campo (400). No se guardó nada."""

    def __init__(self, errores):
        super().__init__(", ".join(sorted(errores)))
        self.errores = errores
