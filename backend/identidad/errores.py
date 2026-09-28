"""Errores del dominio de identidad.

Los mensajes están pensados para mostrarse a la persona (RNF-15): indican el
campo y la acción correctiva, sin nombres internos ni SQL.
"""


class ErrorValidacion(Exception):
    """Dato recibido inválido o regla de negocio incumplida. No se creó nada."""

    def __init__(self, campo, mensaje):
        super().__init__(f"{campo}: {mensaje}")
        self.campo = campo
        self.mensaje = mensaje


class InvarianteVioladaError(Exception):
    """Error de programación: una vía de creación dejó una cuenta incoherente.

    Se lanza dentro de la transacción, por lo que provoca rollback.
    """

    def __init__(self, violaciones):
        super().__init__("; ".join(violaciones))
        self.violaciones = violaciones
