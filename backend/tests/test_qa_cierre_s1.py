"""Pruebas agregadas por QA en el cierre del Sprint 1 (docs/testing/cierre-sprint-1.md).

Cubren casos de prioridad Alta del plan (docs/testing/plan-identidad-sprint-1.md)
que no tenían prueba automatizada: PI-282, PI-283 (sección P), PI-291 y PI-292
(sección Q). Requisitos: RF-01, RF-03, CA-11.3, HU-25; ADR-013, punto 2 y
Enmiendas E-1 y E-2; RNF-09 (ADR-005).

Datos ficticios: correos @example.com, RUT sintéticos del plan y teléfonos
+56 9 1000 000N.
"""
import datetime
import threading

import pytest
import time_machine
from django.db import connection
from django.test import Client
from django.utils import timezone

from identidad.errores import ErrorValidacion
from identidad.models import PerfilCliente, PerfilMaestro, Rol, Usuario, UsuarioRol
from identidad.servicios import agregar_perfil_cliente, agregar_perfil_maestro, verificar_invariantes
from tests.ayudas import (
    COMUNA,
    TEL_A,
    TEL_B,
    URL_CLIENTES,
    URL_CUENTA,
    URL_POSTULACIONES,
    crear_cliente,
    crear_maestro,
    datos_maestro,
    iniciar_sesion,
    post_json,
    sin_texto_prohibido,
)


@pytest.fixture(autouse=True)
def invariantes_al_final(request):
    """PI-130: al terminar, todas las cuentas cumplen las invariantes de ADR-013."""
    yield
    if request.node.get_closest_marker("django_db") is None:
        return
    for usuario in Usuario.objects.all():
        assert verificar_invariantes(usuario) == [], f"usuario {usuario.pk}"


def _roles(usuario):
    return set(UsuarioRol.objects.filter(usuario=usuario).values_list("rol", flat=True))


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


# --- P. Concurrencia ---


@pytest.mark.django_db(transaction=True)
def test_pi282_cuenta_con_sesion_y_visitante_postulan_a_la_vez_con_el_mismo_rut():
    cliente = crear_cliente(correo="ana.prueba@example.com", telefono=TEL_A)

    resultados = _en_paralelo(
        lambda: agregar_perfil_maestro(cliente, rut="11.111.111-1"),
        lambda: crear_maestro(rut="111111111", telefono=TEL_B),
    )

    exitos = [r for r in resultados if isinstance(r, Usuario)]
    errores = [r for r in resultados if isinstance(r, ErrorValidacion)]
    assert len(exitos) == 1 and len(errores) == 1, resultados
    assert errores[0].campo == "rut"
    assert PerfilMaestro.objects.count() == 1
    # Sin filas huérfanas: el perdedor no deja usuario, perfil ni rol.
    if exitos[0].pk == cliente.pk:
        assert Usuario.objects.count() == 1
        assert _roles(cliente) == {Rol.CLIENTE, Rol.MAESTRO}
    else:
        assert Usuario.objects.count() == 2
        assert _roles(cliente) == {Rol.CLIENTE}
    assert UsuarioRol.objects.filter(rol=Rol.MAESTRO).count() == 1


@pytest.mark.django_db(transaction=True)
def test_pi283_dos_maestros_sin_correo_agregan_perfil_cliente_con_el_mismo_correo():
    uno = crear_maestro(rut="11.111.111-1", telefono=TEL_A)
    dos = crear_maestro(rut="22.222.222-2", telefono=TEL_B)

    resultados = _en_paralelo(
        lambda: agregar_perfil_cliente(uno, comuna=COMUNA, correo="compartido@example.com"),
        lambda: agregar_perfil_cliente(dos, comuna=COMUNA, correo="Compartido@Example.com"),
    )

    exitos = [r for r in resultados if isinstance(r, Usuario)]
    errores = [r for r in resultados if isinstance(r, ErrorValidacion)]
    assert len(exitos) == 1 and len(errores) == 1, resultados
    assert errores[0].campo == "correo"
    perdedor = dos if exitos[0].pk == uno.pk else uno
    perdedor.refresh_from_db()
    assert perdedor.correo is None
    assert not PerfilCliente.objects.filter(usuario=perdedor).exists()
    assert _roles(perdedor) == {Rol.MAESTRO}
    assert Usuario.objects.filter(correo="compartido@example.com").count() == 1


