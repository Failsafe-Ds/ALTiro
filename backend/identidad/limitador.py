"""Limitación de intentos de inicio de sesión (RNF-10, M-07, M-08, ADR-007).

Reglas aprobadas (ADR-007, «Decisión»):
- Par (origen, HMAC del identificador): 5 fallos dentro de 15 minutos bloquean
  ese par durante 15 minutos contados desde el quinto fallo.
- Origen solo: 20 fallos dentro de 15 minutos lo bloquean 15 minutos.
- Solo cuentan los 401. Los 400 y los 429 no se registran.
- Un inicio de sesión correcto no reinicia el contador.
- Se guardan solo fallos, sin correo ni RUT en claro; al registrar un fallo se
  borran los de más de 24 horas.
- Nunca se deshabilita la cuenta: el bloqueo es del origen (M-07).

La hora sale de Python (``timezone.now()``), no de SQL (ADR-014).
"""
import ipaddress
import math
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import salted_hmac

from identidad.models import IntentoAutenticacion

VENTANA = timedelta(minutes=15)
DURACION_BLOQUEO = timedelta(minutes=15)
LIMITE_POR_IDENTIFICADOR = 5
LIMITE_POR_ORIGEN = 20
RETENCION = timedelta(hours=24)

_ORIGEN_DESCONOCIDO = "0.0.0.0"


def origen_de(request):
    """IP del cliente. ``X-Real-IP`` solo se usa si viene del proxy propio (ADR-007, punto 5)."""
    candidatos = []
    if settings.ALTIRO_CONFIAR_X_REAL_IP:
        candidatos.append(request.META.get("HTTP_X_REAL_IP", ""))
    candidatos.append(request.META.get("REMOTE_ADDR", ""))
    for candidato in candidatos:
        try:
            return str(ipaddress.ip_address(candidato.strip()))
        except ValueError:
            continue
    return _ORIGEN_DESCONOCIDO


def clave_de(tipo, valor):
    """HMAC del identificador normalizado: nunca se guarda el correo ni el RUT en claro."""
    return salted_hmac("altiro.limitador.identificador", f"{tipo}:{valor}", algorithm="sha256").hexdigest()


def _fin_de_bloqueo(fechas, limite, ahora):
    """Fin del bloqueo vigente según una serie de fallos ordenada, o ``None``."""
    fin = None
    for i in range(limite - 1, len(fechas)):
        if fechas[i] - fechas[i - limite + 1] <= VENTANA:
            candidato = fechas[i] + DURACION_BLOQUEO
            if candidato > ahora and (fin is None or candidato > fin):
                fin = candidato
    return fin


def minutos_de_bloqueo(origen, clave):
    """Minutos que faltan para desbloquear (redondeados hacia arriba), o 0 si no hay bloqueo."""
    ahora = timezone.now()
    recientes = IntentoAutenticacion.objects.filter(
        origen=origen, fecha__gt=ahora - VENTANA - DURACION_BLOQUEO
    ).order_by("fecha")
    del_origen = list(recientes.values_list("fecha", flat=True))
    del_par = list(recientes.filter(clave=clave).values_list("fecha", flat=True))
    fines = [
        fin
        for fin in (
            _fin_de_bloqueo(del_par, LIMITE_POR_IDENTIFICADOR, ahora),
            _fin_de_bloqueo(del_origen, LIMITE_POR_ORIGEN, ahora),
        )
        if fin is not None
    ]
    if not fines:
        return 0
    return max(1, math.ceil((max(fines) - ahora).total_seconds() / 60))


def registrar_fallo(origen, clave):
    ahora = timezone.now()
    IntentoAutenticacion.objects.filter(fecha__lt=ahora - RETENCION).delete()
    IntentoAutenticacion.objects.create(origen=origen, clave=clave, fecha=ahora)
