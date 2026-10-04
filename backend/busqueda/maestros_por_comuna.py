"""Maestros FICTICIOS publicados en cada comuna, para probar los filtros de la búsqueda (ADR-028, Enmienda E-1).

Lo llama ``python manage.py cargar_datos_demo --maestros-por-comuna N [--region R] [--comuna C ...]``.
Garantiza al menos ``N`` maestros ficticios publicados con **comuna base** en
cada comuna (o en las de la región ``R``, o solo en las comunas ``C``). Hasta
``MAXIMO_POR_COMUNA`` por comuna, para demos con decenas de resultados en las
comunas grandes (ADR-028, E-2). Es idempotente: cuenta los maestros
de demostración que ya están publicados con base en cada comuna (los de este
módulo y los de ``cuentas_demo``) y crea solo los que faltan.

Variedad pensada para RF-09 a RF-12 (ADR-022):

- oficios: el oficio principal rota con la comuna y el puesto, así en cada
  comuna hay oficios distintos y otros quedan sin maestro con base allí (para
  ver las sugerencias). A veces se agrega un segundo oficio;
- cobertura: la comuna base y, a veces, 1 o 2 comunas de la misma provincia
  (cercanía 100 o 60 del puntaje). Desde el puesto ``PUESTO_ZONA_DENSA``
  (solo con N alto), de 3 a 6 comunas de la provincia, primero las pedidas con
  ``--comuna``: así una búsqueda en Concepción o Santiago trae decenas de
  maestros de cada oficio (E-2);
- agenda: mañana, tarde, jornada completa o vespertino, en días distintos;
  algunos maestros tienen un bloque próximo **ocupado** por un ticket aceptado;
- modalidad y monto variados según lo que admite el catálogo;
- calificación: algunos tienen órdenes finalizadas en el pasado con la
  evaluación del cliente (desempate de RF-11);
- oficios regulados (gas y electricidad): con licencia SEC vigente cargada
  con el servicio real de documentos cifrados (``ficticios``).

Rotulado: "Maestro Demo NNNN (datos de prueba)", RUT sintéticos
48.000.000 + comuna·100 + puesto (48.110.100 a 49.630.599: no chocan con
``cuentas_demo``, desde 49.990.001, ni con ``generar_volumen_prueba``, desde
50.000.000), teléfonos ficticios, sin correo y con contraseña inutilizable.
Los tickets usan un grupo fijo de clientes ficticios, también sin ingreso.
No escribe la bitácora (ADR-010) ni avisos.
"""
import datetime
import random
import secrets
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from busqueda import ficticios
from busqueda.cuentas_demo import MOTIVO
from catalogo.models import ServicioModalidad
from evaluaciones.models import Evaluacion, ParteEvaluacion
from expediente import vigencia
from expediente.models import EstadoExpediente, Expediente
from identidad import servicios as identidad
from identidad.models import PerfilMaestro, Usuario
from perfil import ocurrencias
from perfil.models import Cobertura, Disponibilidad, PerfilPublico, ServicioMaestro
from territorio.models import Comuna, Region
from tickets.models import EstadoTicket, Ticket, TicketEvento

MAXIMO_POR_COMUNA = 99  # ADR-028, E-2; siempre menor que PUESTOS
# Zona densa (ADR-028, E-2): desde este puesto, el maestro atiende de 3 a 6
# comunas más de su provincia, primero las de la lista ``--comuna``, como un
# maestro de una ciudad grande que se mueve por varias comunas.
PUESTO_ZONA_DENSA = 40
EXTRA_ZONA_DENSA = (3, 6)
POR_DEFECTO = 3
RUT_BASE = 48_000_000
# Cuerpos de RUT de los maestros de demostración (este módulo y cuentas_demo).
RANGO_DEMO = range(48_000_000, 50_000_000)
PUESTOS = 100  # puestos posibles por comuna en el esquema de RUT
CLIENTES = 20
LOTE_TICKETS = 200
# Horarios (minutos múltiplos de 30 sin cruzar la medianoche, ADR-020).
HORARIOS = ((540, 780), (840, 1080), (510, 1050), (1020, 1260))  # mañana, tarde, jornada, vespertino
DIAS = ((1, 2, 3, 4, 5), (1, 3, 5), (2, 4, 6), (6, 7), (1, 2, 3, 4, 5, 6), (4, 5, 6, 7), (1, 2, 3, 4, 5, 6, 7))
FACTORES_MONTO = (0.7, 0.85, 1.0, 1.0, 1.15, 1.3, 1.6)


