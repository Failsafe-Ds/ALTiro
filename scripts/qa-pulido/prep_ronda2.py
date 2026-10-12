"""QA ronda 2 (v0.6.3): cuentas ficticias qa.r2.*@example.com en altiro-dev. Uso: docker compose exec -T app python manage.py shell < prep_ronda2.py
La contraseña es aleatoria por corrida y se imprime una sola vez en el JSON (datos2.json, no versionado)."""
import datetime, json, uuid
from django.utils import timezone
from catalogo.models import Modalidad, Servicio
from expediente.models import EstadoExpediente, Expediente, OficioMaestro
from identidad import servicios as si
from perfil import ocurrencias
from perfil.models import Cobertura, Disponibilidad, PerfilPublico, ServicioMaestro
from tickets.models import EstadoTicket, Ticket
from tickets.servicios import calcular_vence_en
from busqueda.cuentas_demo import contrasena_aleatoria
PWD = contrasena_aleatoria(); SUF = uuid.uuid4().hex[:6]; base = int(SUF, 16) % 900000
def rut(n):
    c = 33_000_000 + n; s = 0; f = 2
    for d in reversed(str(c)):
        s += int(d) * f; f = 2 if f == 7 else f + 1
    dv = 11 - s % 11
    return f"{c}-{'0' if dv == 11 else 'K' if dv == 10 else dv}"
serv = Servicio.objects.filter(oficio__codigo="pintura").first()
def aprobar(u):
    OficioMaestro.objects.create(maestro_id=u.pk, oficio_id=serv.oficio_id)
    Expediente.objects.filter(perfil_maestro_id=u.pk).update(estado=EstadoExpediente.APROBADO)
    ServicioMaestro.objects.create(maestro_id=u.pk, servicio=serv, modalidad=Modalidad.POR_TRABAJO, monto=25000)
    Cobertura.objects.create(maestro_id=u.pk, comuna_id=8101, es_base=True)
    [Disponibilidad.objects.create(maestro_id=u.pk, dia_semana=d, inicio_min=480, fin_min=720) for d in range(1, 8)]
    PerfilPublico.objects.filter(perfil_maestro_id=u.pk).update(foto=uuid.uuid4(), foto_actualizada_en=timezone.now())
M1 = si.crear_cuenta_maestro(nombre="Maestro QA Ronda Dos", telefono="+56 9 1000 0201", rut=rut(base + 1), contrasena=PWD); aprobar(M1)
DUAL = si.crear_cuenta_maestro(nombre="Dual QA Ronda Dos", telefono="+56 9 1000 0202", rut=rut(base + 2), contrasena=PWD)
DCORREO = f"qa.r2.dual.{SUF}@example.com"; si.agregar_perfil_cliente(DUAL, comuna="8101", correo=DCORREO); aprobar(DUAL)
C1 = si.crear_cuenta_cliente(nombre="Cliente QA Ronda Dos", telefono="+56 9 1000 0203", correo=f"qa.r2.cliente.{SUF}@example.com", contrasena=PWD, comuna="8101")
CP = si.crear_cuenta_cliente(nombre="Postulante QA Ronda Dos", telefono="+56 9 1000 0204", correo=f"qa.r2.post.{SUF}@example.com", contrasena=PWD, comuna="8101")
CP2 = si.crear_cuenta_cliente(nombre="Postulante QA Ronda Dos B", telefono="+56 9 1000 0205", correo=f"qa.r2.post2.{SUF}@example.com", contrasena=PWD, comuna="8101")
ahora = timezone.now(); hoy = ahora.astimezone(ocurrencias.ZONA).date()
def tk(cli, mae, estado, dias, antes):
    sm = ServicioMaestro.objects.get(maestro_id=mae.pk); f = hoy + datetime.timedelta(days=dias)
    i, e = ocurrencias.instante(f, 480), ocurrencias.instante(f, 720); env = ahora - datetime.timedelta(days=antes)
    c = dict(cliente_id=cli.pk, perfil_maestro_id=mae.pk, servicio_maestro=sm, modalidad=sm.modalidad, monto_publicado=sm.monto, fecha=f, inicio_min=480, fin_min=720,
             inicio_en=i, fin_en=e, comuna_id=8101, direccion="Pasaje Ficticio QA 123", descripcion="Trabajo ficticio QA ronda 2", materiales=False, estado=estado, enviado_en=env, vence_en=calcular_vence_en(env, i), aceptado_en=env)
    if estado == EstadoTicket.FINALIZADO: c.update(finalizado_en=env, monto_final=sm.monto, monto_final_en=env, monto_final_autor_id=mae.pk)
    return str(Ticket.objects.create(**c).ref)
out = dict(pwd=PWD, M1=rut(base + 1), DUAL=DCORREO, C1=C1.correo, CP=CP.correo, CP2=CP2.correo,
  a_dual_maestro=tk(C1, DUAL, EstadoTicket.ACEPTADO, -1, 3), a_dual_cliente=tk(DUAL, M1, EstadoTicket.ACEPTADO, -1, 3),
  f_dual_maestro=tk(C1, DUAL, EstadoTicket.FINALIZADO, -10, 12), f_dual_cliente=tk(DUAL, M1, EstadoTicket.FINALIZADO, -12, 14),
  rut_post=rut(base + 3), rut_post2=rut(base + 4))
print("JSON:" + json.dumps(out))
