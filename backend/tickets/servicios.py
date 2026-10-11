"""Creación del ticket: transición "— → pendiente" (RF-15 a RF-18, HU-06, CA-06.1, CA-06.2, CA-06.4; ADR-023, puntos 1 a 4).

``crear_ticket(usuario, datos, ahora)`` recibe los datos ya filtrados por la
lista de campos permitidos (``tickets.vistas.CAMPOS_CREAR``) y exige, en el
servidor y en este orden:

1. Datos completos y bien formados (CA-06.4): ``maestro`` (ref pública del
   perfil), ``servicio`` (ref del catálogo, como la entrega la ficha),
   ``comuna`` (código CUT), ``fecha``, ``inicio`` y ``fin`` (el horario de la
   ficha, en "HH:MM" de 24 horas y dentro del horizonte de 14 días),
   ``direccion``, ``descripcion`` y ``materiales`` (booleano, **sin valor por
   defecto**). Si falta o no sirve un dato: ``ErroresDeCampo`` (400 por campo).
2. Nadie se pide un trabajo a sí mismo (ADR-013, E-9): ``AutoPedido`` (400).
3. Con el expediente del maestro **bloqueado** (``select_for_update``; ADR-023,
   punto 4: el mismo bloqueo que tomará la aceptación), la idempotencia de
   D-10: si el cliente ya tiene un pendiente con ese maestro para ese inicio,
   se devuelve ese mismo ticket sin crear nada (200). Si ese pendiente ya
   venció, se cierra en ese momento con su motivo (protección al actuar,
   ADR-016 E-1) y se responde ``ErrorEstado`` (409).
4. Maestro publicado (regla única, ``perfil.publicacion``), servicio
   **visible** y comuna en su cobertura: 400 en el campo. Un maestro que no
   existe y uno que no está publicado reciben el mismo mensaje.
5. Horario ofrecible (ADR-022, punto 1; CA-06.2): una ocurrencia exacta de su
   agenda, que empieza en **más** de 4 horas (RF-16) y no se cruza con un
   ticket aceptado o finalizado (CA-14.3). Si no: ``HorarioNoDisponible``
   (409), con los horarios libres vigentes para ofrecer otros (CA-06.2).
6. Crea el ticket con las copias de modalidad, monto y bloque (RF-15) y
   ``vence_en``; el primer ``ticket_evento`` y el aviso ``ticket_nuevo`` para
   el maestro (RF-18), todo en la misma transacción.

Las demás transiciones (aceptar, rechazar, cancelar y cerrar) están en
``tickets.transiciones``.

Mensajes en el lenguaje de pantalla (RNF-15, RNF-17; ADR-024, punto 4):
"pedido" por ticket y "horario" por bloque.
"""
import datetime
import re
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from comun.api import MENSAJE_TEXTO_INVALIDO, ErroresDeCampo
from comun.texto import FALTA, INVALIDO, LARGO, limpiar_texto, recortar
from expediente import vigencia
from expediente.errores import ErrorEstado
from expediente.models import Expediente
from perfil import agenda, ocupacion, ocurrencias, publicacion
from perfil.models import Cobertura, PerfilPublico
from territorio.models import Comuna
from tickets import transiciones
from tickets.avisos import MOTIVOS_PARA_CLIENTE
from tickets.models import (
    ANTICIPACION_MINIMA,
    LARGO_DESCRIPCION,
    LARGO_DIRECCION,
    PLAZO_RESPUESTA,
    AutorTipo,
    AvisoTicket,
    EstadoTicket,
    Ticket,
    TicketEvento,
    TipoAvisoTicket,
)