@dataclass
class Resumen:
    comunas: int = 0
    maestros: int = 0
    licencias: int = 0
    tickets: int = 0
    evaluaciones: int = 0
    minimo: int = 0
    faltantes: list = field(default_factory=list)


def cuerpo_rut(comuna, puesto):
    return RUT_BASE + comuna * PUESTOS + puesto


def _cuerpo(rut):
    """Cuerpo numérico de un RUT guardado sin puntos ni guion (``12345678K``), o ``None``."""
    return int(rut[:-1]) if rut[:-1].isdigit() else None


def demo_publicados_por_comuna(codigos):
    """``{comuna: cantidad}`` de maestros de demostración publicados con base en esas comunas.

    Publicado según la regla de elegibilidad (ADR-019): expediente aprobado,
    comuna base y foto; todos tienen servicios visibles por construcción.
    """
    aprobados = set(
        Expediente.objects.filter(estado=EstadoExpediente.APROBADO).values_list("perfil_maestro_id", flat=True)
    )
    con_foto = set(PerfilPublico.objects.filter(foto__isnull=False).values_list("perfil_maestro_id", flat=True))
    conteo = {}
    for comuna, maestro, rut in Cobertura.objects.filter(es_base=True, comuna_id__in=codigos).values_list(
        "comuna_id", "maestro_id", "maestro__rut"
    ):
        if _cuerpo(rut) in RANGO_DEMO and maestro in aprobados and maestro in con_foto:
            conteo[comuna] = conteo.get(comuna, 0) + 1
    return conteo


def _ruts_usados():
    return {
        c for c in (_cuerpo(r) for r in PerfilMaestro.objects.filter(rut__startswith="4").values_list("rut", flat=True))
        if c is not None and c in RANGO_DEMO
    }


def _agenda(azar):
    dias = azar.choice(DIAS)
    if len(dias) > 2 and azar.random() < 0.3:
        corte = len(dias) // 2  # mañana unos días y tarde los otros
        return [(d, *HORARIOS[0]) for d in dias[:corte]] + [(d, *HORARIOS[1]) for d in dias[corte:]]
    inicio, fin = azar.choice(HORARIOS)
    return [(d, inicio, fin) for d in dias]


def _servicios(azar, comuna, puesto, oficios, por_oficio):
    """Oficio principal rotando por comuna y puesto; a veces un segundo oficio. Hasta 3 servicios."""
    principal = oficios[(comuna + puesto * 3) % len(oficios)]
    elegidos = [principal]
    if azar.random() < 0.35:
        elegidos.append(azar.choice([o for o in oficios if o != principal]))
    candidatos = [s for o in elegidos for s in por_oficio[o]]
    return candidatos[:3]


def _precios(azar, servicios, admitidas):
    modalidades, montos = [], []
    for servicio in servicios:
        modalidad, referencia = azar.choice(admitidas[servicio.pk])
        modalidades.append(modalidad)
        montos.append(max(1000, round(int(referencia) * azar.choice(FACTORES_MONTO) / 500) * 500))
    return modalidades, montos


def _clientes():
    """Grupo fijo de clientes ficticios sin ingreso para los tickets (idempotente por correo)."""
    clientes = []
    comunas = list(Comuna.objects.order_by("codigo").values_list("codigo", flat=True))
    for numero in range(CLIENTES):
        correo = f"cliente.volumen.demo.{numero + 1:02d}@example.com"
        usuario = Usuario.objects.filter(correo=correo).first()
        if usuario is None:
            with transaction.atomic():
                usuario = identidad.crear_cuenta_cliente(
                    nombre=f"Cliente Demo Volumen {numero + 1:02d} (datos de prueba)",
                    telefono=f"+56 9 0003 {numero + 1:04d}",
                    correo=correo,
                    contrasena=secrets.token_urlsafe(24),
                    comuna=str(comunas[(numero * 17) % len(comunas)]),
                )
                usuario.set_unusable_password()
                usuario.save(update_fields=["password"])
        clientes.append(usuario)
    return clientes


