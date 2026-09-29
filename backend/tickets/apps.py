from django.apps import AppConfig


class TicketsConfig(AppConfig):
    """Ticket y orden, historial y avisos de tickets (RF-15 a RF-24; ADR-023; ADR-024)."""

    name = "tickets"
    default_auto_field = "django.db.models.BigAutoField"
