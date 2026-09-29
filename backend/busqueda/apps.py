from django.apps import AppConfig


class BusquedaConfig(AppConfig):
    """Búsqueda de maestros (RF-09 a RF-13; ADR-022). Sin modelos propios."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "busqueda"