def _tickets_de(azar, usuario, base, clientes, ahora, hoy):
    """Tickets del maestro recién creado: a veces uno aceptado próximo (ocupa un bloque) y 0 a 3
    finalizados en las últimas 4 semanas, con evaluación del cliente en la mayoría.
    Devuelve ``[(ticket, pasos, notas | None)]``."""
    servicios = list(ServicioMaestro.objects.filter(maestro_id=usuario.pk).order_by("pk"))
    patrones = list(Disponibilidad.objects.filter(maestro_id=usuario.pk))
    planes = []

    def nuevo(una, estado, enviado):
        return ficticios.ticket(
            perfil=usuario, cliente=azar.choice(clientes), servicio=azar.choice(servicios), comuna=base, una=una,
            estado=estado, enviado_en=enviado, direccion=f"Calle Ficticia {azar.randint(1, 999)} (datos de prueba)",
            descripcion="Trabajo ficticio de demostración.", materiales=azar.random() < 0.5,
        )

    if azar.random() < 0.35:
        futuras = [o for o in ocurrencias.ocurrencias(patrones, hoy, 7) if ocurrencias.empieza_con_anticipacion(o, ahora)]
        if futuras:
            una = azar.choice(futuras[:4])
            enviado = ahora - datetime.timedelta(minutes=azar.randint(30, 600))
            t = nuevo(una, EstadoTicket.ACEPTADO, enviado)
            t.aceptado_en = ficticios.entre(azar, enviado, ahora)
            planes.append((t, [(t.aceptado_en, EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO, usuario.pk, None)], None))
    pasadas = [o for o in ocurrencias.ocurrencias(patrones, hoy - datetime.timedelta(days=28), 28) if o.fin_en < ahora]
    calidad = azar.choice((2, 3, 4, 4, 5, 5))
    for una in azar.sample(pasadas, min(len(pasadas), azar.choice((0, 0, 1, 2, 3)))):
        enviado = ficticios.en_utc(una.inicio_en) - datetime.timedelta(hours=azar.randint(6, 48))
        t = nuevo(una, EstadoTicket.PENDIENTE, enviado)
        pasos = ficticios.finalizar(t, usuario.pk, ficticios.entre(azar, enviado, t.vence_en),
                                    min(ficticios.en_utc(una.fin_en) + datetime.timedelta(hours=1), ahora))
        notas = None
        if azar.random() < 0.8:
            notas = tuple(max(1, min(5, calidad + azar.choice((-1, 0, 0, 1)))) for _ in range(3))
        planes.append((t, pasos, notas))
    return planes


def _guardar_tickets(planes, ahora):
    """Inserta en lote tickets, historial y evaluaciones del cliente. Devuelve ``(tickets, evaluaciones)``."""
    if not planes:
        return 0, 0
    with transaction.atomic():
        tickets = Ticket.objects.bulk_create([t for t, _, _ in planes])
        eventos, evaluaciones = [], []
        for t, pasos, notas in planes:
            eventos.append(ficticios.evento(t, t.enviado_en, None, EstadoTicket.PENDIENTE, t.cliente_id))
            eventos += [ficticios.evento(t, *paso) for paso in pasos]
            if notas is not None:
                evaluaciones.append(Evaluacion(
                    ticket_id=t.pk, parte=ParteEvaluacion.CLIENTE, autor_id=t.cliente_id,
                    evaluado_id=t.perfil_maestro_id, puntualidad=notas[0], trabajo=notas[1], cordialidad=notas[2],
                    creada_en=min(t.finalizado_en + datetime.timedelta(hours=2), ahora),
                ))
        TicketEvento.objects.bulk_create(eventos, batch_size=1000)
        Evaluacion.objects.bulk_create(evaluaciones, batch_size=1000)
    return len(tickets), len(evaluaciones)