MENSAJE_MAESTRO = "No encontramos a este maestro o ya no está recibiendo pedidos. Busca otro maestro."
MENSAJE_AUTOPEDIDO = "No puedes pedirte un trabajo a ti mismo."
MENSAJE_SERVICIO = "Este maestro no ofrece ese servicio. Elige uno de los servicios que aparecen en su ficha."
MENSAJE_COMUNA_FALTA = "Elige la comuna donde necesitas el trabajo."
MENSAJE_COMUNA_INVALIDA = "Elige una comuna de la lista."
MENSAJE_COMUNA_FUERA = "Este maestro no trabaja en esa comuna. Elige una de las comunas donde trabaja."
MENSAJE_FECHA_FALTA = "Elige el día del trabajo."
MENSAJE_FECHA_INVALIDA = "Elige un día del calendario."
MENSAJE_FECHA_FUERA = "Elige un día entre hoy y los próximos {dias} días."
MENSAJE_FIN_NO_POSTERIOR = "La hora de término debe ser después de la hora de inicio. Por ejemplo, de 08:00 a 12:00."
MENSAJE_DIRECCION_FALTA = "Escribe la dirección donde se hará el trabajo."
MENSAJE_DIRECCION_LARGA = "La dirección es muy larga: escríbela en {largo} caracteres o menos."
MENSAJE_DESCRIPCION_FALTA = "Cuenta qué trabajo necesitas."
MENSAJE_DESCRIPCION_LARGA = "La descripción es muy larga: escríbela en {largo} caracteres o menos."
MENSAJE_MATERIALES = "Responde si tienes los materiales para el trabajo: sí o no."
MENSAJE_HORARIO_NO_EXISTE = "Ese horario ya no está en la agenda del maestro. Elige uno de sus horarios libres."
MENSAJE_HORARIO_PRONTO = (
    "Ese horario empieza en 4 horas o menos y ya no se puede pedir. Elige uno de sus horarios libres."
)
MENSAJE_HORARIO_OCUPADO = (
    "Ese horario ya no está libre: el maestro tomó otro trabajo. Elige uno de sus horarios libres."
)
MENSAJE_PENDIENTE_VENCIDO = (
    "Ya le habías enviado este pedido a este maestro y se cerró: {motivo}. "
    "Si todavía necesitas el trabajo, envíalo de nuevo o elige otro horario."
)

_FECHA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DIGITOS = re.compile(r"[0-9]{1,6}")
# Caracteres de control (salvo el salto de línea y el tabulador de la descripción).


class AutoPedido(Exception):
    """ADR-013, E-9: el cliente es el mismo maestro (400)."""

    mensaje = MENSAJE_AUTOPEDIDO


class HorarioNoDisponible(Exception):
    """CA-06.2: el horario ya no se puede pedir (409). ``bloques``: los horarios libres vigentes."""

    def __init__(self, mensaje, bloques):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.bloques = bloques


def calcular_vence_en(enviado_en, inicio_en):
    """ADR-023, punto 1: ``LEAST(enviado_en + 24 h, inicio_en - 4 h)`` (RF-21, RF-22).

    Se calcula en UTC: sumar o restar horas a una fecha con zona America/Santiago
    es aritmética de reloj de pared y se desvía una hora al cruzar el cambio de
    horario (DEF-QA-005). ADR-020: los plazos se miden en tiempo real.
    """
    enviado_en = enviado_en.astimezone(datetime.timezone.utc)
    inicio_en = inicio_en.astimezone(datetime.timezone.utc)
    return min(enviado_en + PLAZO_RESPUESTA, inicio_en - ANTICIPACION_MINIMA)


# --- 1. Datos ---


def _uuid(valor):
    try:
        return uuid.UUID(valor) if isinstance(valor, str) else None
    except ValueError:
        return None


def _perfil_publico(valor, errores):
    ref = _uuid(valor)
    perfil = PerfilPublico.objects.filter(ref=ref).first() if ref else None
    if perfil is None:
        errores["maestro"] = MENSAJE_MAESTRO
    return perfil


def _servicio_ref(valor, errores):
    ref = _uuid(valor)
    if ref is None:
        errores["servicio"] = MENSAJE_SERVICIO
    return ref


def _comuna(valor, errores):
    valor = recortar(valor)
    if valor in (None, ""):
        errores["comuna"] = MENSAJE_COMUNA_FALTA
        return None
    if isinstance(valor, int) and not isinstance(valor, bool):
        valor = str(valor)
    comuna = None
    if isinstance(valor, str) and _DIGITOS.fullmatch(valor):
        comuna = Comuna.objects.filter(codigo=int(valor)).first()
    if comuna is None:
        errores["comuna"] = MENSAJE_COMUNA_INVALIDA
    return comuna


def _fecha(valor, hoy, errores):
    valor = recortar(valor)
    if valor in (None, ""):
        errores["fecha"] = MENSAJE_FECHA_FALTA
        return None
    try:
        fecha = datetime.date.fromisoformat(valor) if isinstance(valor, str) and _FECHA.fullmatch(valor) else None
    except ValueError:
        fecha = None
    if fecha is None:
        errores["fecha"] = MENSAJE_FECHA_INVALIDA
        return None
    # Horizonte de 14 días: de hoy a hoy+13 (ADR-022, D-5; propuesta del S4, §11, aclaración 2).
    if not hoy <= fecha < hoy + datetime.timedelta(days=ocurrencias.HORIZONTE_DIAS):
        errores["fecha"] = MENSAJE_FECHA_FUERA.format(dias=ocurrencias.HORIZONTE_DIAS - 1)
        return None
    return fecha


def _hora(valor, campo, errores):
    try:
        return agenda.minutos_de_hora(valor)
    except agenda.HoraInvalida as error:
        errores[campo] = error.mensaje
        return None


def _texto(valor, campo, largo, falta, largo_excedido, errores, una_linea):
    texto, problema = limpiar_texto(valor, largo, una_linea=una_linea)
    if problema:
        errores[campo] = {
            FALTA: falta,
            INVALIDO: MENSAJE_TEXTO_INVALIDO,
            LARGO: largo_excedido.format(largo=f"{largo:,}".replace(",", ".")),
        }[problema]
    return texto


def _materiales(valor, errores):
    """CA-06.4: la casilla debe venir respondida (``true`` o ``false``); no hay valor por defecto."""
    if not isinstance(valor, bool):
        errores["materiales"] = MENSAJE_MATERIALES
        return None
    return valor


def leer_datos(datos, hoy):
    """Datos validados del pedido, o ``ErroresDeCampo`` con todos los campos que fallan."""
    errores = {}
    perfil = _perfil_publico(datos.get("maestro"), errores)
    servicio_ref = _servicio_ref(datos.get("servicio"), errores)
    comuna = _comuna(datos.get("comuna"), errores)
    fecha = _fecha(datos.get("fecha"), hoy, errores)
    inicio = _hora(datos.get("inicio"), "inicio", errores)
    fin = _hora(datos.get("fin"), "fin", errores)
    if inicio is not None and inicio >= ocurrencias.MINUTOS_DIA:
        errores["inicio"] = agenda.MENSAJE_INICIO_FIN_DE_DIA
    elif inicio is not None and fin is not None and fin <= inicio:
        errores["fin"] = MENSAJE_FIN_NO_POSTERIOR
    direccion = _texto(
        datos.get("direccion"), "direccion", LARGO_DIRECCION, MENSAJE_DIRECCION_FALTA, MENSAJE_DIRECCION_LARGA,
        errores, una_linea=True,
    )
    descripcion = _texto(
        datos.get("descripcion"), "descripcion", LARGO_DESCRIPCION, MENSAJE_DESCRIPCION_FALTA,
        MENSAJE_DESCRIPCION_LARGA, errores, una_linea=False,
    )
    materiales = _materiales(datos.get("materiales"), errores)
    if errores:
        raise ErroresDeCampo(errores)
    return {
        "perfil": perfil, "servicio_ref": servicio_ref, "comuna": comuna, "fecha": fecha, "inicio": inicio,
        "fin": fin, "direccion": direccion, "descripcion": descripcion, "materiales": materiales,
    }


# --- 4 y 5. Reglas con el maestro bloqueado ---


def _servicio_visible(maestro_id, servicio_ref, hoy):
    """El ``ServicioMaestro`` activo y **visible** del maestro para ese servicio del catálogo, o ``None``."""
    for servicio_maestro in publicacion.servicios_activos(maestro_id).filter(servicio__ref=servicio_ref):
        if not publicacion.motivos_no_visible(servicio_maestro, hoy, elegible=True):
            return servicio_maestro
    return None


def horarios_libres(maestro_id, ahora, hoy):
    """Horarios libres de la ficha (ADR-022, punto 4): los que se ofrecen en el 409 de CA-06.2."""
    from perfil.vistas_publicas import ESTADO_LIBRE, bloques_de_ficha

    return [
        {"fecha": b["fecha"], "inicio": b["inicio"], "fin": b["fin"]}
        for b in bloques_de_ficha(maestro_id, ahora, hoy)
        if b["estado"] == ESTADO_LIBRE
    ]


def _ocurrencia_ofrecible(maestro_id, fecha, inicio, fin, ahora, hoy):
    """La ocurrencia exacta pedida, si es ofrecible; si no, ``HorarioNoDisponible`` (409)."""
    patrones = agenda.bloques_activos(maestro_id).filter(dia_semana=fecha.isoweekday(), inicio_min=inicio, fin_min=fin)
    una = next(
        (
            o for o in (ocurrencias.ocurrencia(p.ref, p.dia_semana, p.inicio_min, p.fin_min, fecha) for p in patrones)
            if o is not None
        ),
        None,
    )
    mensaje = None
    if una is None:
        mensaje = MENSAJE_HORARIO_NO_EXISTE
    elif not ocurrencias.empieza_con_anticipacion(una, ahora):
        mensaje = MENSAJE_HORARIO_PRONTO
    else:
        ocupados = ocupacion.rangos_ocupados([maestro_id], una.inicio_en, una.fin_en).get(maestro_id, ())
        if ocurrencias.ocupada(una, ocupados):
            mensaje = MENSAJE_HORARIO_OCUPADO
    if mensaje is not None:
        raise HorarioNoDisponible(mensaje, horarios_libres(maestro_id, ahora, hoy))
    return una


def _pendiente_existente(cliente_id, maestro_id, inicio_en):
    return Ticket.objects.filter(
        cliente_id=cliente_id, perfil_maestro_id=maestro_id, inicio_en=inicio_en, estado=EstadoTicket.PENDIENTE
    ).first()


