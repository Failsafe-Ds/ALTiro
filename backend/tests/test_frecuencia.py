"""Limitación de frecuencia contra el exceso de solicitudes (ADR-007, E-1; ADR-027, E-1).

- B1: registro sin sesión (cliente y postulación) por origen.
- B2: la solicitud de recuperación no espera la escritura del correo.
- B3: solicitudes de recuperación simultáneas respetan los límites y dejan un solo enlace vigente.
- B9: frecuencia de mensajes por parte y ticket; inundación de ``acceso_denegado``.

Datos ficticios. Las pruebas de concurrencia usan hilos con barrera (ADR-014).
"""
import datetime
import threading
import uuid

import pytest
import time_machine
from django.db import connection
from django.test import Client
from django.utils import timezone

from autorizacion.models import RegistroAccesoDenegado
from comun.api import respuesta_no_encontrado
from identidad import frecuencia, recuperacion
from identidad.models import EventoFrecuencia, SolicitudRecuperacion, Usuario
from mensajeria import conversacion
from mensajeria.models import Mensaje
from tests import busqueda_ayudas as ay
from tests import tickets_ayudas as tk
from tests.ayudas import (
    CONTRASENA,
    crear_cliente,
    datos_cliente,
    datos_maestro,
    iniciar_sesion,
    post_json,
    sin_texto_prohibido,
)
from tests.recurso_prueba.models import RecursoPrueba
from tickets.models import EstadoTicket

pytestmark = pytest.mark.django_db

D = datetime.timedelta
URL_CLIENTES = "/api/clientes"
URL_POSTULACIONES = "/api/maestros/postulaciones"
URL_RECUPERACION = "/api/recuperacion"
LIMITE_REGISTRO = frecuencia.REGLAS_REGISTRO[0][0]
LIMITE_DENEGADO = frecuencia.REGLAS_DENEGADO[0][0]
NO_ENCONTRADO = respuesta_no_encontrado().content


def _en_paralelo(*funciones):
    """Ejecuta las funciones a la vez (hilos con barrera; ADR-014)."""
    barrera = threading.Barrier(len(funciones))
    resultados = [None] * len(funciones)

    def ejecutar(indice, funcion):
        try:
            barrera.wait(timeout=10)
            resultados[indice] = funcion()
        except Exception as error:  # noqa: BLE001 - se inspecciona en la prueba
            resultados[indice] = error
        finally:
            connection.close()

    hilos = [threading.Thread(target=ejecutar, args=(i, f)) for i, f in enumerate(funciones)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
    return resultados


def _telefono(i):
    return f"+56 9 2000 {i:04d}"


def _registrar_cliente(client, i, **extra):
    datos = datos_cliente(correo=f"persona{i}@example.com", telefono=_telefono(i))
    return post_json(client, URL_CLIENTES, datos, **extra)


def _es_429_accionable(respuesta):
    assert respuesta.status_code == 429
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "errores"} and cuerpo["errores"] == {}
    assert "espera" in cuerpo["mensaje"].lower()
    assert int(respuesta["Retry-After"]) > 0
    sin_texto_prohibido(respuesta)
    return cuerpo["mensaje"]


# --- Regla común ---


def test_espera_segun_libera_cuando_el_evento_mas_antiguo_del_cupo_sale_de_la_ventana():
    ahora = timezone.now()
    reglas = ((3, D(minutes=10)),)
    fechas = [ahora - D(minutes=9), ahora - D(minutes=5), ahora - D(minutes=1)]
    assert frecuencia.espera_segun(fechas, reglas, ahora) == D(minutes=1)
    assert frecuencia.espera_segun(fechas[1:], reglas, ahora) is None
    # Un evento fuera de la ventana no cuenta.
    assert frecuencia.espera_segun([ahora - D(minutes=11), *fechas[1:]], reglas, ahora) is None


def test_consumir_no_registra_el_rechazo_y_borra_eventos_de_mas_de_24_horas():
    reglas = ((2, D(minutes=10)),)
    EventoFrecuencia.objects.create(ambito="prueba", clave="x", fecha=timezone.now() - D(hours=25))
    assert frecuencia.consumir("prueba", "a", reglas) is None
    assert frecuencia.consumir("prueba", "a", reglas) is None
    assert frecuencia.consumir("prueba", "a", reglas) is not None
    assert EventoFrecuencia.objects.filter(ambito="prueba", clave="a").count() == 2
    assert not EventoFrecuencia.objects.filter(clave="x").exists()
    # Otra clave tiene su propio cupo.
    assert frecuencia.consumir("prueba", "b", reglas) is None


