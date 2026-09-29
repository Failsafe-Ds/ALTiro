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
  (rol ``maestro``): versión mínima, patrón "me", páginas de 20 (``pagina``).
- ``GET /api/avisos`` y ``POST /api/avisos/vistos``: los avisos propios (ADR-024).

La respuesta depende de la relación con **ese** ticket (``tickets.serializacion``).
Todas con ``Cache-Control: no-store``.
"""
import re
import uuid

from django.http import JsonResponse

from autorizacion.acceso import obtener_autorizado
from autorizacion.decoradores import requiere_rol
from comun.api import (
    MENSAJE_CLAVE_DESCONOCIDA,
    MENSAJE_VALOR_REPETIDO,
    ErroresDeCampo,
    ErrorSolicitud,
    leer_json,
    manejar_errores,
    metodos,
    respuesta_error,
)
from expediente.errores import ErrorEstado
from tickets import avisos as avisos_ticket
from tickets import serializacion, servicios
from tickets.politicas import PoliticaTicket

CAMPOS_CREAR = {"maestro", "servicio", "comuna", "fecha", "inicio", "fin", "direccion", "descripcion", "materiales"}
CAMPOS_VISTOS = {"avisos"}
TAMANO_PAGINA = 20
PAGINA_MAXIMA = 9999
MAXIMO_VISTOS = 100

MENSAJE_PAGINA_INVALIDA = "Vuelve a la primera página."
MENSAJE_AVISOS_INVALIDOS = "No pudimos marcar tus avisos como vistos. Vuelve a cargar la página e inténtalo de nuevo."

_DIGITOS = re.compile(r"[0-9]{1,4}")


def _json(datos, estado=200):
    respuesta = JsonResponse(datos, status=estado)
    respuesta["Cache-Control"] = "no-store"
    return respuesta


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
        return _json({"mensaje": error.mensaje, "errores": {}, "bloques": error.bloques}, 409)
    except ErrorEstado as error:
        return respuesta_error(409, error.mensaje)
    ticket = serializacion.consulta().get(pk=ticket.pk)
    return _json({"ticket": serializacion.para_cliente(ticket)}, 201 if creado else 200)


@metodos("GET")
def detalle(request, ref):
    ticket = obtener_autorizado(serializacion.consulta(), ref, request.usuario, PoliticaTicket())
    return _json({"ticket": serializacion.para(ticket, request.usuario)})


@metodos("GET")
@requiere_rol("cliente")
@manejar_errores
def del_cliente(request):
    pagina = _pagina(request.GET)
    consulta = serializacion.consulta().filter(cliente_id=request.usuario.pk).order_by("-enviado_en", "-id")
    return _json(_paginado(consulta, pagina, "tickets", serializacion.para_cliente))


@metodos("GET")
@requiere_rol("maestro")
@manejar_errores
def del_maestro(request):
    pagina = _pagina(request.GET)
    consulta = serializacion.consulta().filter(perfil_maestro_id=request.usuario.pk).order_by("-enviado_en", "-id")
    return _json(_paginado(consulta, pagina, "tickets", serializacion.para_maestro))


@metodos("GET")
@manejar_errores
def avisos(request):
    pagina = _pagina(request.GET)
    datos = _paginado(avisos_ticket.del_usuario(request.usuario.pk), pagina, "avisos", avisos_ticket.datos_aviso)
    datos["sin_ver"] = avisos_ticket.sin_ver(request.usuario.pk)
    return _json(datos)


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
    return _json({"sin_ver": avisos_ticket.sin_ver(request.usuario.pk)})
