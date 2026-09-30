"""Denuncias y moderación (S5, incremento 6).

HU-21, HU-25; RF-31, RF-37; CA-21.1, CA-21.2, CA-25.3; M-04; ADR-026, E-4;
propuesta del S5, §3.3 y §3.4. Datos ficticios (``tests.tickets_ayudas``).
"""
import uuid

import pytest
import time_machine
from django.db import IntegrityError, transaction

from autorizacion.models import RegistroAccesoDenegado
from bitacora.models import Bitacora
from comun.api import respuesta_no_encontrado
from evaluaciones import calificacion
from evaluaciones.models import Denuncia, EstadoDenuncia, EstadoEvaluacion, Evaluacion, ParteEvaluacion
from evaluaciones.politicas import MENSAJE_CONFLICTO
from identidad.models import Rol, UsuarioRol
from mensajeria.models import Mensaje
from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from tests.ayudas import TEL_A, post_json, sin_texto_prohibido
from tickets.models import AvisoTicket, EstadoTicket, TipoAvisoTicket

pytestmark = pytest.mark.django_db

AHORA = tk.AHORA
NO_ENCONTRADO = respuesta_no_encontrado().content
URL_MOD = "/api/moderacion/denuncias"
CORREO_MOD = "moderacion@example.com"


@pytest.fixture
def reloj():
    with time_machine.travel(AHORA, tick=False):
        yield


@pytest.fixture
def catalogo(reloj):
    return ay.catalogo_basico()


@pytest.fixture
def maestro(catalogo):
    return tk.maestro_con_agenda(catalogo)


@pytest.fixture
def cliente(reloj):
    return tk.cliente()


@pytest.fixture
def sesion_cliente(cliente):
    return tk.sesion(tk.CORREO_CLIENTE)


@pytest.fixture
def sesion_maestro(maestro):
    return tk.sesion(ay.rut(1))


@pytest.fixture
def moderador(reloj):
    return tk.administrativo(Rol.MODERACION, CORREO_MOD)


@pytest.fixture
def sesion_mod(moderador):
    return tk.sesion(CORREO_MOD)


@pytest.fixture
def ticket(cliente, maestro):
    return tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.FINALIZADO)


@pytest.fixture
def evaluacion(ticket, cliente, maestro):
    """El cliente evaluó al maestro; el maestro es la parte evaluada."""
    Mensaje.objects.create(ticket_id=ticket.pk, autor_id=cliente.pk, texto="¿Llega a las 8?", enviado_en=AHORA,
                           clave_envio=uuid.uuid4())
    return Evaluacion.objects.create(ticket=ticket, parte=ParteEvaluacion.CLIENTE, autor_id=cliente.pk,
                                     evaluado_id=maestro.pk, puntualidad=1, trabajo=1, cordialidad=1,
                                     comentario="Comentario ofensivo de prueba")


@pytest.fixture
def denuncia(evaluacion, maestro):
    return Denuncia.objects.create(evaluacion=evaluacion, denunciante_id=maestro.pk, motivo="No es verdad")


def _url_denunciar(ticket):
    return f"{tk.URL}/{ticket.ref}/evaluacion-recibida/denuncia"


def _resolver(sesion, denuncia, decision="retirar", motivo="Lenguaje ofensivo"):
    return post_json(sesion, f"{URL_MOD}/{denuncia.ref}/resolucion", {"decision": decision, "motivo": motivo})


# --- Denuncia de la parte evaluada (RF-31, P-26) ---


@pytest.mark.regla("A-18")
def test_la_parte_evaluada_denuncia_una_sola_vez(sesion_maestro, ticket, evaluacion):
    primera = post_json(sesion_maestro, _url_denunciar(ticket), {"motivo": "No es verdad"})
    segunda = post_json(sesion_maestro, _url_denunciar(ticket), {"motivo": "Otra vez"})

    assert primera.status_code == 201 and primera.json()["denuncia"]["estado"] == "abierta"
    assert segunda.status_code == 409 and sin_texto_prohibido(segunda)
    assert Denuncia.objects.count() == 1
    recibida = sesion_maestro.get(f"{tk.URL}/{ticket.ref}/evaluaciones").json()["recibida"]
    assert recibida["puede_denunciar"] is False and recibida["denuncia"]["estado_texto"] == "En revisión"


@pytest.mark.regla("A-18")
def test_quien_no_recibio_evaluacion_no_puede_denunciar(sesion_cliente, ticket, evaluacion):
    # El cliente es el autor: no tiene evaluación recibida.
    respuesta = post_json(sesion_cliente, _url_denunciar(ticket), {"motivo": "Quiero denunciar"})
    assert respuesta.status_code == 409 and Denuncia.objects.count() == 0


def test_el_motivo_de_la_denuncia_es_obligatorio(sesion_maestro, ticket, evaluacion):
    respuesta = post_json(sesion_maestro, _url_denunciar(ticket), {"motivo": "   "})
    assert respuesta.status_code == 400 and "motivo" in respuesta.json()["errores"]


