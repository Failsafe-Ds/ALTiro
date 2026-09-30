"""Pruebas agregadas por QA en el cierre del Sprint 4 (docs/testing/cierre-sprint-4.md).

DEF-QA-005: ``tickets.servicios.calcular_vence_en`` resta 4 horas a ``inicio_en``
(un instante con zona America/Santiago) con aritmética de reloj de pared. Si el
salto del horario de verano cae entre el instante y su resta, el resultado
difiere en una hora de la fórmula ``LEAST(enviado_en + 24 h, inicio_en - 4 h)``
(tiempo transcurrido) que exige el CHECK ``ticket_vence_en_formula`` (ADR-023,
punto 1; ADR-020, los plazos se miden en tiempo real): el ticket no se puede
crear. Corregido: ``calcular_vence_en`` y ``motivo_vencimiento`` calculan en UTC.

Datos ficticios (``tests.tickets_ayudas``).
"""
import datetime

import pytest
import time_machine

from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from tickets.models import EstadoTicket, Ticket

pytestmark = pytest.mark.django_db

UTC = datetime.timezone.utc
# Sábado 5 de septiembre de 2026, 21:00 en Santiago (UTC-4). A las 24:00 los relojes
# pasan a la 01:00 (UTC-3): el domingo 6 a las 03:00 está a 5 horas de tiempo transcurrido.
ENVIO = datetime.datetime(2026, 9, 5, 21, 0, tzinfo=ay.ocurrencias.ZONA)
DOMINGO = datetime.date(2026, 9, 6)


@pytest.mark.regla("C-08")
def test_def_qa_005_ticket_para_un_bloque_justo_despues_del_salto_de_horario_de_verano():
    with time_machine.travel(ENVIO, tick=False):
        catalogo = ay.catalogo_basico()
        maestro = tk.maestro_con_agenda(catalogo, bloques=((7, "03:00", "05:00"),))
        tk.cliente()
        sesion = tk.sesion(tk.CORREO_CLIENTE)
        datos = tk.pedido(maestro, catalogo, fecha=DOMINGO.isoformat(), inicio="03:00", fin="05:00")
        respuesta = tk.enviar(sesion, datos)
    assert respuesta.status_code == 201, respuesta.content
    ticket = Ticket.objects.get(estado=EstadoTicket.PENDIENTE)
    esperado = min(ticket.enviado_en + datetime.timedelta(hours=24), ticket.inicio_en.astimezone(UTC) - datetime.timedelta(hours=4))
    assert ticket.vence_en == esperado
