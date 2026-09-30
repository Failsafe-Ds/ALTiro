"""Evaluaciones y calificación (S5, incremento 5).

HU-09, HU-18, HU-05; RF-29, RF-30, RF-11, RF-13, RF-14; CA-09.1, CA-09.2,
CA-18.1, CA-05.1, CA-05.2, CA-03.3; ADR-026, E-3; propuesta del S5, §3.1 a
§3.4. Datos ficticios (``tests.tickets_ayudas``). Reloj: miércoles 7 de
octubre de 2026, 08:00 en Santiago.
"""
import datetime
import uuid
from decimal import Decimal

import pytest
import time_machine
from django.db import IntegrityError, transaction
from django.test import Client

from autorizacion.models import RegistroAccesoDenegado
from comun.api import respuesta_no_encontrado
from evaluaciones import calificacion
from evaluaciones.models import Denuncia, EstadoEvaluacion, Evaluacion, ParteEvaluacion
from evaluaciones.servicios import MENSAJE_YA_EVALUASTE
from identidad.models import Rol
from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from tests.ayudas import TEL_A, post_json, sin_texto_prohibido
from tickets.models import EstadoTicket

pytestmark = pytest.mark.django_db

D = datetime.timedelta
AHORA = tk.AHORA
NO_ENCONTRADO = respuesta_no_encontrado().content
NOTAS = {"puntualidad": 5, "trabajo": 4, "cordialidad": 5}


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


def _ticket(cliente, maestro, estado=EstadoTicket.FINALIZADO, **extra):
    return tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=estado, **extra)


def _url(ticket, sufijo="evaluacion"):
    return f"{tk.URL}/{ticket.ref}/{sufijo}"


def _evaluar(sesion, ticket, **cambios):
    return post_json(sesion, _url(ticket), {**NOTAS, "comentario": "Muy buen trabajo.", **cambios})


def _pasado(cliente_usuario, del_maestro, dias):
    """Ticket finalizado en el pasado (no ocupa la agenda que mide el puntaje)."""
    fecha = tk.HOY - D(days=dias)
    inicio = datetime.datetime.combine(fecha, datetime.time(8), tzinfo=AHORA.tzinfo)
    return tk.ticket_directo(cliente_usuario, del_maestro, fecha, "08:00", "12:00", estado=EstadoTicket.FINALIZADO,
                             enviado_en=inicio - D(days=2))


def _directa(ticket, notas, parte=ParteEvaluacion.CLIENTE, estado=EstadoEvaluacion.PUBLICADA, comentario="",
             creada_en=None):
    autor, evaluado = (ticket.cliente_id, ticket.perfil_maestro_id)
    if parte == ParteEvaluacion.MAESTRO:
        autor, evaluado = evaluado, autor
    p, t, c = notas
    return Evaluacion.objects.create(ticket=ticket, parte=parte, autor_id=autor, evaluado_id=evaluado, puntualidad=p,
                                     trabajo=t, cordialidad=c, comentario=comentario, estado=estado,
                                     creada_en=creada_en or AHORA)


# --- CA-09.1, CA-18.1: cada parte evalúa una orden finalizada ---


@pytest.mark.regla("C-16")
def test_ca09_1_y_ca18_1_ambas_partes_evaluan_la_orden_finalizada(sesion_cliente, sesion_maestro, cliente, maestro):
    ticket = _ticket(cliente, maestro)

    del_cliente = _evaluar(sesion_cliente, ticket)
    del_maestro = _evaluar(sesion_maestro, ticket, comentario="")

    assert (del_cliente.status_code, del_maestro.status_code) == (201, 201)
    assert set(del_cliente.json()["evaluacion"]) == {"parte", "puntualidad", "trabajo", "cordialidad", "comentario",
                                                     "creada_en", "estado", "estado_texto"}
    filas = {e.parte: e for e in Evaluacion.objects.all()}
    assert (filas["cliente"].autor_id, filas["cliente"].evaluado_id) == (cliente.pk, maestro.pk)
    assert (filas["maestro"].autor_id, filas["maestro"].evaluado_id) == (maestro.pk, cliente.pk)
    vista = sesion_maestro.get(_url(ticket, "evaluaciones")).json()
    assert vista["mia"]["parte"] == "maestro" and vista["recibida"]["comentario"] == "Muy buen trabajo."
    assert vista["puede_evaluar"] is False and vista["recibida"]["puede_denunciar"] is True


