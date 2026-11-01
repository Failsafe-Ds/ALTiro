"""Limitador de frecuencia genérico (ADR-007, E-1; RNF-10 como base, M-07, M-08).

Cuenta eventos por ``(ambito, clave)`` en ventanas móviles. ``consumir``
verifica y, si no hay espera, registra el evento en la misma transacción, con
un bloqueo consultivo por ``(ambito, clave)``: dos peticiones simultáneas no
superan el límite. Un rechazo (429) **no** se cuenta (ADR-007, punto 2): las
filas por clave nunca pasan del límite de cada ventana.

Ámbitos en uso:

- ``registro``: registros sin sesión (cliente y postulación de maestro) por origen.
- ``correo``: intentos de guardar un correo con sesión (``/api/cuenta/correo`` y
  el primer correo de ``/api/clientes``), con claves ``cuenta:<id>`` y
  ``origen:<ip>`` (ADR-027, E-2).
- ``denegado``: accesos denegados o referencias inexistentes de un usuario autenticado.

Los mensajes del chat no usan esta tabla: se cuentan desde ``mensaje`` mismo
(``espera_segun`` con las fechas de envío).

La hora sale de Python (``timezone.now()``), no de SQL (ADR-014).
"""
import hashlib
import math
from datetime import timedelta

from django.db import connection, transaction
from django.utils import timezone

from identidad.models import EventoFrecuencia

RETENCION = timedelta(hours=24)

# (límite, ventana): con ``límite`` eventos dentro de ``ventana`` se espera.
REGLAS_REGISTRO = ((20, timedelta(hours=1)),)
REGLAS_CORREO = REGLAS_REGISTRO  # no más laxa que la del registro (ADR-027, E-2)
REGLAS_DENEGADO = ((20, timedelta(minutes=10)),)


def espera_segun(fechas, reglas, ahora):
    """Tiempo que falta para poder actuar (``timedelta``) o ``None``.

    ``fechas`` son los eventos ya contados, en orden ascendente. Para cada
    regla, si hay ``límite`` o más dentro de la ventana, se libera cuando el
    evento ``límite``-ésimo desde el final sale de ella.
    """
    fin = None
    for limite, ventana in reglas:
        dentro = [f for f in fechas if f > ahora - ventana]
        if len(dentro) >= limite:
            libre = dentro[-limite] + ventana
            if fin is None or libre > fin:
                fin = libre
    return None if fin is None else fin - ahora


def minutos(espera):
    """Minutos de espera redondeados hacia arriba (mínimo 1)."""
    return max(1, math.ceil(espera.total_seconds() / 60))


def segundos(espera):
    """Segundos de espera redondeados hacia arriba (mínimo 1)."""
    return max(1, math.ceil(espera.total_seconds()))


def bloquear(ambito, clave):
    """Bloqueo consultivo de PostgreSQL hasta el fin de la transacción en curso."""
    llave = int.from_bytes(hashlib.sha256(f"frecuencia:{ambito}:{clave}".encode()).digest()[:8], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [llave])


@transaction.atomic
def consumir(ambito, clave, reglas):
    """Registra un evento si hay cupo y devuelve ``None``; si no, la espera (sin registrar)."""
    clave = str(clave)
    bloquear(ambito, clave)
    ahora = timezone.now()
    mayor = max(ventana for _, ventana in reglas)
    fechas = list(
        EventoFrecuencia.objects.filter(ambito=ambito, clave=clave, fecha__gt=ahora - mayor)
        .order_by("fecha")
        .values_list("fecha", flat=True)
    )
    espera = espera_segun(fechas, reglas, ahora)
    if espera is not None:
        return espera
    EventoFrecuencia.objects.filter(fecha__lt=ahora - RETENCION).delete()
    EventoFrecuencia.objects.create(ambito=ambito, clave=clave, fecha=ahora)
    return None
