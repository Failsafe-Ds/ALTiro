"""Cobertura y agenda del maestro, incrementos 3 y 4 del S3; oficios dados de baja (§8.4).

RF-06, RF-07, HU-13, HU-14, CA-13.1, CA-14.1, CA-14.2, CA-14.4, NTI-02, RNF-07;
ADR-019 (puntos 3 y 4), ADR-020; propuesta del S3, §8.4.

Datos ficticios (@example.com, RUT sintéticos). Comunas del catálogo CUT 2018.
"""
import json
import threading
import uuid

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import Client

from autorizacion.middleware import MENSAJE_SIN_ROL
from autorizacion.models import RegistroAccesoDenegado
from catalogo.models import Oficio
from comun.api import respuesta_no_encontrado
from expediente import servicios as expedientes
from expediente.errores import ErroresValidacion
from expediente.models import EstadoExpediente, Expediente, OficioMaestro
from identidad import servicios as servicios_identidad
from identidad.errores import ErrorValidacion
from identidad.models import Rol
from perfil import agenda, cobertura, publicacion
from perfil.models import Cobertura, Disponibilidad
from tests.ayudas import CONTRASENA, TEL_B, crear_cliente, crear_maestro, iniciar_sesion, post_json, sin_texto_prohibido
from tests.privacidad import assert_campos_ausentes

pytestmark = pytest.mark.django_db

RUT = "11.111.111-1"
RUT_OTRO = "22.222.222-2"
URL_COBERTURA = "/api/maestros/cobertura"
URL_AGENDA = "/api/maestros/disponibilidad"
URL_OFICIOS = "/api/maestros/expediente/oficios"
NO_ENCONTRADO = respuesta_no_encontrado().content
CONCEPCION, CHIGUAYANTE, TALCAHUANO = "8101", "8103", "8110"


def _sesion(identificador=RUT):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


def _put(client, url, datos):
    return client.put(url, data=json.dumps(datos), content_type="application/json")


def _con_estado(usuario, estado):
    Expediente.objects.filter(perfil_maestro_id=usuario.pk).update(estado=estado)


def _comunas(*pares):
    return {"comunas": [{"comuna": codigo, "es_base": base} for codigo, base in pares]}


def _bloque(dia=1, inicio="08:00", fin="12:00"):
    return {"dia_semana": dia, "inicio": inicio, "fin": fin}


@pytest.fixture
def maestro():
    return crear_maestro(rut=RUT)


@pytest.fixture
def sesion(maestro):
    return _sesion()


# --- §8.4: un oficio dado de baja no se declara de nuevo; lo ya declarado se conserva ---


def _dar_de_baja(codigo):
    Oficio.objects.filter(codigo=codigo).update(activo=False)


def test_oficio_dado_de_baja_se_rechaza_en_una_declaracion_nueva(sesion, maestro):
    _dar_de_baja("jardineria")

    respuesta = post_json(sesion, URL_OFICIOS, {"oficios": ["pintura", "jardineria"]})

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"oficios": expedientes.MENSAJE_OFICIO_DADO_DE_BAJA}
    assert not OficioMaestro.objects.filter(maestro_id=maestro.pk).exists()


def test_oficio_dado_de_baja_ya_declarado_se_conserva(sesion, maestro):
    expediente = Expediente.objects.get(perfil_maestro_id=maestro.pk)
    expedientes.declarar_oficios(expediente, ["pintura", "jardineria"])
    _dar_de_baja("jardineria")

    respuesta = post_json(sesion, URL_OFICIOS, {"oficios": ["pintura", "jardineria", "carpinteria"]})

    assert respuesta.status_code == 200
    declarados = set(OficioMaestro.objects.filter(maestro_id=maestro.pk).values_list("oficio__codigo", flat=True))
    assert declarados == {"pintura", "jardineria", "carpinteria"}
    # Quitarlo sí se puede; después ya no se puede volver a agregar.
    assert post_json(sesion, URL_OFICIOS, {"oficios": ["pintura"]}).status_code == 200
    assert post_json(sesion, URL_OFICIOS, {"oficios": ["pintura", "jardineria"]}).status_code == 400


def test_la_regla_del_oficio_dado_de_baja_esta_en_el_servicio(maestro):
    _dar_de_baja("gas")
    with pytest.raises(ErrorValidacion):
        expedientes.declarar_oficios(Expediente.objects.get(perfil_maestro_id=maestro.pk), ["gas"])