@pytest.mark.django_db(transaction=True)
def test_consumir_en_paralelo_no_supera_el_limite():
    reglas = ((3, D(hours=1)),)
    resultados = _en_paralelo(*[lambda: frecuencia.consumir("prueba", "paralelo", reglas)] * 8)
    assert sum(1 for r in resultados if r is None) == 3, resultados
    assert all(r is None or isinstance(r, datetime.timedelta) for r in resultados), resultados
    assert EventoFrecuencia.objects.filter(ambito="prueba", clave="paralelo").count() == 3


# --- B1: registro sin sesión por origen ---


def test_b1_el_registro_de_clientes_se_limita_por_origen_con_429_accionable(client):
    for i in range(LIMITE_REGISTRO):
        assert _registrar_cliente(client, i).status_code == 201
    respuesta = _registrar_cliente(client, LIMITE_REGISTRO)
    mensaje = _es_429_accionable(respuesta)
    assert "60 minutos" in mensaje and respuesta["Retry-After"] == "3600"
    assert not Usuario.objects.filter(correo=f"persona{LIMITE_REGISTRO}@example.com").exists()
    # Otro origen no queda afectado.
    assert _registrar_cliente(client, 900, REMOTE_ADDR="203.0.113.9").status_code == 201


def test_b1_postulacion_y_registro_de_cliente_comparten_el_cupo_del_origen(client):
    for i in range(LIMITE_REGISTRO):
        assert _registrar_cliente(client, i).status_code == 201
    datos = datos_maestro(rut="11.111.111-1", telefono=_telefono(500))
    _es_429_accionable(post_json(client, URL_POSTULACIONES, datos))


def test_b1_ya_registrado_sigue_respondiendo_igual_y_cuenta_para_el_cupo(client):
    """CA-11.3: el RUT repetido se rechaza indicando que ya tiene postulación; el intento cuenta."""
    assert post_json(client, URL_POSTULACIONES, datos_maestro()).status_code == 201
    repetido = post_json(client, URL_POSTULACIONES, datos_maestro(telefono=_telefono(1)))
    assert repetido.status_code == 400 and "rut" in repetido.json()["errores"]
    assert EventoFrecuencia.objects.filter(ambito="registro").count() == 2


def test_b1_un_400_de_formato_no_gasta_el_cupo(client):
    for _ in range(LIMITE_REGISTRO + 3):
        assert post_json(client, URL_CLIENTES, datos_cliente(correo="no-es-correo")).status_code == 400
    assert not EventoFrecuencia.objects.filter(ambito="registro").exists()
    assert _registrar_cliente(client, 1).status_code == 201


def test_b1_el_cupo_se_libera_una_hora_despues(client):
    inicio = timezone.now()
    with time_machine.travel(inicio, tick=False):
        for i in range(LIMITE_REGISTRO):
            assert _registrar_cliente(client, i).status_code == 201
        assert _registrar_cliente(client, 100).status_code == 429
    with time_machine.travel(inicio + D(minutes=59), tick=False):
        assert _registrar_cliente(client, 101).status_code == 429
    with time_machine.travel(inicio + D(hours=1, seconds=1), tick=False):
        assert _registrar_cliente(client, 102).status_code == 201


def test_b1_con_sesion_agregar_perfil_no_usa_el_cupo(client):
    crear_cliente()
    for i in range(LIMITE_REGISTRO):
        EventoFrecuencia.objects.create(ambito="registro", clave="127.0.0.1", fecha=timezone.now())
    assert iniciar_sesion(client, "ana.prueba@example.com").status_code == 200
    assert post_json(client, URL_POSTULACIONES, {"rut": "11.111.111-1"}).status_code == 201


# --- B2: la respuesta no espera la escritura del correo ---