@pytest.mark.regla("C-16")
@pytest.mark.parametrize("estado", [EstadoTicket.PENDIENTE, EstadoTicket.ACEPTADO, EstadoTicket.CERRADO])
def test_solo_se_evalua_una_orden_finalizada(sesion_cliente, cliente, maestro, estado):
    ticket = _ticket(cliente, maestro, estado=estado)

    respuesta = _evaluar(sesion_cliente, ticket)

    assert respuesta.status_code == 409 and sin_texto_prohibido(respuesta)
    assert Evaluacion.objects.count() == 0
    assert sesion_cliente.get(_url(ticket, "evaluaciones")).json()["puede_evaluar"] is False


@pytest.mark.regla("C-17")
def test_ca09_2_la_segunda_evaluacion_se_rechaza(sesion_cliente, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    assert _evaluar(sesion_cliente, ticket).status_code == 201

    segunda = _evaluar(sesion_cliente, ticket, puntualidad=1)

    assert segunda.status_code == 409 and segunda.json()["mensaje"] == MENSAJE_YA_EVALUASTE
    assert Evaluacion.objects.get().puntualidad == 5


@pytest.mark.regla("C-17")
def test_la_base_impide_dos_evaluaciones_de_la_misma_parte(cliente, maestro):
    ticket = _ticket(cliente, maestro)
    _directa(ticket, (5, 5, 5))
    with pytest.raises(IntegrityError), transaction.atomic():
        _directa(ticket, (1, 1, 1))


def test_la_base_rechaza_notas_fuera_de_escala_y_autor_igual_al_evaluado(cliente, maestro):
    ticket = _ticket(cliente, maestro)
    with pytest.raises(IntegrityError), transaction.atomic():
        _directa(ticket, (6, 5, 5))
    with pytest.raises(IntegrityError), transaction.atomic():
        Evaluacion.objects.create(ticket=ticket, parte="cliente", autor_id=cliente.pk, evaluado_id=cliente.pk,
                                  puntualidad=5, trabajo=5, cordialidad=5)


@pytest.mark.parametrize("cambios, campo", [
    ({"puntualidad": 0}, "puntualidad"),
    ({"trabajo": 6}, "trabajo"),
    ({"cordialidad": True}, "cordialidad"),
    ({"cordialidad": "5"}, "cordialidad"),
    ({"comentario": "x" * 501}, "comentario"),
])
def test_notas_y_comentario_se_validan_en_el_servidor(sesion_cliente, cliente, maestro, cambios, campo):
    ticket = _ticket(cliente, maestro)
    respuesta = _evaluar(sesion_cliente, ticket, **cambios)
    assert respuesta.status_code == 400 and campo in respuesta.json()["errores"]
    assert Evaluacion.objects.count() == 0


def test_una_clave_desconocida_da_400_general(sesion_cliente, cliente, maestro):
    ticket = _ticket(cliente, maestro)
    respuesta = _evaluar(sesion_cliente, ticket, autor="otro")
    assert respuesta.status_code == 400 and respuesta.json()["errores"] == {}


# --- Acceso (CA-25.1; ADR-026, E-5) ---


def _terceros(catalogo):
    return {
        "otro_cliente": (lambda: tk.cliente(correo="otro.cliente@example.com", telefono=TEL_A),
                         "otro.cliente@example.com"),
        "otro_maestro": (lambda: tk.maestro_con_agenda(catalogo, n=2), ay.rut(2)),
        "moderacion": (lambda: tk.administrativo(Rol.MODERACION, "moderacion@example.com"), "moderacion@example.com"),
        "curatoria": (lambda: tk.administrativo(Rol.CURATORIA, "cura@example.com"), "cura@example.com"),
    }


@pytest.mark.terceros("ticket_evaluacion")
@pytest.mark.terceros("ticket_evaluaciones")
@pytest.mark.terceros("ticket_denuncia")
@pytest.mark.regla("A-16")
@pytest.mark.parametrize("ruta", ["evaluacion", "evaluaciones", "evaluacion-recibida/denuncia"])
@pytest.mark.parametrize("nombre", ["otro_cliente", "otro_maestro", "moderacion", "curatoria"])
def test_ca25_1_un_tercero_recibe_el_404_identico_con_registro(cliente, maestro, catalogo, ruta, nombre):
    ticket = _ticket(cliente, maestro)
    _directa(ticket, (4, 4, 4), parte=ParteEvaluacion.MAESTRO)
    crear, identificador = _terceros(catalogo)[nombre]
    tercero = crear()
    sesion = tk.sesion(identificador)
    url = _url(ticket, ruta)

    if ruta == "evaluaciones":
        respuesta = sesion.get(url)
    elif ruta == "evaluacion":
        respuesta = post_json(sesion, url, NOTAS)
    else:
        respuesta = post_json(sesion, url, {"motivo": "intruso"})

    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "ticket", str(ticket.ref))
    assert Evaluacion.objects.count() == 1 and Denuncia.objects.count() == 0