# --- Cobertura (RF-06, CA-13.1) ---


def test_el_maestro_guarda_sus_comunas_con_una_comuna_base(sesion, maestro):
    respuesta = _put(sesion, URL_COBERTURA, _comunas((CONCEPCION, True), (TALCAHUANO, False), (8103, False)))

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    comunas = respuesta.json()["comunas"]
    assert {c["codigo"] for c in comunas} == {CONCEPCION, TALCAHUANO, CHIGUAYANTE}
    assert [c["codigo"] for c in comunas if c["es_base"]] == [CONCEPCION]
    assert set(comunas[0]) == {"codigo", "nombre", "es_base"}
    assert publicacion.tiene_comuna_base(maestro.pk)
    assert sesion.get(URL_COBERTURA).json() == respuesta.json()


@pytest.mark.parametrize(
    ("pares", "mensaje"),
    [
        (((CONCEPCION, False), (TALCAHUANO, False)), cobertura.MENSAJE_SIN_COMUNA_BASE),
        (((CONCEPCION, True), (TALCAHUANO, True)), cobertura.MENSAJE_DOS_COMUNAS_BASE),
        (((CONCEPCION, False),), cobertura.MENSAJE_SIN_COMUNA_BASE),
    ],
    ids=["cero_bases", "dos_bases", "una_comuna_sin_base"],
)
def test_ca13_1_sin_exactamente_una_comuna_base_no_se_guarda(sesion, maestro, pares, mensaje):
    respuesta = _put(sesion, URL_COBERTURA, _comunas(*pares))

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"comunas": mensaje}
    assert not Cobertura.objects.exists()


@pytest.mark.parametrize(
    ("cuerpo", "mensaje"),
    [
        ({"comunas": []}, cobertura.MENSAJE_COMUNAS_FALTA),
        ({}, cobertura.MENSAJE_COMUNAS_FALTA),
        ({"comunas": "8101"}, cobertura.MENSAJE_COMUNAS_FALTA),
        (_comunas(("999999", True)), cobertura.MENSAJE_COMUNA_NO_EXISTE),
        (_comunas((CONCEPCION, True), ("1", False)), cobertura.MENSAJE_COMUNA_NO_EXISTE),
        (_comunas(("abc", True)), cobertura.MENSAJE_COMUNA_NO_EXISTE),
        (_comunas(("８１０１", True)), cobertura.MENSAJE_COMUNA_NO_EXISTE),
        (_comunas((True, True)), cobertura.MENSAJE_COMUNA_NO_EXISTE),
        (_comunas((CONCEPCION, True), (8101, False)), cobertura.MENSAJE_COMUNA_REPETIDA),
        (_comunas((CONCEPCION, "si")), cobertura.MENSAJE_COMUNAS_ILEGIBLES),
        ({"comunas": [{"comuna": CONCEPCION, "es_base": True, "rut": "1"}]}, cobertura.MENSAJE_COMUNAS_ILEGIBLES),
        ({"comunas": [CONCEPCION]}, cobertura.MENSAJE_COMUNAS_ILEGIBLES),
        ({"comunas": [{"es_base": True}]}, cobertura.MENSAJE_COMUNAS_ILEGIBLES),
    ],
)
def test_comunas_invalidas_responden_400_en_el_campo(sesion, cuerpo, mensaje):
    respuesta = _put(sesion, URL_COBERTURA, cuerpo)

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == {"comunas": mensaje}
    assert sin_texto_prohibido(respuesta)
    assert not Cobertura.objects.exists()


def test_el_reemplazo_es_completo_y_atomico(sesion, maestro):
    assert _put(sesion, URL_COBERTURA, _comunas((CONCEPCION, True), (TALCAHUANO, False))).status_code == 200
    antes = list(Cobertura.objects.order_by("comuna_id").values_list("comuna_id", "es_base"))

    # Una lista inválida (código inexistente al final) no borra nada de lo guardado.
    invalida = _comunas((CHIGUAYANTE, True), ("999999", False))
    assert _put(sesion, URL_COBERTURA, invalida).status_code == 400
    assert list(Cobertura.objects.order_by("comuna_id").values_list("comuna_id", "es_base")) == antes

    # Una lista válida reemplaza todo: la comuna quitada ya no está (base de CA-13.2 en S4).
    assert _put(sesion, URL_COBERTURA, _comunas((CHIGUAYANTE, True))).status_code == 200
    assert list(Cobertura.objects.values_list("comuna_id", "es_base")) == [(8103, True)]