def test_b2_el_correo_del_enlace_se_escribe_en_un_hilo_aparte(client, settings, monkeypatch):
    settings.ALTIRO_CORREO_EN_SEGUNDO_PLANO = True
    crear_cliente()
    liberar = threading.Event()
    escritos = []
    hilos = []

    def escribir_lento(destino, asunto, cuerpo):
        hilos.append(threading.current_thread())
        liberar.wait(timeout=10)
        escritos.append(destino)

    monkeypatch.setattr(recuperacion, "enviar_correo", escribir_lento)
    respuesta = post_json(client, URL_RECUPERACION, {"identificador": "ana.prueba@example.com"})
    # La respuesta llegó mientras el correo seguía sin escribirse.
    assert respuesta.status_code == 202 and escritos == []
    liberar.set()
    hilos[0].join(timeout=10)
    assert escritos == ["ana.prueba@example.com"]
    assert hilos[0] is not threading.main_thread()


def test_b2_cuenta_inexistente_y_existente_responden_igual_sin_esperar_el_correo(client, settings, monkeypatch):
    settings.ALTIRO_CORREO_EN_SEGUNDO_PLANO = True
    crear_cliente()
    monkeypatch.setattr(recuperacion, "enviar_correo", lambda *a: threading.Event().wait(timeout=0.2))
    existente = post_json(client, URL_RECUPERACION, {"identificador": "ana.prueba@example.com"})
    inexistente = post_json(client, URL_RECUPERACION, {"identificador": "nadie@example.com"})
    assert existente.status_code == inexistente.status_code == 202
    assert existente.content == inexistente.content


# --- B3: solicitudes de recuperación simultáneas ---


@pytest.mark.django_db(transaction=True)
def test_b3_solicitudes_simultaneas_de_una_cuenta_dejan_un_solo_enlace_vigente_y_respetan_el_tope():
    usuario = crear_cliente()
    origenes = [f"198.51.100.{i}" for i in range(1, 7)]
    resultados = _en_paralelo(*[lambda o=o: recuperacion.solicitar(usuario, o) for o in origenes])
    assert all(r is None for r in resultados), resultados
    con_enlace = SolicitudRecuperacion.objects.filter(usuario=usuario, token_hash__isnull=False)
    assert con_enlace.count() == recuperacion.LIMITE_POR_CUENTA
    assert con_enlace.filter(anulada_en__isnull=True, usada_en__isnull=True).count() == 1


@pytest.mark.django_db(transaction=True)
def test_b3_solicitudes_simultaneas_de_un_origen_no_superan_su_limite():
    resultados = _en_paralelo(*[lambda: recuperacion.solicitar(None, "198.51.100.50")] * 8)
    rechazadas = [r for r in resultados if isinstance(r, recuperacion.DemasiadasSolicitudes)]
    assert len(rechazadas) == 8 - recuperacion.LIMITE_POR_ORIGEN, resultados
    assert SolicitudRecuperacion.objects.filter(origen="198.51.100.50").count() == recuperacion.LIMITE_POR_ORIGEN


# --- B9: frecuencia de mensajes ---


@pytest.fixture
def conversacion_abierta():
    with time_machine.travel(tk.AHORA, tick=False) as reloj:
        catalogo = ay.catalogo_basico()
        maestro = tk.maestro_con_agenda(catalogo)
        cliente = tk.cliente()
        ticket = tk.ticket_directo(cliente, maestro, tk.JUEVES, "08:00", "12:00", estado=EstadoTicket.ACEPTADO)
        yield reloj, ticket, tk.sesion(tk.CORREO_CLIENTE), tk.sesion(ay.rut(1))


def _url_mensajes(ticket):
    return f"{tk.URL}/{ticket.ref}/mensajes"


def _enviar(sesion, ticket, clave=None):
    datos = {"texto": "Hola, ¿a qué hora llega?", "clave_envio": str(clave or uuid.uuid4())}
    return post_json(sesion, _url_mensajes(ticket), datos)


