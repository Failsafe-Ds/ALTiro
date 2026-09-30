import datetime
from tickets import transiciones
from tickets.models import Ticket, TicketEvento, AvisoTicket
D=datetime.timedelta(seconds=1)
t5=Ticket.objects.get(ref="7839b262-e387-4464-8578-cea54d384084"); t6=Ticket.objects.get(ref="714a79a4-bf2a-439d-a43c-80a904b30cba")
print("vence T5", t5.vence_en.isoformat(), "T6", t6.vence_en.isoformat(), "enviado T5", t5.enviado_en.isoformat(), "inicio T6", t6.inicio_en.isoformat())
print("estado actual:", estado() if False else "")
print("formula T6: inicio-4h == vence:", t6.inicio_en-datetime.timedelta(hours=4)==t6.vence_en, "| T5: enviado+24h == vence:", t5.enviado_en+datetime.timedelta(hours=24)==t5.vence_en)
def estado():
    return {n:(Ticket.objects.get(pk=t.pk).estado, Ticket.objects.get(pk=t.pk).motivo_cierre) for n,t in (("T5",t5),("T6",t6))}
# 1 segundo antes del vencimiento de T6: nada de T5/T6 se cierra
for n,t in (("T5",t5),("T6",t6)):
    ev=list(TicketEvento.objects.filter(ticket_id=t.pk).order_by("id").values("estado_anterior","estado_nuevo","motivo","autor_tipo"))
    print(n,"eventos:",ev)
    av=list(AvisoTicket.objects.filter(ticket_id=t.pk).values_list("destinatario_id","tipo"))
    print(n,"avisos:",[a[1] for a in av], "destinatarios distintos:", len({a[0] for a in av}))
