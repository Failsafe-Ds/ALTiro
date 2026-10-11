"""QA Pulido: crea datos ficticios (qa.pulido.*@example.com) en la pila en marcha. Uso: manage.py shell < preparar_datos.py"""
import datetime, json, uuid
from django.utils import timezone
from catalogo.models import Modalidad, Oficio, Servicio
from expediente.models import EstadoExpediente, Expediente, OficioMaestro
from identidad import servicios as si
from perfil import agenda, ocurrencias
from perfil.models import Cobertura, Disponibilidad, PerfilPublico, ServicioMaestro
from tickets.models import EstadoTicket, Ticket, MotivoCierre
from tickets.servicios import calcular_vence_en
from busqueda.cuentas_demo import contrasena_aleatoria
# Contraseña al azar en cada corrida, impresa una sola vez en el JSON final (ADR-028): nunca fija en el repositorio.
PWD = contrasena_aleatoria(); SUF = uuid.uuid4().hex[:6]
def rut(n):
    c = 31_000_000 + n; s = 0; f = 2
    for d in reversed(str(c)):
        s += int(d) * f; f = 2 if f == 7 else f + 1
    dv = 11 - s % 11
    return f"{c}-{'0' if dv == 11 else 'K' if dv == 10 else dv}"
serv = Servicio.objects.filter(oficio__codigo="pintura").first()
base = int(SUF, 16) % 900000
def maestro(n, nombre, tel):
    u = si.crear_cuenta_maestro(nombre=nombre, telefono=tel, rut=rut(base + n), contrasena=PWD)
    OficioMaestro.objects.create(maestro_id=u.pk, oficio_id=serv.oficio_id)
    Expediente.objects.filter(perfil_maestro_id=u.pk).update(estado=EstadoExpediente.APROBADO)
    ServicioMaestro.objects.create(maestro_id=u.pk, servicio=serv, modalidad=Modalidad.POR_TRABAJO, monto=25000)
    Cobertura.objects.create(maestro_id=u.pk, comuna_id=8101, es_base=True)
    [Disponibilidad.objects.create(maestro_id=u.pk, dia_semana=d, inicio_min=480, fin_min=720) for d in range(1, 8)]
    PerfilPublico.objects.filter(perfil_maestro_id=u.pk).update(foto=uuid.uuid4(), foto_actualizada_en=timezone.now())
    return u
M1 = maestro(1, "Maestro QA Pulido Uno", "+56 9 1000 0101"); M2 = maestro(2, "Maestro QA Pulido Dos", "+56 9 1000 0102")
from identidad.models import Usuario
A = Usuario.objects.get(correo="qa.pulido.cliente@example.com"); si.cambiar_contrasena(A, PWD)
B = si.crear_cuenta_cliente(nombre="Cliente QA Pulido B", telefono="+56 9 1000 0104", correo=f"qa.pulido.b.{SUF}@example.com", contrasena=PWD, comuna="8101")
MOD = si.crear_cuenta_administrativa(nombre="Moderador QA Pulido", correo=f"qa.pulido.mod.{SUF}@example.com", roles=["moderacion"], contrasena=PWD)
MOD2 = si.crear_cuenta_administrativa(nombre="Moderador QA Pulido Dos", correo=f"qa.pulido.mod2.{SUF}@example.com", roles=["moderacion"], contrasena=PWD)
GES = si.crear_cuenta_administrativa(nombre="Gestion QA Pulido", correo=f"qa.pulido.ges.{SUF}@example.com", roles=["control_gestion"], contrasena=PWD)
CUR = si.crear_cuenta_administrativa(nombre="Curatoria QA Pulido", correo=f"qa.pulido.cur.{SUF}@example.com", roles=["curatoria"], contrasena=PWD)
ahora = timezone.now(); hoy = ahora.astimezone(ocurrencias.ZONA).date()
sm = ServicioMaestro.objects.get(maestro_id=M1.pk)
def tk(estado, dias, enviado_dias_antes, motivo=None):
    f = hoy + datetime.timedelta(days=dias)
    i, e = ocurrencias.instante(f, 480), ocurrencias.instante(f, 720)
    env = ahora - datetime.timedelta(days=enviado_dias_antes)
    c = dict(cliente_id=A.pk, perfil_maestro_id=M1.pk, servicio_maestro=sm, modalidad=sm.modalidad, monto_publicado=sm.monto,
             fecha=f, inicio_min=480, fin_min=720, inicio_en=i, fin_en=e, comuna_id=8101, direccion="Pasaje Ficticio QA 123, depto 45",
             descripcion="Trabajo ficticio de QA Pulido", materiales=False, estado=estado, enviado_en=env, vence_en=calcular_vence_en(env, i))
    if estado in (EstadoTicket.ACEPTADO, EstadoTicket.FINALIZADO): c["aceptado_en"] = env
    if estado == EstadoTicket.FINALIZADO:
        c.update(finalizado_en=env, monto_final=sm.monto, monto_final_en=env, monto_final_autor_id=M1.pk)
    if estado == EstadoTicket.CERRADO: c.update(cerrado_en=env, motivo_cierre=motivo)
    return str(Ticket.objects.create(**c).ref)

CUR2 = si.crear_cuenta_administrativa(nombre="Comercial QA Pulido", correo=f"qa.pulido.com.{SUF}@example.com", roles=["comercial"], contrasena=PWD)
M3 = si.crear_cuenta_maestro(nombre="Maestro Revision QA Pulido", telefono="+56 9 1000 0105", rut=rut(base + 3), contrasena=PWD)
M4 = si.crear_cuenta_maestro(nombre="Maestro Revision QA Pulido Dos", telefono="+56 9 1000 0106", rut=rut(base + 4), contrasena=PWD)
DUAL = si.crear_cuenta_maestro(nombre="Dual QA Pulido", telefono="+56 9 1000 0107", rut=rut(base + 5), contrasena=PWD)
si.agregar_perfil_cliente(DUAL, comuna="8101", correo=f"qa.pulido.dual.{SUF}@example.com")
out = dict(pwd=PWD, COM=CUR2.correo, M3=rut(base+3), M4=rut(base+4), DUAL_RUT=rut(base+5), DUAL_CORREO=f"qa.pulido.dual.{SUF}@example.com", M3ref=str(Expediente.objects.get(perfil_maestro_id=M3.pk).ref) if hasattr(Expediente,"ref") else "", A=A.correo, B=B.correo, M1=rut(base + 1), M2=rut(base + 2), MOD=MOD.correo, MOD2=MOD2.correo, GES=GES.correo, CUR=CUR.correo,
  pend=tk("pendiente", 5, 0), acep=tk("aceptado", -1, 3), fin1=tk("finalizado", -10, 12), fin2=tk("finalizado", -12, 14), fin3=tk("finalizado", -14, 16),
  cerr=tk("cerrado", -8, 9, MotivoCierre.RECHAZADO_MAESTRO), m1_pub=str(PerfilPublico.objects.get(perfil_maestro_id=M1.pk).ref))
print("JSON:" + json.dumps(out))
