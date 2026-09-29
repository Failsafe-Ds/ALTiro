"""Errores del dominio del catálogo (RNF-15: mensajes accionables, sin nombres internos)."""


class ErrorVersion(Exception):
    """El registro cambió desde que se leyó (``version`` distinta): 409. No se cambió nada (ADR-018, punto 4)."""

    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje
