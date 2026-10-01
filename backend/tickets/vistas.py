"""Rutas de tickets y de sus avisos (RF-15 a RF-18, RF-28 parcial, RNF-07, RNF-08, CA-06.x, CA-15.1, CA-25.1; ADR-023; ADR-024).

- ``POST /api/tickets``: rol ``cliente``. Crea el ticket (``tickets.servicios``).
  201 con el ticket; 200 con el mismo ticket si ya existía ese pendiente (D-10).
  Errores en ``{mensaje, errores}`` (ADR-013, E-2): 400 por campo, 400 de
  E-9 ("No puedes pedirte un trabajo a ti mismo") y 409 si el horario ya no
  se puede pedir, con ``bloques``: los horarios libres vigentes (CA-06.2).
- ``GET /api/tickets/<uuid:ref>``: sin rol exigido; decide ``PoliticaTicket``
  (solo el cliente o el maestro de ese ticket). Cualquier otro recibe el 404
  idéntico con registro (CA-25.1; cierra DA-05).
- ``GET /api/clientes/tickets`` (rol ``cliente``) y ``GET /api/maestros/tickets``
  (rol ``maestro``): patrón "me", páginas de 20 (``pagina``) y filtro opcional
  ``estado`` (``pendiente``, ``aceptado``, ``finalizado`` o ``cerrado``) para las
  bandejas (incremento 7).
- ``GET /api/avisos`` y ``POST /api/avisos/vistos``: los avisos propios (ADR-024).
- ``POST /api/tickets/<uuid:ref>/aceptacion`` y ``.../rechazo`` (el maestro del
  ticket) y ``.../cancelacion`` (el cliente del ticket): ``tickets.transiciones``.
  Un tercero recibe el 404 idéntico con registro; la otra parte, 403 registrado
  (ADR-023, punto 6). 200 con el ticket; 409 accionable si el estado no lo permite.
- ``POST /api/tickets/<uuid:ref>/precio-final`` ``{monto}`` (el maestro del
  ticket), ``.../precio-final/aceptacion`` ``{monto}`` y ``.../precio-final/objecion``
  (sin cuerpo; el cliente del ticket): RF-26 a RF-28, CA-16.x; ADR-026, E-1 y E-5.
  Mismas políticas que las acciones anteriores (``ParteEquivocada`` para la otra parte).
  Sin ``estado``, las bandejas devuelven el historial completo (CA-08.1).

La respuesta depende de la relación con **ese** ticket (``tickets.serializacion``).
Todas con ``Cache-Control: no-store``.
"""
import re
import uuid


from autorizacion.acceso import obtener_autorizado
from autorizacion.decoradores import requiere_rol
from autorizacion.excepciones import ParteEquivocada
from comun.api import (
    ErrorSolicitud,
    ErroresDeCampo,
    MENSAJE_CLAVE_DESCONOCIDA,
    MENSAJE_VALOR_REPETIDO,
    leer_json,
    manejar_errores,
    metodos,
    respuesta_error,
    respuesta_json,
)
from expediente.errores import ErrorEstado
from perfil.servicios import _monto as validar_monto
from tickets import avisos as avisos_ticket
from tickets import serializacion, servicios, transiciones
from tickets.politicas import PoliticaTicket

CAMPOS_CREAR = {"maestro", "servicio", "comuna", "fecha", "inicio", "fin", "direccion", "descripcion", "materiales"}
CAMPOS_VISTOS = {"avisos"}
TAMANO_PAGINA = 20
PAGINA_MAXIMA = 9999
MAXIMO_VISTOS = 100

ESTADOS_FILTRO = ("pendiente", "aceptado", "finalizado", "cerrado")

MENSAJE_PAGINA_INVALIDA = "Vuelve a la primera página."
MENSAJE_ESTADO_INVALIDO = "Elige una de las pestañas de la lista."
MENSAJE_AVISOS_INVALIDOS = "No pudimos marcar tus avisos como vistos. Vuelve a cargar la página e inténtalo de nuevo."

_DIGITOS = re.compile(r"[0-9]{1,4}")


def _pagina(parametros):
    """``pagina`` (opcional, 1 a 9999). Otro parámetro: 400 general, sin repetirlo (ADR-013, E-2)."""
    if set(parametros) - {"pagina"}:
        raise ErrorSolicitud(MENSAJE_CLAVE_DESCONOCIDA)
    valores = parametros.getlist("pagina")
    if not valores:
        return 1
    if len(valores) > 1:
        raise ErroresDeCampo({"pagina": MENSAJE_VALOR_REPETIDO})
    if not _DIGITOS.fullmatch(valores[0]) or not 1 <= int(valores[0]) <= PAGINA_MAXIMA:
        raise ErroresDeCampo({"pagina": MENSAJE_PAGINA_INVALIDA})
    return int(valores[0])


def _lista_filtrada(parametros):
    """``pagina`` y ``estado``, ambos opcionales. Otro parámetro: 400 general (ADR-013, E-2)."""
    copia = parametros.copy()
    valores = copia.pop("estado", [])
    if len(valores) > 1:
        raise ErroresDeCampo({"estado": MENSAJE_VALOR_REPETIDO})
    if valores and valores[0] not in ESTADOS_FILTRO:
        raise ErroresDeCampo({"estado": MENSAJE_ESTADO_INVALIDO})
    return _pagina(copia), (valores[0] if valores else None)