def cargar_maestros_por_comuna(n=POR_DEFECTO, region=None, ahora=None, comunas=None, avance=None):
    """Crea los maestros ficticios que faltan para tener al menos ``n`` con base en cada comuna.

    ``region`` (código) limita a sus comunas; ``comunas`` (códigos) limita aún
    más (opción ``--comuna`` y las pruebas). ``avance(texto)`` recibe una línea por región.
    Devuelve un ``Resumen``. Cada maestro se crea en su propia transacción; sus
    tickets y evaluaciones, en lotes.
    """
    if not 1 <= n <= MAXIMO_POR_COMUNA:
        raise ValueError(f"La cantidad de maestros por comuna debe estar entre 1 y {MAXIMO_POR_COMUNA}.")
    consulta = Comuna.objects.select_related("provincia").order_by("codigo")
    if region is not None:
        if not Region.objects.filter(codigo=region).exists():
            raise ValueError("No existe una región con ese código (usa el código CUT, por ejemplo 8 o 13).")
        consulta = consulta.filter(provincia__region_id=region)
    if comunas is not None:
        consulta = consulta.filter(codigo__in=comunas)
    lista = list(consulta)
    foco = frozenset(comunas or ())
    if comunas is not None and len(lista) != len(set(comunas)):
        raise ValueError("Alguna comuna no existe o no es de esa región (usa el código CUT, por ejemplo 8101).")
    por_oficio = ficticios.servicios_por_oficio(incluir_regulados=True)
    if len(por_oficio) < 2:
        raise ValueError("El catálogo no tiene servicios suficientes: ejecuta antes cargar_datos_demo.")
    oficios = sorted(por_oficio, key=lambda o: (o.orden, o.pk))
    admitidas = {}
    for servicio_id, modalidad, precio in ServicioModalidad.objects.values_list(
        "servicio_id", "modalidad", "precio_referencia"
    ):
        admitidas.setdefault(servicio_id, []).append((modalidad, precio))
    vecinas = {}
    for comuna in Comuna.objects.filter(provincia_id__in={c.provincia_id for c in lista}).order_by("codigo"):
        vecinas.setdefault(comuna.provincia_id, []).append(comuna.codigo)

    ahora = ahora or timezone.now()
    hoy = vigencia.hoy_negocio(ahora)
    existentes = demo_publicados_por_comuna([c.codigo for c in lista])
    usados = _ruts_usados()
    numero = sum(1 for c in usados if c < 49_990_000)
    resumen = Resumen(comunas=len(lista))
    clientes, planes, region_actual = None, [], None
    for comuna in lista:
        region_comuna = comuna.provincia.region_id
        if avance and region_comuna != region_actual:
            region_actual = region_comuna
            avance(f"Región {region_comuna}: maestros nuevos hasta ahora {resumen.maestros}.")
        faltan, puesto = n - existentes.get(comuna.codigo, 0), 0
        while faltan > 0:
            while cuerpo_rut(comuna.codigo, puesto) in usados:
                puesto += 1
            if puesto >= PUESTOS:
                raise ValueError(f"La comuna {comuna.codigo} no tiene más RUT de demostración disponibles.")
            cuerpo = cuerpo_rut(comuna.codigo, puesto)
            azar = random.Random(f"demo-comuna-{comuna.codigo}-{puesto}")
            servicios = _servicios(azar, comuna.codigo, puesto, oficios, por_oficio)
            modalidades, montos = _precios(azar, servicios, admitidas)
            otras = [c for c in vecinas[comuna.provincia_id] if c != comuna.codigo]
            if puesto >= PUESTO_ZONA_DENSA:
                densas = [c for c in otras if c in foco] or otras
                extra = azar.sample(densas, min(len(densas), azar.randint(*EXTRA_ZONA_DENSA)))
            else:
                extra = azar.sample(otras, min(len(otras), azar.choice((0, 0, 1, 2))))
            numero += 1
            usuario = ficticios.crear_maestro_publicado(
                nombre=f"{'Maestro' if numero % 2 else 'Maestra'} Demo {numero:04d} (datos de prueba)",
                telefono=f"+56 9 {(cuerpo - RUT_BASE) // 10_000:04d} {(cuerpo - RUT_BASE) % 10_000:04d}",
                rut=ficticios.rut_con_dv(cuerpo),
                servicios=servicios, montos=montos, modalidades=modalidades,
                base=comuna.codigo, extra=extra, agenda=_agenda(azar),
                foto=ficticios.foto_sintetica(azar), motivo=MOTIVO, licencias=True,
            )
            usados.add(cuerpo)
            resumen.maestros += 1
            resumen.licencias += len({s.oficio for s in servicios if s.oficio.regulado})
            if clientes is None:
                clientes = _clientes()
            planes += _tickets_de(azar, usuario, comuna.codigo, clientes, ahora, hoy)
            if len(planes) >= LOTE_TICKETS:
                tickets, evaluaciones = _guardar_tickets(planes, ahora)
                resumen.tickets, resumen.evaluaciones = resumen.tickets + tickets, resumen.evaluaciones + evaluaciones
                planes = []
            faltan -= 1
    tickets, evaluaciones = _guardar_tickets(planes, ahora)
    resumen.tickets += tickets
    resumen.evaluaciones += evaluaciones
    finales = demo_publicados_por_comuna([c.codigo for c in lista])
    resumen.minimo = min((finales.get(c.codigo, 0) for c in lista), default=0)
    resumen.faltantes = [c.codigo for c in lista if finales.get(c.codigo, 0) < n]
    return resumen