def test_si_falla_la_insercion_la_cobertura_anterior_se_conserva(maestro, monkeypatch):
    cobertura.reemplazar_cobertura(maestro, _comunas((CONCEPCION, True))["comunas"])

    def falla(*args, **kwargs):
        raise IntegrityError("simulada")

    monkeypatch.setattr(Cobertura.objects, "bulk_create", falla)
    with pytest.raises(IntegrityError):
        cobertura.reemplazar_cobertura(maestro, _comunas((TALCAHUANO, True))["comunas"])
    assert list(Cobertura.objects.values_list("comuna_id", "es_base")) == [(8101, True)]


def test_la_bd_impide_dos_comunas_base_y_comunas_repetidas(maestro):
    Cobertura.objects.create(maestro_id=maestro.pk, comuna_id=8101, es_base=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        Cobertura.objects.create(maestro_id=maestro.pk, comuna_id=8110, es_base=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        Cobertura.objects.create(maestro_id=maestro.pk, comuna_id=8101, es_base=False)


@pytest.mark.parametrize("estado", [EstadoExpediente.EN_REVISION, EstadoExpediente.OBSERVADO,
                                    EstadoExpediente.APROBADO, EstadoExpediente.SUSPENDIDO])
def test_d7_cobertura_y_agenda_se_editan_en_todo_estado_salvo_rechazado(sesion, maestro, estado):
    _con_estado(maestro, estado)
    assert _put(sesion, URL_COBERTURA, _comunas((CONCEPCION, True))).status_code == 200
    assert post_json(sesion, URL_AGENDA, _bloque()).status_code == 201


def test_d7_rechazado_responde_409_sin_cambios(sesion, maestro):
    _con_estado(maestro, EstadoExpediente.RECHAZADO)

    respuesta = _put(sesion, URL_COBERTURA, _comunas((CONCEPCION, True)))
    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == cobertura.MENSAJE_RECHAZADO
    respuesta = post_json(sesion, URL_AGENDA, _bloque())
    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == agenda.MENSAJE_RECHAZADO
    assert not Cobertura.objects.exists() and not Disponibilidad.objects.exists()


def test_la_cobertura_es_solo_del_maestro_de_la_sesion(sesion, maestro):
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    Cobertura.objects.create(maestro_id=otro.pk, comuna_id=8110, es_base=True)

    respuesta = sesion.get(URL_COBERTURA)

    assert respuesta.json() == {"comunas": []}
    assert_campos_ausentes(respuesta, {"id", "maestro", "perfil_maestro_id", "rut"})


# --- Agenda (RF-07, CA-14.1, CA-14.2, CA-14.4) ---


def test_ca14_1_el_bloque_se_guarda_y_se_muestra_en_24_horas(sesion, maestro):
    respuesta = post_json(sesion, URL_AGENDA, _bloque(dia=3, inicio="13:30", fin="24:00"))

    assert respuesta.status_code == 201
    bloque = respuesta.json()["bloque"]
    assert {k: bloque[k] for k in ("dia_semana", "dia", "inicio", "fin", "inicio_min", "fin_min")} == {
        "dia_semana": 3, "dia": "miércoles", "inicio": "13:30", "fin": "24:00", "inicio_min": 810, "fin_min": 1440,
    }
    assert set(bloque) == {"ref", "dia_semana", "dia", "inicio", "fin", "inicio_min", "fin_min"}
    fila = Disponibilidad.objects.get()
    assert (fila.maestro_id, fila.dia_semana, fila.inicio_min, fila.fin_min) == (maestro.pk, 3, 810, 1440)


def test_ca14_4_los_bloques_guardados_se_conservan_al_volver_a_entrar(maestro):
    primera = _sesion()
    for dia, inicio, fin in [(1, "08:00", "12:00"), (1, "14:00", "18:00"), (6, "09:00", "13:00")]:
        assert post_json(primera, URL_AGENDA, _bloque(dia, inicio, fin)).status_code == 201
    # "Se corta la conexión" antes de terminar: una sesión nueva ve lo ya guardado.
    bloques = _sesion().get(URL_AGENDA).json()["bloques"]

    assert [(b["dia_semana"], b["inicio"], b["fin"]) for b in bloques] == [
        (1, "08:00", "12:00"), (1, "14:00", "18:00"), (6, "09:00", "13:00"),
    ]


@pytest.mark.parametrize(
    ("inicio", "fin", "cruza"),
    [("12:00", "12:00", False), ("12:00", "08:00", True), ("22:00", "02:00", True), ("08:00", "00:00", True)],
    ids=["igual", "anterior", "cruce_de_medianoche", "fin_00"],
)
def test_ca14_2_termino_no_posterior_se_rechaza_con_mensaje_comprensible(sesion, inicio, fin, cruza):
    respuesta = post_json(sesion, URL_AGENDA, _bloque(inicio=inicio, fin=fin))

    assert respuesta.status_code == 400
    mensaje = respuesta.json()["errores"]["fin"]
    assert f"de {inicio} a {fin}" in mensaje
    assert "después de la hora de inicio" in mensaje
    assert ("medianoche" in mensaje) is cruza
    assert "AM" not in mensaje and "PM" not in mensaje
    assert not Disponibilidad.objects.exists()


@pytest.mark.parametrize(
    ("datos", "campo", "mensaje"),
    [
        (_bloque(inicio="08:15"), "inicio", agenda.MENSAJE_GRANULARIDAD),
        (_bloque(fin="12:45"), "fin", agenda.MENSAJE_GRANULARIDAD),
        (_bloque(inicio="25:00"), "inicio", agenda.MENSAJE_HORA_INVALIDA),
        (_bloque(fin="24:30"), "fin", agenda.MENSAJE_HORA_INVALIDA),
        (_bloque(inicio="08:60"), "inicio", agenda.MENSAJE_HORA_INVALIDA),
        (_bloque(inicio="8:00"), "inicio", agenda.MENSAJE_HORA_INVALIDA),
        (_bloque(inicio="08:00 AM"), "inicio", agenda.MENSAJE_HORA_INVALIDA),
        (_bloque(inicio="-01:00"), "inicio", agenda.MENSAJE_HORA_INVALIDA),
        (_bloque(inicio=480), "inicio", agenda.MENSAJE_HORA_INVALIDA),
        (_bloque(inicio="０８:００"), "inicio", agenda.MENSAJE_HORA_INVALIDA),
        (_bloque(inicio="24:00", fin="24:00"), "inicio", agenda.MENSAJE_INICIO_FIN_DE_DIA),
        (_bloque(inicio=None), "inicio", agenda.MENSAJE_HORA_FALTA),
        (_bloque(fin=""), "fin", agenda.MENSAJE_HORA_FALTA),
        (_bloque(dia=0), "dia_semana", agenda.MENSAJE_DIA),
        (_bloque(dia=8), "dia_semana", agenda.MENSAJE_DIA),
        (_bloque(dia=True), "dia_semana", agenda.MENSAJE_DIA),
        (_bloque(dia="lunes"), "dia_semana", agenda.MENSAJE_DIA),
        (_bloque(dia=None), "dia_semana", agenda.MENSAJE_DIA),
    ],
)
def test_granularidad_rango_y_formato_se_validan_en_el_servidor(sesion, datos, campo, mensaje):
    respuesta = post_json(sesion, URL_AGENDA, datos)

    assert respuesta.status_code == 400
    assert respuesta.json()["errores"][campo] == mensaje
    assert sin_texto_prohibido(respuesta)
    assert not Disponibilidad.objects.exists()


@pytest.mark.parametrize(("inicio", "fin"), [("00:00", "24:00"), ("00:00", "00:30"), ("23:30", "24:00")])
def test_bordes_del_dia_validos(sesion, inicio, fin):
    assert post_json(sesion, URL_AGENDA, _bloque(dia="7", inicio=inicio, fin=fin)).status_code == 201


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [("08:00", "12:00"), ("09:00", "10:00"), ("07:00", "08:30"), ("11:30", "13:00"), ("06:00", "14:00")],
)
def test_solapamiento_con_otro_bloque_del_mismo_dia_se_rechaza(sesion, maestro, inicio, fin):
    assert post_json(sesion, URL_AGENDA, _bloque(inicio="08:00", fin="12:00")).status_code == 201

    respuesta = post_json(sesion, URL_AGENDA, _bloque(inicio=inicio, fin=fin))

    assert respuesta.status_code == 400
    mensaje = respuesta.json()["errores"]["inicio"]
    assert "lunes de 08:00 a 12:00" in mensaje and "quita ese horario" in mensaje
    assert Disponibilidad.objects.count() == 1


def test_bloques_contiguos_y_otros_dias_se_aceptan(sesion):
    for datos in [_bloque(inicio="08:00", fin="12:00"), _bloque(inicio="12:00", fin="16:00"),
                  _bloque(inicio="06:00", fin="08:00"), _bloque(dia=2, inicio="08:00", fin="12:00")]:
        assert post_json(sesion, URL_AGENDA, datos).status_code == 201
    assert Disponibilidad.objects.count() == 4


def test_otro_maestro_no_choca_con_mis_bloques(sesion, maestro):
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    Disponibilidad.objects.create(maestro_id=otro.pk, dia_semana=1, inicio_min=480, fin_min=720)

    assert post_json(sesion, URL_AGENDA, _bloque()).status_code == 201
    assert [b["inicio"] for b in sesion.get(URL_AGENDA).json()["bloques"]] == ["08:00"]


def test_quitar_es_baja_logica_y_libera_el_horario(sesion, maestro):
    ref = post_json(sesion, URL_AGENDA, _bloque()).json()["bloque"]["ref"]

    assert sesion.delete(f"{URL_AGENDA}/{ref}").status_code == 204
    fila = Disponibilidad.objects.get(ref=ref)
    assert fila.retirado_en is not None and (fila.inicio_min, fila.fin_min) == (480, 720)
    assert sesion.get(URL_AGENDA).json()["bloques"] == []
    # Editar = quitar y crear otro: el mismo horario ya se puede declarar.
    assert post_json(sesion, URL_AGENDA, _bloque()).status_code == 201
    respuesta = sesion.delete(f"{URL_AGENDA}/{ref}")
    assert respuesta.status_code == 409
    assert respuesta.json()["mensaje"] == agenda.MENSAJE_RETIRADO


@pytest.mark.parametrize(
    ("dia", "inicio", "fin"),
    [(0, 480, 720), (8, 480, 720), (1, 720, 480), (1, 480, 480), (1, 0, 1470), (1, 485, 720), (1, 480, 725)],
)
def test_la_bd_exige_dia_iso_rango_y_multiplos_de_30(maestro, dia, inicio, fin):
    with pytest.raises(IntegrityError), transaction.atomic():
        Disponibilidad.objects.create(maestro_id=maestro.pk, dia_semana=dia, inicio_min=inicio, fin_min=fin)


@pytest.mark.django_db(transaction=True)
def test_dos_bloques_solapados_simultaneos_solo_guardan_uno():
    # transaction=True: cada hilo usa su propia conexión. Estas operaciones no
    # escriben en la bitácora ni en acceso_denegado (tablas de solo inserción).
    usuario = crear_maestro(rut=RUT)
    barrera = threading.Barrier(2)
    resultados = []
    candado = threading.Lock()

    def agregar(inicio, fin):
        try:
            barrera.wait(timeout=10)
            resultado = agenda.agregar_bloque(usuario, _bloque(inicio=inicio, fin=fin))
        except ErroresValidacion as error:
            resultado = error
        finally:
            connection.close()
        with candado:
            resultados.append(resultado)

    hilos = [threading.Thread(target=agregar, args=par) for par in (("08:00", "12:00"), ("10:00", "14:00"))]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    guardados = [r for r in resultados if isinstance(r, Disponibilidad)]
    errores = [r for r in resultados if isinstance(r, ErroresValidacion)]
    assert len(guardados) == 1 and len(errores) == 1, resultados
    assert "inicio" in errores[0].errores
    assert Disponibilidad.objects.filter(maestro_id=usuario.pk, retirado_en__isnull=True).count() == 1


# --- Terceros (RNF-07, CA-25.1; ADR-011) ---


def _administrativo(rol, correo):
    return servicios_identidad.crear_cuenta_administrativa(
        nombre="Admin Prueba", correo=correo, roles=[rol], contrasena=CONTRASENA
    )


def _terceros_sin_rol():
    return {
        "cliente": (lambda: crear_cliente(telefono=TEL_B), "ana.prueba@example.com"),
        "comercial": (lambda: _administrativo(Rol.COMERCIAL, "comercial@example.com"), "comercial@example.com"),
        "curatoria": (lambda: _administrativo(Rol.CURATORIA, "cura@example.com"), "cura@example.com"),
        "moderacion": (lambda: _administrativo(Rol.MODERACION, "moderacion@example.com"), "moderacion@example.com"),
        "control_gestion": (
            lambda: _administrativo(Rol.CONTROL_GESTION, "gestion@example.com"), "gestion@example.com"
        ),
    }


def _bloque_de(maestro):
    return Disponibilidad.objects.create(maestro_id=maestro.pk, dia_semana=1, inicio_min=480, fin_min=720)


def _sigue_activo(bloque):
    bloque.refresh_from_db()
    assert bloque.retirado_en is None


@pytest.mark.terceros("mi_bloque")
def test_otro_maestro_recibe_el_404_identico_y_queda_registrado(maestro):
    bloque = _bloque_de(maestro)
    otro = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)

    respuesta = _sesion(RUT_OTRO).delete(f"{URL_AGENDA}/{bloque.ref}")

    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (otro.pk, "disponibilidad", str(bloque.ref))
    assert fila.recurso == "DELETE api/maestros/disponibilidad/<uuid:ref>"
    _sigue_activo(bloque)