def test_la_base_exige_resolucion_completa_y_una_denuncia_por_denunciante(denuncia, maestro):
    denuncia.estado = EstadoDenuncia.RESUELTA
    with pytest.raises(IntegrityError), transaction.atomic():
        denuncia.save()
    with pytest.raises(IntegrityError), transaction.atomic():
        Denuncia.objects.create(evaluacion=denuncia.evaluacion, denunciante_id=maestro.pk, motivo="Repetida")


# --- Rol y conflicto de interés (HU-25, CA-25.3; E-4.3) ---


@pytest.mark.regla("A-19")
@pytest.mark.parametrize("ruta", ["", "/{ref}", "/{ref}/conversacion"])
def test_un_no_moderador_recibe_403_registrado(sesion_cliente, cliente, denuncia, ruta):
    respuesta = sesion_cliente.get(URL_MOD + ruta.format(ref=denuncia.ref))

    assert respuesta.status_code == 403 and sin_texto_prohibido(respuesta)
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad) == (cliente.pk, "ruta")


@pytest.mark.regla("A-20")
@pytest.mark.parametrize("ruta", ["/{ref}", "/{ref}/conversacion", "/{ref}/resolucion"])
def test_el_moderador_que_es_parte_recibe_conflicto_de_interes(sesion_cliente, cliente, denuncia, ruta):
    UsuarioRol.objects.create(usuario=cliente, rol=Rol.MODERACION)
    url = URL_MOD + ruta.format(ref=denuncia.ref)

    if ruta.endswith("resolucion"):
        respuesta = post_json(sesion_cliente, url, {"decision": "retirar", "motivo": "Me conviene"})
    else:
        respuesta = sesion_cliente.get(url)

    assert respuesta.status_code == 403 and respuesta.json()["mensaje"] == MENSAJE_CONFLICTO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (cliente.pk, "denuncia", str(denuncia.ref))
    assert not Bitacora.objects.exists()
    assert Denuncia.objects.get().estado == EstadoDenuncia.ABIERTA
    # Tampoco la ve en su lista.
    assert sesion_cliente.get(URL_MOD).json()["denuncias"] == []


@pytest.mark.terceros("moderacion_denuncia")
@pytest.mark.terceros("moderacion_conversacion")
@pytest.mark.terceros("moderacion_resolucion")
@pytest.mark.parametrize("ruta", ["/{ref}", "/{ref}/conversacion", "/{ref}/resolucion"])
@pytest.mark.parametrize("nombre", ["otro_cliente", "otro_maestro", "curatoria"])
def test_un_tercero_sin_rol_recibe_403_registrado_en_moderacion(catalogo, denuncia, ruta, nombre):
    terceros = {
        "otro_cliente": (lambda: tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A),
                         "otro.cliente@example.com"),
        "otro_maestro": (lambda: tk.maestro_con_agenda(catalogo, n=2), ay.rut(2)),
        "curatoria": (lambda: tk.administrativo(Rol.CURATORIA, "cura@example.com"), "cura@example.com"),
    }
    crear, identificador = terceros[nombre]
    tercero = crear()
    sesion = tk.sesion(identificador)
    url = URL_MOD + ruta.format(ref=denuncia.ref)

    respuesta = post_json(sesion, url, {"decision": "retirar", "motivo": "x"}) if "resolucion" in ruta \
        else sesion.get(url)

    assert respuesta.status_code == 403
    assert RegistroAccesoDenegado.objects.get().usuario_id == tercero.pk
    assert Denuncia.objects.get().estado == EstadoDenuncia.ABIERTA


def test_una_denuncia_inexistente_da_404(sesion_mod):
    respuesta = sesion_mod.get(f"{URL_MOD}/{uuid.uuid4()}")
    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO


# --- Lista y detalle (E-4.5) ---


def test_lista_con_filtro_de_estado(sesion_mod, denuncia):
    assert [d["ref"] for d in sesion_mod.get(URL_MOD, {"estado": "abierta"}).json()["denuncias"]] == [str(denuncia.ref)]
    assert sesion_mod.get(URL_MOD, {"estado": "resuelta"}).json()["denuncias"] == []
    assert sesion_mod.get(URL_MOD, {"estado": "otra"}).status_code == 400
    assert sesion_mod.get(URL_MOD, {"pagina": "1"}).status_code == 400


@pytest.mark.regla("A-21")
def test_el_detalle_no_trae_direccion_ni_telefono(sesion_mod, denuncia):
    respuesta = sesion_mod.get(f"{URL_MOD}/{denuncia.ref}")

    assert respuesta.status_code == 200
    datos = respuesta.json()["denuncia"]
    assert datos["evaluacion"]["comentario"] == "Comentario ofensivo de prueba"
    assert datos["puede_ver_conversacion"] is True and datos["denunciante"] == "maestro"
    contenido = respuesta.content.decode("utf-8")
    for prohibido in (tk.DIRECCION, tk.TELEFONO_CLIENTE, "+56 9", tk.NOMBRE_CLIENTE, tk.CORREO_CLIENTE,
                      "Maestro", '"direccion"', '"telefono"', '"cliente_id"', '"descripcion"'):
        assert prohibido not in contenido