# --- Q. Autorización básica ---


@pytest.mark.django_db
def test_pi291_sesion_expirada_se_trata_como_visitante_y_no_crea_nada():
    maestro = crear_maestro(correo="mae1@example.com")
    navegador = Client()
    inicio = timezone.now()
    with time_machine.travel(inicio, tick=False):
        assert iniciar_sesion(navegador, "mae1@example.com").status_code == 200

    with time_machine.travel(inicio + datetime.timedelta(minutes=31), tick=False):
        respuesta = post_json(navegador, URL_CLIENTES, {"comuna": COMUNA})
        assert navegador.get(URL_CUENTA).status_code == 401

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) >= {"nombre", "telefono", "correo", "contrasena"}
    assert sin_texto_prohibido(respuesta)
    assert Usuario.objects.count() == 1
    assert _roles(maestro) == {Rol.MAESTRO}
    assert not PerfilCliente.objects.exists()


@pytest.mark.django_db
def test_pi291_cookie_de_sesion_invalida_se_trata_como_visitante(client):
    maestro = crear_maestro(correo="mae1@example.com")
    client.cookies["sessionid"] = "cookie-inventada-que-no-existe-en-el-servidor"

    respuesta = post_json(client, URL_CLIENTES, {"comuna": COMUNA})

    assert respuesta.status_code == 400
    assert set(respuesta.json()["errores"]) >= {"nombre", "telefono", "correo", "contrasena"}
    assert Usuario.objects.count() == 1
    assert _roles(maestro) == {Rol.MAESTRO}


@pytest.mark.django_db
def test_pi292_con_sesion_no_se_opera_sobre_otra_cuenta_por_id_correo_o_rut(client):
    # A es cliente (puede postular); C es maestro con correo (puede agregar perfil_cliente).
    a = crear_cliente(correo="ana.prueba@example.com", telefono=TEL_A)
    b = crear_maestro(rut="22.222.222-2", correo="mae1@example.com", telefono=TEL_B)
    c = crear_maestro(rut="10.000.004-0", correo="mae2@example.com", telefono=TEL_A)
    assert iniciar_sesion(client, "ana.prueba@example.com").status_code == 200
    con_id = post_json(client, URL_POSTULACIONES, {"rut": "33.333.333-3", "id": b.pk})
    con_rut = post_json(client, URL_POSTULACIONES, {"rut": "22.222.222-2"})
    otro = Client()
    assert iniciar_sesion(otro, "mae2@example.com").status_code == 200
    con_correo = post_json(otro, URL_CLIENTES, {"comuna": COMUNA, "correo": "mae1@example.com"})

    assert con_id.status_code == 400
    assert con_id.json()["errores"] == {}
    assert con_correo.status_code == 400
    assert set(con_correo.json()["errores"]) == {"correo"}
    assert con_rut.status_code == 400
    assert con_rut.json()["errores"]["rut"].startswith("Ese RUT ya tiene una postulación")
    for respuesta in (con_id, con_correo, con_rut):
        assert sin_texto_prohibido(respuesta)
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.correo, _roles(a)) == ("ana.prueba@example.com", {Rol.CLIENTE})
    c.refresh_from_db()
    assert (b.correo, _roles(b)) == ("mae1@example.com", {Rol.MAESTRO})
    assert (c.correo, _roles(c)) == ("mae2@example.com", {Rol.MAESTRO})
    assert PerfilMaestro.objects.get(rut="222222222").usuario_id == b.pk
    assert not PerfilMaestro.objects.filter(usuario=a).exists()
    assert not PerfilCliente.objects.filter(usuario__in=[b, c]).exists()


@pytest.mark.django_db
def test_pi292_la_respuesta_de_postulacion_no_expone_datos_de_otra_cuenta(client):
    crear_maestro(rut="22.222.222-2", correo="mae1@example.com", telefono=TEL_B)

    respuesta = post_json(client, URL_POSTULACIONES, datos_maestro(rut="22.222.222-2", telefono=TEL_A))

    assert respuesta.status_code == 400
    texto = respuesta.content.decode("utf-8")
    assert "mae1@example.com" not in texto and "Maestro Uno" not in texto and "910000002" not in texto