def test_sin_sesion_401_y_ticket_inexistente_404(client, sesion_cliente):
    assert client.get(f"{tk.URL}/{uuid.uuid4()}/evaluaciones").status_code == 401
    respuesta = sesion_cliente.get(f"{tk.URL}/{uuid.uuid4()}/evaluaciones")
    assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO


# --- RF-30: promedio y dimensiones ---


@pytest.mark.regla("P-12")
def test_rf30_el_promedio_coincide_con_el_calculo(cliente, maestro):
    for n, notas in enumerate([(5, 4, 5), (3, 4, 4), (5, 5, 5)], start=3):
        _directa(_pasado(cliente, maestro, n), notas)
    # La evaluación del maestro al cliente no cuenta para el maestro.
    _directa(_pasado(cliente, maestro, 9), (1, 1, 1), parte=ParteEvaluacion.MAESTRO)

    nota = calificacion.de_maestro(maestro.pk)

    # (14/3 + 11/3 + 15/3) / 3 = 40/9 = 4,444… → 4,4
    assert nota.promedio == Decimal("4.4") and nota.cantidad == 3
    assert (nota.puntualidad, nota.trabajo, nota.cordialidad) == (Decimal("4.3"), Decimal("4.3"), Decimal("4.7"))
    assert calificacion.texto(nota) == "4,4 de 5 (3 evaluaciones)"


def test_el_redondeo_es_mitad_hacia_arriba():
    assert calificacion.redondear(45, 10) == Decimal("4.5")
    assert calificacion.redondear(425, 100) == Decimal("4.3")  # 4,25 → 4,3 (no redondeo bancario)


@pytest.mark.regla("P-13")
def test_una_evaluacion_retirada_queda_excluida_sin_borrarse(cliente, maestro):
    _directa(_pasado(cliente, maestro, 3), (5, 5, 5))
    _directa(_pasado(cliente, maestro, 4), (1, 1, 1), estado=EstadoEvaluacion.RETIRADA)

    nota = calificacion.de_maestro(maestro.pk)

    assert (nota.promedio, nota.cantidad) == (Decimal("5.0"), 1)
    assert Evaluacion.objects.count() == 2


# --- Ficha pública (RF-14, CA-05.1, CA-05.2) ---


def _ficha(del_maestro):
    return Client().get(f"/api/maestros/publicos/{ay.ref(del_maestro)}")


@pytest.mark.regla("P-14")
def test_ca05_2_sin_evaluaciones_la_ficha_lo_dice(maestro):
    datos = _ficha(maestro).json()["maestro"]
    assert datos["calificacion"] is None and datos["comentarios"] == []
    assert datos["calificacion_texto"] == "Todavía no tiene evaluaciones"