# --- Conversación (CA-21.1, M-04) ---


@pytest.mark.regla("A-22")
def test_ca21_1_cada_consulta_de_la_conversacion_queda_en_bitacora_y_avisa_a_ambas_partes(
        sesion_mod, moderador, denuncia, ticket, cliente, maestro):
    respuesta = sesion_mod.get(f"{URL_MOD}/{denuncia.ref}/conversacion")
    sesion_mod.get(f"{URL_MOD}/{denuncia.ref}/conversacion")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert [(m["autor"], m["texto"]) for m in datos["mensajes"]] == [("cliente", "¿Llega a las 8?")]
    assert datos["puede_escribir"] is False
    entradas = Bitacora.objects.filter(accion="conversacion_consultada")
    assert entradas.count() == 2
    entrada = entradas.first()
    assert (entrada.autor_id, entrada.entidad, entrada.entidad_ref, entrada.motivo) == (
        moderador.pk, "ticket", str(ticket.ref), f"Denuncia {denuncia.ref}")
    avisos = AvisoTicket.objects.filter(tipo=TipoAvisoTicket.CONVERSACION_REVISADA, visto_en__isnull=True)
    assert set(avisos.values_list("destinatario_id", flat=True)) == {cliente.pk, maestro.pk}
    del_cliente = tk.sesion(tk.CORREO_CLIENTE).get(tk.URL_AVISOS).json()
    texto = next(a["texto"] for a in del_cliente["avisos"] if a["tipo"] == "conversacion_revisada")
    assert texto.startswith("Moderación revisó la conversación")


@pytest.mark.regla("A-23")
def test_con_la_denuncia_resuelta_la_conversacion_da_404_registrado(sesion_mod, moderador, denuncia):
    assert _resolver(sesion_mod, denuncia, "mantener").status_code == 200

    respuesta = sesion_mod.get(f"{URL_MOD}/{denuncia.ref}/conversacion")

    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (moderador.pk, "denuncia", str(denuncia.ref))
    assert not Bitacora.objects.filter(accion="conversacion_consultada").exists()


def test_moderacion_no_entra_por_la_ruta_de_mensajes_del_ticket(sesion_mod, denuncia, ticket):
    respuesta = sesion_mod.get(f"{tk.URL}/{ticket.ref}/mensajes")
    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO


# --- Resolución (CA-21.2, RF-37) ---


@pytest.mark.regla("A-24")
def test_ca21_2_retirar_registra_decision_autor_y_motivo_y_excluye_del_promedio(sesion_mod, moderador, denuncia,
                                                                                 maestro):
    assert calificacion.de_maestro(maestro.pk).cantidad == 1

    respuesta = _resolver(sesion_mod, denuncia)

    assert respuesta.status_code == 200
    assert respuesta.json()["denuncia"]["estado"] == "resuelta"
    resuelta = Denuncia.objects.get()
    assert (resuelta.decision, resuelta.resuelta_por_id, resuelta.motivo_resolucion) == (
        "retirar", moderador.pk, "Lenguaje ofensivo")
    evaluacion = Evaluacion.objects.get()
    assert evaluacion.estado == EstadoEvaluacion.RETIRADA  # no se borra
    assert calificacion.de_maestro(maestro.pk) is None
    entrada = Bitacora.objects.get(accion="denuncia_resuelta")
    assert (entrada.autor_id, entrada.entidad, entrada.entidad_ref, entrada.motivo) == (
        moderador.pk, "evaluacion", str(evaluacion.ref), "Lenguaje ofensivo")
    assert entrada.valor_anterior["estado"] == "publicada" and entrada.valor_nuevo["estado"] == "retirada"
    assert entrada.valor_nuevo["decision"] == "retirar"


@pytest.mark.regla("A-24")
@pytest.mark.parametrize("cuerpo, campo", [
    ({"decision": "retirar", "motivo": ""}, "motivo"),
    ({"decision": "retirar"}, "motivo"),
    ({"decision": "borrar", "motivo": "x"}, "decision"),
])
def test_la_resolucion_exige_decision_y_motivo(sesion_mod, denuncia, cuerpo, campo):
    respuesta = post_json(sesion_mod, f"{URL_MOD}/{denuncia.ref}/resolucion", cuerpo)
    assert respuesta.status_code == 400 and campo in respuesta.json()["errores"]
    assert Denuncia.objects.get().estado == EstadoDenuncia.ABIERTA and not Bitacora.objects.exists()


def test_mantener_no_cambia_la_evaluacion_y_resolver_dos_veces_da_409(sesion_mod, denuncia):
    assert _resolver(sesion_mod, denuncia, "mantener").status_code == 200
    segunda = _resolver(sesion_mod, denuncia, "retirar")

    assert segunda.status_code == 409 and sin_texto_prohibido(segunda)
    assert Evaluacion.objects.get().estado == EstadoEvaluacion.PUBLICADA
    entrada = Bitacora.objects.get(accion="denuncia_resuelta")
    assert entrada.valor_anterior["estado"] == entrada.valor_nuevo["estado"] == "publicada"
