"""Políticas de autorización por recurso (RNF-07, CA-25.1, CA-25.2; propuesta del S1, §5, punto 3).

Una política decide por la **relación del usuario con el recurso** (identidad,
propiedad, rol, estado y finalidad), no por el rol global ni por el perfil
activo en la interfaz. Tener un rol es condición necesaria, no suficiente: un
rol administrativo no exime de las reglas de conflicto de interés (ADR-013,
punto 2). Por defecto, toda política deniega.

En S1 no hay políticas de negocio. Puntos de extensión previstos:

- Documento del maestro (S2, CA-25.2): solo el maestro dueño y curatoría;
  la descarga usa enlaces firmados (``autorizacion.enlaces``, RNF-06).
- Expediente del maestro (S2): curatoría revisa, pero un maestro no cambia el
  estado de su propio expediente aunque tenga el rol ``curatoria`` (HU-19,
  CA-19.4).
- Orden/ticket (S4, CA-25.1): solo el cliente y el maestro del ticket; la
  dirección y el teléfono del cliente no viajan mientras esté ``Pendiente``.
- Conversación (S5): las partes del ticket aceptado; moderación solo con una
  disputa abierta.

Otras reglas solo se agregan con respaldo en el informe o en una decisión
documentada.
"""


class Politica:
    """Base: ``entidad`` nombra el tipo de recurso en ``acceso_denegado``.

    - ``conflicto``: verdadero si el usuario no puede actuar sobre el recurso
      por conflicto de interés aunque tenga el rol (ADR-011, E-2). Por defecto
      no hay conflicto. ``obtener_autorizado`` lo evalúa antes que ``permite``.
    - ``permite``: por defecto, deniega.
    """

    entidad = None
    # Mensaje accionable del 403 por conflicto de interés; ``None`` usa el del expediente.
    mensaje_conflicto = None

    def conflicto(self, usuario, objeto):
        return False

    def permite(self, usuario, objeto):
        return False