@pytest.mark.regla("A-17")
def test_ca05_1_la_ficha_muestra_dimensiones_y_los_ultimos_10_comentarios_sin_autor(cliente, maestro):
    for n in range(12):
        _directa(_pasado(cliente, maestro, n + 3), (4, 5, 3), comentario=f"Comentario {n}",
                 creada_en=AHORA - D(days=40 - n))
    _directa(_pasado(cliente, maestro, 20), (5, 5, 5), comentario="Retirado", estado=EstadoEvaluacion.RETIRADA)

    respuesta = _ficha(maestro)

    datos = respuesta.json()["maestro"]
    assert datos["calificacion"] == {"promedio": 4.0, "cantidad": 12, "puntualidad": 4.0, "trabajo": 5.0,
                                     "cordialidad": 3.0}
    assert datos["calificacion_texto"] == "4,0 de 5 (12 evaluaciones)"
    assert [c["texto"] for c in datos["comentarios"]] == [f"Comentario {n}" for n in range(11, 1, -1)]
    assert all(set(c) == {"texto", "fecha_texto"} for c in datos["comentarios"])
    assert datos["comentarios"][0]["fecha_texto"] == "septiembre de 2026"
    contenido = respuesta.content.decode("utf-8")
    for prohibido in (tk.NOMBRE_CLIENTE, tk.CORREO_CLIENTE, "Retirado", '"autor', '"evaluado'):
        assert prohibido not in contenido


# --- RF-11, RF-13, CA-03.3: tarjeta y desempate con la calificación real ---


def _buscar():
    return Client().get("/api/busqueda", {"oficio": "pintura", "comuna": str(ay.CONCEPCION)})


@pytest.mark.regla("P-09")
def test_ca03_3_desempate_por_promedio_redondeado_y_luego_cantidad(catalogo, cliente):
    uno, dos, tres, cuatro = (ay.maestro(n, catalogo) for n in range(1, 5))
    # uno: 29/6 = 4,83 → 4,8 con 2. dos: 43/9 = 4,78 → 4,8 con 3 (gana por cantidad aunque su valor exacto es menor).
    for dias, notas in ((3, (5, 5, 5)), (4, (5, 5, 4))):
        _directa(_pasado(cliente, uno, dias), notas)
    for dias, notas in ((3, (5, 5, 5)), (4, (5, 5, 4)), (5, (5, 5, 4))):
        _directa(_pasado(cliente, dos, dias), notas)
    # tres: 5,0 con 1. cuatro: sin evaluaciones publicadas (la retirada no cuenta) → al final.
    _directa(_pasado(cliente, tres, 3), (5, 5, 5))
    _directa(_pasado(cliente, cuatro, 3), (5, 5, 5), estado=EstadoEvaluacion.RETIRADA)

    respuesta = _buscar()

    assert ay.refs(respuesta) == [ay.ref(tres), ay.ref(dos), ay.ref(uno), ay.ref(cuatro)]
    tarjetas = {t["ref"]: t for t in respuesta.json()["resultados"]}
    assert tarjetas[ay.ref(dos)]["calificacion"] == {"promedio": 4.8, "cantidad": 3}
    assert tarjetas[ay.ref(dos)]["calificacion_texto"] == "4,8 de 5 (3 evaluaciones)"
    assert tarjetas[ay.ref(tres)]["calificacion_texto"] == "5,0 de 5 (1 evaluación)"
    assert tarjetas[ay.ref(cuatro)]["calificacion"] is None


def test_la_calificacion_de_la_busqueda_se_calcula_en_una_consulta(catalogo, cliente):
    maestros = [ay.maestro(n, catalogo) for n in range(1, 4)]
    for m in maestros:
        _directa(_pasado(cliente, m, 3), (4, 4, 4))
    with _consultas_evaluacion() as contador:
        _buscar()
    assert contador["evaluacion"] == 1


class _consultas_evaluacion:
    """Cuenta las consultas a la tabla ``evaluacion`` (sin N+1)."""

    def __enter__(self):
        from django.db import connection

        self.contador = {"evaluacion": 0}
        self._envoltura = connection.execute_wrapper(self._contar)
        self._envoltura.__enter__()
        return self.contador

    def _contar(self, ejecutar, sql, params, many, context):
        if 'FROM "evaluacion"' in sql:
            self.contador["evaluacion"] += 1
        return ejecutar(sql, params, many, context)

    def __exit__(self, *args):
        self._envoltura.__exit__(*args)