def _idempotente(existente, ahora):
    """D-10: el mismo pedido ya existe. Devuelve ``(existente, False)``, o ``None`` si estaba vencido.

    Protección al actuar (ADR-016 E-1, incremento 6): un pendiente vencido se
    cierra aquí mismo con su motivo; quien llama confirma la transacción y
    responde 409 (``PedidoRepetidoVencido``).
    """
    if transiciones.cerrar_si_vencido(existente, ahora):
        return None
    return existente, False


# --- Caso de uso ---


def crear_ticket(usuario, datos, ahora=None):
    """Crea el ticket del cliente ``usuario``. Devuelve ``(ticket, creado)``; ``creado`` es falso si ya existía."""
    ahora = ahora or timezone.now()
    hoy = vigencia.hoy_negocio(ahora)
    pedido = leer_datos(datos, hoy)
    maestro_id = pedido["perfil"].perfil_maestro_id
    if maestro_id == usuario.pk:
        raise AutoPedido()
    with transaction.atomic():
        resultado = _crear_con_maestro_bloqueado(usuario, pedido, maestro_id, ahora, hoy)
    if isinstance(resultado, Ticket):
        # Protección al actuar (incremento 6): el cierre del pendiente vencido ya quedó guardado.
        raise ErrorEstado(MENSAJE_PENDIENTE_VENCIDO.format(motivo=MOTIVOS_PARA_CLIENTE[resultado.motivo_cierre]))
    return resultado


def _crear_con_maestro_bloqueado(usuario, pedido, maestro_id, ahora, hoy):
    """Pasos 3 a 6, dentro de la transacción. Devuelve ``(ticket, creado)``, o el pendiente vencido que cerró."""
    fecha, inicio, fin = pedido["fecha"], pedido["inicio"], pedido["fin"]
    # ADR-023, punto 4: primero el expediente del maestro (serializa con la aceptación y con curatoría).
    if Expediente.objects.select_for_update().filter(perfil_maestro_id=maestro_id).first() is None:
        raise ErroresDeCampo({"maestro": MENSAJE_MAESTRO})
    inicio_en = ocurrencias.instante(fecha, inicio)
    if inicio_en is not None:
        existente = _pendiente_existente(usuario.pk, maestro_id, inicio_en)
        if existente is not None:
            return _idempotente(existente, ahora) or existente
    errores = {}
    servicio_maestro = None
    if not publicacion.maestro_publicado(maestro_id, hoy):
        errores["maestro"] = MENSAJE_MAESTRO
    else:
        servicio_maestro = _servicio_visible(maestro_id, pedido["servicio_ref"], hoy)
        if servicio_maestro is None:
            errores["servicio"] = MENSAJE_SERVICIO
        if not Cobertura.objects.filter(maestro_id=maestro_id, comuna=pedido["comuna"]).exists():
            errores["comuna"] = MENSAJE_COMUNA_FUERA
    if errores:
        raise ErroresDeCampo(errores)
    una = _ocurrencia_ofrecible(maestro_id, fecha, inicio, fin, ahora, hoy)
    try:
        with transaction.atomic():
            ticket = Ticket.objects.create(
                cliente_id=usuario.pk,
                perfil_maestro_id=maestro_id,
                servicio_maestro=servicio_maestro,
                modalidad=servicio_maestro.modalidad,
                monto_publicado=servicio_maestro.monto,
                fecha=una.fecha,
                inicio_min=una.inicio_min,
                fin_min=una.fin_min,
                inicio_en=una.inicio_en,
                fin_en=una.fin_en,
                comuna=pedido["comuna"],
                direccion=pedido["direccion"],
                descripcion=pedido["descripcion"],
                materiales=pedido["materiales"],
                estado=EstadoTicket.PENDIENTE,
                enviado_en=ahora,
                vence_en=calcular_vence_en(ahora, una.inicio_en),
            )
    except IntegrityError:
        # Resguardo del único parcial de D-10; con el bloqueo por maestro no debería ocurrir.
        existente = _pendiente_existente(usuario.pk, maestro_id, una.inicio_en)
        if existente is None:
            raise
        return _idempotente(existente, ahora) or existente
    TicketEvento.objects.create(
        ticket_id=ticket.pk,
        fecha=ahora,
        estado_anterior=None,
        estado_nuevo=EstadoTicket.PENDIENTE,
        motivo=None,
        autor_tipo=AutorTipo.USUARIO,
        autor_id=usuario.pk,
    )
    # RF-18: el aviso nace en la misma transacción que el ticket.
    AvisoTicket.objects.create(
        ticket=ticket, destinatario_id=maestro_id, tipo=TipoAvisoTicket.TICKET_NUEVO, creado_en=ahora
    )
    return ticket, True