@pytest.mark.terceros("mi_bloque")
@pytest.mark.parametrize("nombre", sorted(_terceros_sin_rol()))
def test_los_roles_sin_maestro_reciben_403_registrado(maestro, nombre):
    bloque = _bloque_de(maestro)
    crear, identificador = _terceros_sin_rol()[nombre]
    tercero = crear()

    respuesta = _sesion(identificador).delete(f"{URL_AGENDA}/{bloque.ref}")

    assert respuesta.status_code == 403
    assert respuesta.json() == {"mensaje": MENSAJE_SIN_ROL, "errores": {}}
    fila = RegistroAccesoDenegado.objects.get()
    assert (fila.usuario_id, fila.entidad, fila.entidad_ref) == (tercero.pk, "ruta", None)
    _sigue_activo(bloque)


@pytest.mark.terceros("mi_bloque")
def test_anonimo_recibe_401_sin_registro(maestro):
    bloque = _bloque_de(maestro)

    respuesta = Client().delete(f"{URL_AGENDA}/{bloque.ref}")

    assert respuesta.status_code == 401
    assert not RegistroAccesoDenegado.objects.exists()
    _sigue_activo(bloque)


@pytest.mark.terceros("mi_bloque")
def test_referencia_inexistente_responde_404_sin_registro(sesion):
    respuesta = sesion.delete(f"{URL_AGENDA}/{uuid.uuid4()}")

    assert respuesta.status_code == 404
    assert respuesta.content == NO_ENCONTRADO
    assert not RegistroAccesoDenegado.objects.exists()


@pytest.mark.parametrize("url", [URL_COBERTURA, URL_AGENDA, "/api/maestros/perfil", "/api/maestros/perfil/foto"])
@pytest.mark.parametrize("nombre", sorted(_terceros_sin_rol()))
def test_las_rutas_del_maestro_exigen_el_rol_maestro(url, nombre):
    crear, identificador = _terceros_sin_rol()[nombre]
    crear()
    client = _sesion(identificador)

    respuesta = client.post(url) if url.endswith("foto") else client.get(url)

    assert respuesta.status_code == 403
    assert RegistroAccesoDenegado.objects.get().entidad == "ruta"


@pytest.mark.parametrize(
    ("metodo", "url"),
    [("post", URL_COBERTURA), ("delete", URL_COBERTURA), ("put", URL_AGENDA), ("delete", URL_AGENDA),
     ("get", "bloque"), ("put", "bloque")],
)
def test_metodos_no_permitidos_responden_405(sesion, maestro, metodo, url):
    destino = f"{URL_AGENDA}/{_bloque_de(maestro).ref}" if url == "bloque" else url
    assert getattr(sesion, metodo)(destino).status_code == 405