def _paginado(consulta, pagina, clave, serializar):
    total = consulta.count()
    inicio = (pagina - 1) * TAMANO_PAGINA
    return {
        clave: [serializar(x) for x in consulta[inicio:inicio + TAMANO_PAGINA]],
        "pagina": pagina,
        "paginas": max(1, -(-total // TAMANO_PAGINA)),
        "total": total,
    }


@metodos("POST")
@requiere_rol("cliente")
@manejar_errores
def crear(request):
    datos = leer_json(request, CAMPOS_CREAR)
    try:
        ticket, creado = servicios.crear_ticket(request.usuario, datos)
    except servicios.AutoPedido as error:
        return respuesta_error(400, error.mensaje, {"maestro": error.mensaje})
    except servicios.HorarioNoDisponible as error:
        return respuesta_json({"mensaje": error.mensaje, "errores": {}, "bloques": error.bloques}, 409)
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)
    ticket = serializacion.consulta().get(pk=ticket.pk)
    return respuesta_json({"ticket": serializacion.para_cliente(ticket)}, 201 if creado else 200)


@metodos("GET")
def detalle(request, ref):
    ticket = obtener_autorizado(serializacion.consulta(), ref, request.usuario, PoliticaTicket())
    return respuesta_json({"ticket": serializacion.para(ticket, request.usuario)})


@metodos("GET")
@requiere_rol("cliente")
@manejar_errores
def del_cliente(request):
    pagina, estado = _lista_filtrada(request.GET)
    consulta = serializacion.consulta().filter(cliente_id=request.usuario.pk).order_by("-enviado_en", "-id")
    if estado:
        consulta = consulta.filter(estado=estado)
    return respuesta_json(_paginado(consulta, pagina, "tickets", serializacion.para_cliente))


@metodos("GET")
@requiere_rol("maestro")
@manejar_errores
def del_maestro(request):
    pagina, estado = _lista_filtrada(request.GET)
    consulta = serializacion.consulta().filter(perfil_maestro_id=request.usuario.pk).order_by("-enviado_en", "-id")
    if estado:
        consulta = consulta.filter(estado=estado)
    return respuesta_json(_paginado(consulta, pagina, "tickets", serializacion.para_maestro))


@metodos("GET")
@manejar_errores
def avisos(request):
    pagina = _pagina(request.GET)
    datos = _paginado(avisos_ticket.del_usuario(request.usuario.pk), pagina, "avisos", avisos_ticket.datos_aviso)
    datos["sin_ver"] = avisos_ticket.sin_ver(request.usuario.pk)
    return respuesta_json(datos)


def _refs_de_avisos(valor):
    if not isinstance(valor, list) or not 1 <= len(valor) <= MAXIMO_VISTOS:
        raise ErroresDeCampo({"avisos": MENSAJE_AVISOS_INVALIDOS})
    refs = set()
    for elemento in valor:
        try:
            refs.add(uuid.UUID(elemento) if isinstance(elemento, str) else None)
        except ValueError:
            refs.add(None)
    if None in refs:
        raise ErroresDeCampo({"avisos": MENSAJE_AVISOS_INVALIDOS})
    return refs


@metodos("POST")
@manejar_errores
def avisos_vistos(request):
    datos = leer_json(request, CAMPOS_VISTOS)
    refs = _refs_de_avisos(datos.get("avisos"))
    avisos_ticket.marcar_vistos(request.usuario.pk, refs)
    return respuesta_json({"sin_ver": avisos_ticket.sin_ver(request.usuario.pk)})


# --- Acciones sobre el ticket (incremento 5; ADR-023, puntos 3 y 6) ---

MENSAJE_SOLO_MAESTRO = "Solo el maestro que recibió este pedido puede aceptarlo o rechazarlo."
MENSAJE_SOLO_CLIENTE = "Solo el cliente que envió este pedido puede cancelarlo. Si no puedes tomarlo, recházalo."


MENSAJE_SOLO_MAESTRO_PRECIO = "Solo el maestro que hizo este trabajo puede registrar su precio final."
MENSAJE_SOLO_CLIENTE_PRECIO = (
    "Solo el cliente que pidió este trabajo puede aceptar o rechazar su precio final. "
    "Si cobraste otro monto, regístralo de nuevo."
)
CAMPOS_PRECIO = {"monto"}


def _sin_cuerpo(request):
    """Estas acciones no reciben datos: un cuerpo con claves se rechaza como en ADR-013, E-2."""
    if request.body:
        leer_json(request, set())


def _monto(request):
    """``{monto}``: entero en pesos de 1 a 10.000.000 (mismas reglas que el monto publicado, ADR-019)."""
    errores = {}
    monto = validar_monto(leer_json(request, CAMPOS_PRECIO), errores)
    if errores:
        raise ErroresDeCampo(errores)
    return (monto,)


def _sin_datos(request):
    _sin_cuerpo(request)
    return ()


def _accion(request, ref, del_maestro, hacer, leer=_sin_datos, mensajes=(MENSAJE_SOLO_MAESTRO, MENSAJE_SOLO_CLIENTE)):
    """Acción de una parte del ticket: ``hacer(ticket, usuario, *leer(request))``. El cuerpo se valida primero."""
    datos = leer(request)
    # Un tercero (incluidos los roles administrativos) recibe el 404 idéntico con registro (CA-25.1).
    ticket = obtener_autorizado(serializacion.consulta(), ref, request.usuario, PoliticaTicket())
    duena = ticket.perfil_maestro_id if del_maestro else ticket.cliente_id
    if request.usuario.pk != duena:
        mensaje = mensajes[0] if del_maestro else mensajes[1]
        raise ParteEquivocada(PoliticaTicket.entidad, ticket.ref, mensaje)
    try:
        hacer(ticket, request.usuario, *datos)
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)
    ticket = serializacion.consulta().get(pk=ticket.pk)
    return respuesta_json({"ticket": serializacion.para(ticket, request.usuario)})


@metodos("POST")
@manejar_errores
def aceptacion(request, ref):
    return _accion(request, ref, True, transiciones.aceptar)


@metodos("POST")
@manejar_errores
def rechazo(request, ref):
    return _accion(request, ref, True, transiciones.rechazar)


@metodos("POST")
@manejar_errores
def cancelacion(request, ref):
    return _accion(request, ref, False, transiciones.cancelar)


# --- Precio final (S5, incremento 1; ADR-026, E-1 y E-5) ---

MENSAJES_PRECIO = (MENSAJE_SOLO_MAESTRO_PRECIO, MENSAJE_SOLO_CLIENTE_PRECIO)


@metodos("POST")
@manejar_errores
def precio_final(request, ref):
    return _accion(request, ref, True, transiciones.registrar_precio, _monto, MENSAJES_PRECIO)


@metodos("POST")
@manejar_errores
def precio_aceptacion(request, ref):
    return _accion(request, ref, False, transiciones.aceptar_precio, _monto, MENSAJES_PRECIO)


@metodos("POST")
@manejar_errores
def precio_objecion(request, ref):
    return _accion(request, ref, False, transiciones.objetar_precio, _sin_datos, MENSAJES_PRECIO)
