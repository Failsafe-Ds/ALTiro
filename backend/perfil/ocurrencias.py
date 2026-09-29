"""Ocurrencias concretas de la agenda semanal (ADR-020, punto 1 y Enmienda E-1; ADR-022, punto 1).

Módulo **puro**: no hace consultas. Convierte el par (patrón semanal, fecha)
en instantes reales en ``America/Santiago``, que es el contrato con la
búsqueda, la ficha (S4, incremento 2) y el ticket (S4, incremento 4).

Reglas de E-1:

- ``fin_min = 1440`` corresponde a las 00:00 del día siguiente.
- **Hora inexistente** (salto hacia adelante del horario de verano): la
  ocurrencia no se ofrece ese día. Supuesto de este incremento: basta con que
  el inicio **o** el fin caigan en la hora que no existe (por ejemplo, un
  bloque que termina a las 24:00 del sábado en que el reloj salta de 24:00 a
  01:00) para no ofrecerla; así nunca se muestra un rango con una hora que no
  existe en el reloj.
- **Hora repetida** (fin del horario de verano): se usa ``fold=0``, la primera
  de las dos.
- Los plazos (4 horas de RF-16; 24 horas de RF-21) se miden en tiempo real
  transcurrido: los instantes son ``datetime`` con zona y se comparan en UTC.
  "Hoy" y el día de la semana se calculan en Santiago.

``ofrecible`` resume la regla de ADR-022, punto 1: una ocurrencia es
ofrecible si su bloque está activo (lo decide quien carga los patrones), no se
cruza con un rango ocupado y empieza en **más** de 4 horas.
"""
import datetime
from dataclasses import dataclass
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Santiago")
UTC = datetime.timezone.utc
MINUTOS_DIA = 24 * 60
# RF-16, V-03: no se ofrece un bloque que comienza en 4 horas o menos.
ANTICIPACION_MINIMA = datetime.timedelta(hours=4)
# ADR-022, punto 4 (P-19): la ficha y el filtro de bloque miran 14 días, hoy incluido.
HORIZONTE_DIAS = 14


@dataclass(frozen=True)
class Ocurrencia:
    """Bloque concreto: el patrón ``patron`` (su ``ref``) en la fecha ``fecha``."""

    patron: object
    fecha: datetime.date
    inicio_min: int
    fin_min: int
    inicio_en: datetime.datetime
    fin_en: datetime.datetime


def instante(fecha, minutos):
    """Instante (con zona de Santiago) de ``fecha`` a los ``minutos`` desde su medianoche.

    ``minutos = 1440`` es las 00:00 del día siguiente. Devuelve ``None`` si esa
    hora no existe en el reloj de Santiago (salto del horario de verano). En
    una hora repetida devuelve la primera (``fold=0``).
    """
    dia = fecha + datetime.timedelta(days=minutos // MINUTOS_DIA)
    resto = minutos % MINUTOS_DIA
    local = datetime.datetime.combine(dia, datetime.time(resto // 60, resto % 60), tzinfo=ZONA)  # fold=0
    # Una hora inexistente no sobrevive la ida y vuelta por UTC.
    vuelta = local.astimezone(UTC).astimezone(ZONA)
    if vuelta.replace(tzinfo=None) != local.replace(tzinfo=None):
        return None
    return local


def ocurrencia(patron, dia_semana, inicio_min, fin_min, fecha):
    """``Ocurrencia`` del patrón en ``fecha``, o ``None`` si ese día no le toca o no existe."""
    if fecha.isoweekday() != dia_semana:
        return None
    inicio = instante(fecha, inicio_min)
    fin = instante(fecha, fin_min)
    if inicio is None or fin is None:
        return None
    return Ocurrencia(patron, fecha, inicio_min, fin_min, inicio, fin)


def fechas(desde, dias):
    return [desde + datetime.timedelta(days=n) for n in range(dias)]


def ocurrencias(patrones, desde, dias):
    """Ocurrencias de ``patrones`` en ``dias`` fechas desde ``desde``, por fecha y hora de inicio.

    ``patrones``: objetos con ``ref``, ``dia_semana``, ``inicio_min`` y ``fin_min``
    (filas de ``Disponibilidad`` activas).
    """
    encontradas = []
    for fecha in fechas(desde, dias):
        for patron in patrones:
            una = ocurrencia(patron.ref, patron.dia_semana, patron.inicio_min, patron.fin_min, fecha)
            if una is not None:
                encontradas.append(una)
    encontradas.sort(key=lambda o: (o.fecha, o.inicio_min, o.fin_min, str(o.patron)))
    return encontradas


def empieza_con_anticipacion(una, ahora):
    """RF-16: empieza en **más** de 4 horas reales desde ``ahora``."""
    return una.inicio_en - ahora > ANTICIPACION_MINIMA


def ocupada(una, rangos_ocupados):
    """Se cruza con algún rango ``(inicio_en, fin_en)`` ocupado (CA-14.3). Bordes que se tocan no se cruzan."""
    return any(inicio < una.fin_en and una.inicio_en < fin for inicio, fin in rangos_ocupados)


def ofrecible(una, ahora, rangos_ocupados):
    """ADR-022, punto 1: libre y con más de 4 horas de anticipación."""
    return empieza_con_anticipacion(una, ahora) and not ocupada(una, rangos_ocupados)