def test_b9_rafaga_de_mensajes_da_429_y_no_afecta_leer_ni_a_la_otra_parte(conversacion_abierta):
    reloj, ticket, sesion_cliente, sesion_maestro = conversacion_abierta
    rafaga = conversacion.REGLAS_ENVIO[0][0]
    claves = [uuid.uuid4() for _ in range(rafaga)]
    for clave in claves:
        assert _enviar(sesion_cliente, ticket, clave).status_code == 201
    respuesta = _enviar(sesion_cliente, ticket)
    mensaje = _es_429_accionable(respuesta)
    assert "10 segundos" in mensaje and respuesta["Retry-After"] == "10"
    assert Mensaje.objects.filter(ticket_id=ticket.pk).count() == rafaga
    # Un reenvío con una clave ya usada no cuenta y devuelve el mismo mensaje.
    assert _enviar(sesion_cliente, ticket, claves[0]).status_code == 200
    # Leer y la otra parte no se ven afectados.
    assert sesion_cliente.get(_url_mensajes(ticket)).status_code == 200
    assert _enviar(sesion_maestro, ticket).status_code == 201
    reloj.shift(D(seconds=11))
    assert _enviar(sesion_cliente, ticket).status_code == 201


def test_b9_tope_de_mensajes_por_hora(conversacion_abierta):
    reloj, ticket, sesion_cliente, _ = conversacion_abierta
    for _ in range(12):
        for _ in range(5):
            assert _enviar(sesion_cliente, ticket).status_code == 201
        reloj.shift(D(seconds=11))
    respuesta = _enviar(sesion_cliente, ticket)
    mensaje = _es_429_accionable(respuesta)
    assert "minutos" in mensaje and int(respuesta["Retry-After"]) > 60
    reloj.shift(D(hours=1))
    # La sesión venció por inactividad (ADR-005): se vuelve a ingresar.
    assert _enviar(tk.sesion(tk.CORREO_CLIENTE), ticket).status_code == 201


# --- B9: inundación de acceso_denegado ---


@pytest.fixture
def intruso():
    crear_cliente()
    dueno = crear_cliente(correo="dueno@example.com", telefono="+56 9 1000 0002")
    sesion = Client()
    assert iniciar_sesion(sesion, "ana.prueba@example.com", CONTRASENA).status_code == 200
    return sesion, RecursoPrueba.objects.create(dueno=dueno)


def _pedir(sesion, ref):
    return sesion.get(f"/api/prueba/recursos/{ref}")


def test_b9_tras_el_limite_de_denegaciones_responde_429_igual_para_ajeno_e_inexistente(intruso):
    sesion, ajeno = intruso
    for i in range(LIMITE_DENEGADO):
        ref = ajeno.ref if i % 2 else uuid.uuid4()
        respuesta = _pedir(sesion, ref)
        # Los primeros intentos mantienen el 404 idéntico de ADR-011.
        assert respuesta.status_code == 404 and respuesta.content == NO_ENCONTRADO
    filas = RegistroAccesoDenegado.objects.count()
    assert filas == LIMITE_DENEGADO // 2
    ajena = _pedir(sesion, ajeno.ref)
    inexistente = _pedir(sesion, uuid.uuid4())
    _es_429_accionable(ajena)
    assert ajena.content == inexistente.content and ajena["Retry-After"] == inexistente["Retry-After"]
    # Bloqueado no crece acceso_denegado ni el contador.
    assert RegistroAccesoDenegado.objects.count() == filas
    assert EventoFrecuencia.objects.filter(ambito="denegado").count() == LIMITE_DENEGADO


def test_b9_el_bloqueo_de_denegaciones_es_por_usuario_y_temporal(intruso):
    sesion, ajeno = intruso
    inicio = timezone.now()
    with time_machine.travel(inicio, tick=False):
        for _ in range(LIMITE_DENEGADO):
            assert _pedir(sesion, uuid.uuid4()).status_code == 404
        assert _pedir(sesion, ajeno.ref).status_code == 429
        # El dueño no queda afectado.
        dueno = Client()
        assert iniciar_sesion(dueno, "dueno@example.com").status_code == 200
        assert _pedir(dueno, ajeno.ref).status_code == 200
    with time_machine.travel(inicio + D(minutes=10, seconds=1), tick=False):
        assert _pedir(sesion, ajeno.ref).status_code == 404


def test_b9_visitante_sin_sesion_no_usa_el_contador(client):
    for _ in range(LIMITE_DENEGADO + 2):
        assert _pedir(client, uuid.uuid4()).status_code == 401
    assert not EventoFrecuencia.objects.filter(ambito="denegado").exists()
