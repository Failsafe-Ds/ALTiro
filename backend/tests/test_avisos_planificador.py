"""Avisos de vencimiento y planificador (RF-35, CA-24.2, CA-24.3, RF-08, CA-17.1, M-08; ADR-016).

Incremento 5 del S2:
- tabla ``aviso`` (una sola emisión, sin datos personales);
- tareas idempotentes de ``expediente.tareas`` (avisos, purga de
  ``acceso_denegado`` y archivos huérfanos), que reciben ``ahora``;
- comando ``planificador`` (``--una-vez`` y bucle con apagado por SIGTERM);
- avisos del maestro en su expediente, ``GET /api/curatoria/avisos`` y el
  filtro ``?por_vencer=1`` de la cola.

La hora sale de Python (time-machine; ADR-014), salvo la purga, que usa
``now()`` de SQL por diseño (ADR-010, punto 3): sus filas antiguas se insertan
con fecha explícita. Datos ficticios (@example.com, RUT sintéticos).
Salvo la prueba en paralelo, sin ``transaction=True``.
"""
import datetime
import io

import logging
import os
import signal
import threading
import uuid

import pytest
import time_machine
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.test import Client

from autorizacion.models import RegistroAccesoDenegado
from bitacora.models import Bitacora
from catalogo.models import Oficio
from comun.api import CABECERA_RECHAZO
from autorizacion import tareas as tareas_autorizacion
from expediente import avisos, servicios, tareas, vigencia
from expediente.management.commands import planificador
from expediente.models import (
    Aviso,
    Documento,
    EstadoDocumento,
    Expediente,
    RolDestinatarioAviso,
    TipoAviso,
    TipoDocumento,
)
from identidad import servicios as servicios_identidad
from identidad.models import Rol
from tests.ayudas import CONTRASENA, TEL_B, crear_cliente, crear_maestro, iniciar_sesion, sin_texto_prohibido
from tests.privacidad import assert_campos_ausentes

UTC = datetime.timezone.utc
# 12:00 en Santiago (UTC-3, horario de verano): "hoy" es el 14 de octubre.
AHORA = datetime.datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
HOY = datetime.date(2026, 10, 14)

RUT_MAESTRO = "11.111.111-1"
RUT_MAESTRO_CANONICO = "111111111"
RUT_OTRO = "22.222.222-2"
NOMBRE_OTRO = "Maestro Dos"
CORREO_CURATORIA = "cura@example.com"
CORREO_CLIENTE = "ana.prueba@example.com"
TEL_MAESTRO = "+56 9 1000 0001"

URL_EXPEDIENTE = "/api/maestros/expediente"
URL_AVISOS = "/api/curatoria/avisos"
URL_COLA = "/api/curatoria/expedientes"

CEDULA = TipoDocumento.CEDULA_IDENTIDAD
ANTECEDENTES = TipoDocumento.CERTIFICADO_ANTECEDENTES
LICENCIA = TipoDocumento.LICENCIA_SEC
CURATORIA = RolDestinatarioAviso.CURATORIA


# --- Ayudas ---


@pytest.fixture
def reloj():
    with time_machine.travel(AHORA, tick=False) as viaje:
        yield viaje


def _en(dias):
    return HOY + datetime.timedelta(days=dias)


def _expediente(usuario):
    return Expediente.objects.get(perfil_maestro_id=usuario.pk)


def _documento(usuario, tipo, vence_en=None, oficio=None, estado=EstadoDocumento.EN_REVISION, motivo=""):
    """Documento sin archivo real (las tareas de avisos no leen archivos)."""
    return Documento.objects.create(
        expediente=_expediente(usuario),
        tipo=tipo,
        oficio=Oficio.objects.get(codigo=oficio) if oficio else None,
        fecha_emision=datetime.date(2020, 1, 10),
        fecha_vencimiento=None if vence_en is None else _en(vence_en),
        estado=estado,
        motivo_observacion=motivo,
        archivo=uuid.uuid4(),
        archivo_reverso=uuid.uuid4() if tipo == CEDULA else None,
    )


def _reemplazar(anterior, **cambios):
    """Nuevo documento del mismo (tipo, oficio); el anterior queda ``reemplazado`` (D-11)."""
    Documento.objects.filter(pk=anterior.pk).update(estado=EstadoDocumento.REEMPLAZADO)
    usuario = anterior.expediente.perfil_maestro.usuario
    nuevo = _documento(usuario, anterior.tipo, oficio=anterior.oficio.codigo if anterior.oficio else None, **cambios)
    Documento.objects.filter(pk=nuevo.pk).update(reemplaza_a=anterior)
    return nuevo


def _avisos_de(documento):
    return set(Aviso.objects.filter(documento=documento).values_list("destinatario_id", "destinatario_rol"))


def _administrativo(rol, correo, nombre="Admin Prueba"):
    return servicios_identidad.crear_cuenta_administrativa(nombre=nombre, correo=correo, roles=[rol], contrasena=CONTRASENA)


def _sesion(identificador):
    client = Client()
    assert iniciar_sesion(client, identificador).status_code == 200
    return client


@pytest.fixture
def maestro():
    return crear_maestro(rut=RUT_MAESTRO)


@pytest.fixture
def otro_maestro():
    usuario = crear_maestro(rut=RUT_OTRO, telefono=TEL_B)
    usuario.nombre = NOMBRE_OTRO
    usuario.save(update_fields=["nombre"])
    return usuario


# --- Modelo Aviso (ADR-016, punto 2) ---


def test_la_tabla_aviso_no_tiene_campos_con_datos_personales():
    assert {campo.column for campo in Aviso._meta.concrete_fields} == {
        "id", "tipo", "documento_id", "destinatario_id", "destinatario_rol", "creado_en",
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "destinatario",
    [{}, {"destinatario_rol": CURATORIA, "con_usuario": True}],
    ids=["ninguno", "ambos"],
)
def test_aviso_exige_exactamente_un_destinatario(maestro, destinatario):
    documento = _documento(maestro, ANTECEDENTES, vence_en=10)
    usuario = maestro if destinatario.pop("con_usuario", False) else None
    with pytest.raises(IntegrityError), transaction.atomic():
        Aviso.objects.create(tipo=TipoAviso.DOCUMENTO_POR_VENCER, documento=documento, destinatario=usuario,
                             **destinatario)


@pytest.mark.django_db
def test_aviso_rechaza_tipo_o_rol_desconocido(maestro):
    documento = _documento(maestro, ANTECEDENTES, vence_en=10)
    with pytest.raises(IntegrityError), transaction.atomic():
        Aviso.objects.create(tipo="otro", documento=documento, destinatario_rol=CURATORIA)
    with pytest.raises(IntegrityError), transaction.atomic():
        Aviso.objects.create(tipo=TipoAviso.DOCUMENTO_POR_VENCER, documento=documento, destinatario_rol="comercial")


@pytest.mark.django_db
@pytest.mark.parametrize("al_rol", [True, False], ids=["rol", "cuenta"])
def test_el_unique_impide_un_segundo_aviso_igual(maestro, al_rol):
    documento = _documento(maestro, ANTECEDENTES, vence_en=10)
    datos = {"destinatario_rol": CURATORIA} if al_rol else {"destinatario": maestro}
    Aviso.objects.create(tipo=TipoAviso.DOCUMENTO_POR_VENCER, documento=documento, **datos)
    # nulls_distinct=False: el destinatario nulo cuenta como un valor.
    with pytest.raises(IntegrityError), transaction.atomic():
        Aviso.objects.create(tipo=TipoAviso.DOCUMENTO_POR_VENCER, documento=documento, **datos)


# --- Tarea de avisos (RF-35, CA-24.2, CA-24.3) ---


@pytest.mark.django_db
@pytest.mark.parametrize(("vence_en", "avisa"), [(1, True), (29, True), (30, True), (31, False), (200, False)])
def test_aviso_cuando_faltan_30_dias_o_menos(maestro, vence_en, avisa):
    documento = _documento(maestro, ANTECEDENTES, vence_en=vence_en)

    creados = tareas.emitir_avisos_por_vencer(AHORA)

    esperado = {(maestro.pk, None), (None, CURATORIA)} if avisa else set()
    assert _avisos_de(documento) == esperado
    assert creados == len(esperado)


@pytest.mark.django_db
def test_ca24_2_aviso_al_maestro_y_a_curatoria_al_alcanzar_el_umbral(maestro):
    documento = _documento(maestro, ANTECEDENTES, vence_en=31)
    assert tareas.emitir_avisos_por_vencer(AHORA) == 0

    manana = AHORA + datetime.timedelta(days=1)
    assert tareas.emitir_avisos_por_vencer(manana) == 2

    assert _avisos_de(documento) == {(maestro.pk, None), (None, CURATORIA)}
    assert set(Aviso.objects.values_list("creado_en", flat=True)) == {manana}


@pytest.mark.django_db
def test_el_umbral_se_calcula_con_la_fecha_de_santiago(maestro):
    documento = _documento(maestro, ANTECEDENTES, vence_en=31)
    # 02:30 UTC del 15 de octubre: en UTC faltan 30 días, en Santiago todavía 31.
    casi_medianoche = datetime.datetime(2026, 10, 15, 2, 30, tzinfo=UTC)
    assert tareas.emitir_avisos_por_vencer(casi_medianoche) == 0
    assert tareas.emitir_avisos_por_vencer(casi_medianoche + datetime.timedelta(hours=1)) == 2
    assert _avisos_de(documento) == {(maestro.pk, None), (None, CURATORIA)}


@pytest.mark.django_db
def test_rf35_el_aviso_se_emite_una_sola_vez(maestro):
    documento = _documento(maestro, ANTECEDENTES, vence_en=30)

    assert tareas.emitir_avisos_por_vencer(AHORA) == 2
    assert tareas.emitir_avisos_por_vencer(AHORA) == 0
    for dias in range(1, 30):
        assert tareas.emitir_avisos_por_vencer(AHORA + datetime.timedelta(days=dias)) == 0

    assert Aviso.objects.filter(documento=documento).count() == 2


@pytest.mark.django_db(transaction=True)
def test_rf35_dos_corridas_en_paralelo_emiten_una_sola_vez():
    # transaction=True: cada hilo usa su propia conexión. Esta prueba no escribe
    # en la bitácora ni en acceso_denegado; la tabla aviso se vacía al terminar.
    usuario = crear_maestro(rut=RUT_MAESTRO)
    documentos = [_documento(usuario, tipo, vence_en=10) for tipo in (CEDULA, ANTECEDENTES)]
    barrera = threading.Barrier(2)
    resultados = []

    def correr():
        try:
            barrera.wait(timeout=10)
            resultados.append(tareas.emitir_avisos_por_vencer(AHORA))
        except Exception as error:  # noqa: BLE001 — se reporta en la aserción.
            resultados.append(error)
        finally:
            connection.close()

    hilos = [threading.Thread(target=correr) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    assert all(isinstance(r, int) for r in resultados), resultados
    assert sum(resultados) == 4
    for documento in documentos:
        assert _avisos_de(documento) == {(usuario.pk, None), (None, CURATORIA)}


@pytest.mark.django_db
def test_ca24_3_un_documento_sin_vencimiento_nunca_avisa(maestro):
    _documento(maestro, ANTECEDENTES, vence_en=None)
    for dias in (0, 400, 4000):
        assert tareas.emitir_avisos_por_vencer(AHORA + datetime.timedelta(days=dias)) == 0
    assert not Aviso.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("vence_en", [0, -1, -40])
def test_un_documento_ya_vencido_no_avisa(maestro, vence_en):
    _documento(maestro, ANTECEDENTES, vence_en=vence_en)
    assert tareas.emitir_avisos_por_vencer(AHORA) == 0
    assert not Aviso.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("estado", [EstadoDocumento.EN_REVISION, EstadoDocumento.OBSERVADO, EstadoDocumento.VALIDADO])
def test_avisa_por_todo_documento_actual_cualquiera_sea_su_estado(maestro, estado):
    documento = _documento(maestro, ANTECEDENTES, vence_en=15, estado=estado,
                           motivo="Foto borrosa" if estado == EstadoDocumento.OBSERVADO else "")
    assert tareas.emitir_avisos_por_vencer(AHORA) == 2
    assert _avisos_de(documento) == {(maestro.pk, None), (None, CURATORIA)}


@pytest.mark.django_db
def test_un_documento_reemplazado_no_avisa(maestro):
    anterior = _documento(maestro, ANTECEDENTES, vence_en=10, estado=EstadoDocumento.VALIDADO)
    nuevo = _reemplazar(anterior, vence_en=300)

    assert tareas.emitir_avisos_por_vencer(AHORA) == 0
    assert not Aviso.objects.filter(documento__in=[anterior, nuevo]).exists()


@pytest.mark.django_db
def test_e1_la_licencia_reemplazada_que_sigue_contando_avisa(maestro):
    """ADR-017, E-1: la licencia validada anterior habilita el oficio mientras la nueva no esté validada."""
    servicios.declarar_oficios(_expediente(maestro), ["gas"])
    anterior = _documento(maestro, LICENCIA, vence_en=20, oficio="gas", estado=EstadoDocumento.VALIDADO)
    nueva = _reemplazar(anterior, vence_en=800)
    assert vigencia.licencia_habilitante(_expediente(maestro), anterior.oficio, HOY) == anterior

    assert tareas.emitir_avisos_por_vencer(AHORA) == 2
    assert _avisos_de(anterior) == {(maestro.pk, None), (None, CURATORIA)}
    assert not _avisos_de(nueva)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "estado_nueva",
    [EstadoDocumento.VALIDADO, "observada_antes"],
    ids=["la_nueva_ya_esta_validada", "la_anterior_fue_observada"],
)
def test_e1_la_licencia_reemplazada_que_ya_no_cuenta_no_avisa(maestro, estado_nueva):
    servicios.declarar_oficios(_expediente(maestro), ["gas"])
    if estado_nueva == EstadoDocumento.VALIDADO:
        anterior = _documento(maestro, LICENCIA, vence_en=20, oficio="gas", estado=EstadoDocumento.VALIDADO)
        _reemplazar(anterior, vence_en=800, estado=EstadoDocumento.VALIDADO)
    else:
        anterior = _documento(maestro, LICENCIA, vence_en=20, oficio="gas", estado=EstadoDocumento.OBSERVADO,
                              motivo="Ilegible")
        _reemplazar(anterior, vence_en=800)

    assert tareas.emitir_avisos_por_vencer(AHORA) == 0
    assert not _avisos_de(anterior)


@pytest.mark.django_db
def test_la_tarea_de_avisos_no_escribe_en_la_bitacora(maestro):
    _documento(maestro, ANTECEDENTES, vence_en=5)
    assert tareas.emitir_avisos_por_vencer(AHORA) == 2
    assert not Bitacora.objects.exists()


# --- Purga de acceso_denegado (ADR-010, punto 3; M-08; cierra DA-06) ---


def _insertar_denegacion(usuario_id, dias_atras):
    # La purga usa now() de SQL (ADR-010): la fecha antigua se fija en SQL.
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO acceso_denegado (fecha, usuario_id, recurso, entidad) "
            "VALUES (now() - make_interval(days => %s), %s, 'GET /api/x', 'ruta') RETURNING id",
            [dias_atras, usuario_id],
        )
        return cursor.fetchone()[0]


@pytest.mark.django_db
def test_purga_borra_solo_las_filas_de_mas_de_90_dias(maestro):
    antigua = _insertar_denegacion(maestro.pk, 91)
    limite = _insertar_denegacion(maestro.pk, 89)
    reciente = _insertar_denegacion(maestro.pk, 0)

    assert tareas_autorizacion.purgar_accesos_denegados(AHORA) == 1

    assert set(RegistroAccesoDenegado.objects.values_list("id", flat=True)) == {limite, reciente}
    assert antigua not in set(RegistroAccesoDenegado.objects.values_list("id", flat=True))
    # Idempotente.
    assert tareas_autorizacion.purgar_accesos_denegados(AHORA) == 0


# --- Archivos huérfanos (ADR-015) ---


@pytest.fixture
def directorio_documentos(settings, tmp_path):
    directorio = tmp_path / "documentos"
    directorio.mkdir(mode=0o700)
    settings.ALTIRO_DOCUMENTOS_DIR = directorio
    return directorio


def _archivo(directorio, nombre, antiguedad_segundos):
    ruta = directorio / nombre
    ruta.write_bytes(b"cifrado-ficticio")
    marca = AHORA.timestamp() - antiguedad_segundos
    os.utime(ruta, (marca, marca))
    return ruta


@pytest.mark.django_db
def test_limpieza_borra_solo_huerfanos_antiguos(directorio_documentos, maestro):
    hora = tareas.MARGEN_HUERFANOS_SEGUNDOS
    documento = _documento(maestro, CEDULA, vence_en=None)
    reemplazado = _documento(maestro, ANTECEDENTES, estado=EstadoDocumento.VALIDADO)
    _reemplazar(reemplazado)
    referenciados = [
        _archivo(directorio_documentos, str(documento.archivo), 90 * 86400),
        _archivo(directorio_documentos, str(documento.archivo_reverso), 90 * 86400),
        # Un reemplazado se conserva (RNF-26, V-04).
        _archivo(directorio_documentos, str(reemplazado.archivo), 90 * 86400),
    ]
    huerfano_antiguo = _archivo(directorio_documentos, str(uuid.uuid4()), hora + 60)
    temporal_antiguo = _archivo(directorio_documentos, ".subiendo-abc123", 2 * hora)
    conservados = [
        # Subidas en curso: menos de una hora.
        _archivo(directorio_documentos, str(uuid.uuid4()), hora - 60),
        _archivo(directorio_documentos, ".subiendo-xyz789", 10),
        # Archivos que la aplicación no crea: nunca se tocan.
        _archivo(directorio_documentos, "notas.txt", 90 * 86400),
        _archivo(directorio_documentos, str(uuid.uuid4()).upper(), 90 * 86400),
    ]
    (directorio_documentos / str(uuid.uuid4())).mkdir()

    assert tareas.limpiar_archivos_huerfanos(AHORA) == 2

    assert not huerfano_antiguo.exists()
    assert not temporal_antiguo.exists()
    for ruta in referenciados + conservados:
        assert ruta.exists(), ruta.name
    # Idempotente.
    assert tareas.limpiar_archivos_huerfanos(AHORA) == 0


@pytest.mark.django_db
def test_limpieza_nunca_borra_un_archivo_referenciado_aunque_sea_antiguo(directorio_documentos, maestro):
    documento = _documento(maestro, ANTECEDENTES, vence_en=None)
    ruta = _archivo(directorio_documentos, str(documento.archivo), 10 * 365 * 86400)
    assert tareas.limpiar_archivos_huerfanos(AHORA + datetime.timedelta(days=3650)) == 0
    assert ruta.exists()


# --- Comando planificador (ADR-016, punto 1) ---


@pytest.fixture
def salida_consola():
    """Lo que escribe el handler ``consola`` (con ``FiltroTrazasSeguras``)."""
    consola = next(h for h in logging.getLogger().handlers if h.get_name() == "consola")
    salida = io.StringIO()
    anterior = consola.setStream(salida)
    yield salida
    consola.setStream(anterior)


def _tareas_simuladas(monkeypatch, fallan=()):
    llamadas = []

    def simulada(nombre):
        def tarea(ahora):
            llamadas.append((nombre, ahora))
            if nombre in fallan:
                raise RuntimeError("falla simulada")
            return 7

        return tarea

    monkeypatch.setattr(planificador, "TAREAS", tuple((n, simulada(n)) for n, _ in planificador.TAREAS))
    return llamadas


def test_el_planificador_tiene_las_tres_tareas_en_orden():
    assert planificador.TAREAS == (
        ("avisos_creados", tareas.emitir_avisos_por_vencer),
        ("accesos_denegados_purgados", tareas_autorizacion.purgar_accesos_denegados),
        ("archivos_huerfanos_borrados", tareas.limpiar_archivos_huerfanos),
    )


@pytest.mark.django_db
def test_una_vez_corre_las_tres_tareas_con_el_mismo_ahora(monkeypatch, reloj, salida_consola):
    llamadas = _tareas_simuladas(monkeypatch)

    call_command("planificador", "--una-vez")

    assert [nombre for nombre, _ in llamadas] == [n for n, _ in planificador.TAREAS]
    assert {ahora for _, ahora in llamadas} == {AHORA}
    assert (
        "Planificador: corrida terminada. avisos_creados=7 accesos_denegados_purgados=7 "
        "archivos_huerfanos_borrados=7 tareas_fallidas=0"
    ) in salida_consola.getvalue()


@pytest.mark.django_db
@pytest.mark.parametrize("falla", [n for n, _ in planificador.TAREAS])
def test_la_falla_de_una_tarea_no_detiene_las_demas(monkeypatch, salida_consola, falla):
    llamadas = _tareas_simuladas(monkeypatch, fallan={falla})

    with pytest.raises(CommandError):
        call_command("planificador", "--una-vez")

    assert [nombre for nombre, _ in llamadas] == [n for n, _ in planificador.TAREAS]
    texto = salida_consola.getvalue()
    assert f"Planificador: falló la tarea {falla}." in texto
    assert "tareas_fallidas=1" in texto
    assert "RuntimeError: falla simulada" in texto


@pytest.mark.django_db
def test_un_error_de_base_de_datos_en_una_tarea_se_registra_sin_datos(monkeypatch, maestro, salida_consola):
    """La traza pasa por FiltroTrazasSeguras: sin el DETAIL de PostgreSQL con la fila."""
    documento = _documento(maestro, ANTECEDENTES, vence_en=5)

    def duplicar(ahora):
        with transaction.atomic():
            for _ in range(2):
                Aviso.objects.create(tipo=TipoAviso.DOCUMENTO_POR_VENCER, documento=documento, destinatario=maestro)

    monkeypatch.setattr(planificador, "TAREAS", (("duplicar", duplicar),) + planificador.TAREAS[1:])
    conteos, fallidas = planificador.correr_tareas(AHORA)

    assert fallidas == ["duplicar"]
    assert set(conteos) == {"accesos_denegados_purgados", "archivos_huerfanos_borrados"}
    texto = salida_consola.getvalue()
    assert "restriccion=aviso_una_vez" in texto
    for ausente in ("DETAIL", "Key (", str(maestro.pk) + ")", "Maestro Uno", RUT_MAESTRO_CANONICO):
        assert ausente not in texto, ausente


@pytest.mark.django_db
def test_los_registros_del_planificador_no_tienen_datos_personales(maestro, directorio_documentos, salida_consola):
    """RNF-22 (en parte), NTI-09: solo conteos."""
    documento = _documento(maestro, CEDULA, vence_en=12)
    _archivo(directorio_documentos, str(uuid.uuid4()), 2 * tareas.MARGEN_HUERFANOS_SEGUNDOS)
    _insertar_denegacion(maestro.pk, 100)

    conteos, fallidas = planificador.correr_tareas(AHORA)

    assert fallidas == []
    assert conteos == {"avisos_creados": 2, "accesos_denegados_purgados": 1, "archivos_huerfanos_borrados": 1}
    texto = salida_consola.getvalue()
    assert "Avisos de documentos por vencer creados: 2." in texto
    assert "Archivos huérfanos de documentos eliminados: 1." in texto
    for ausente in ("Maestro Uno", RUT_MAESTRO_CANONICO, TEL_MAESTRO, "56910000001", str(documento.ref),
                    str(documento.archivo), str(_expediente(maestro).ref)):
        assert ausente not in texto, ausente


def test_el_bucle_se_detiene_limpio_con_sigterm(monkeypatch, salida_consola):
    corridas = []

    def correr(ahora=None):
        corridas.append(ahora)
        # SIGTERM llega durante la corrida: termina la corrida y sale sin esperar el intervalo.
        os.kill(os.getpid(), signal.SIGTERM)
        return {}, []

    monkeypatch.setattr(planificador, "correr_tareas", correr)
    anteriores = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        hilo_seguridad = threading.Timer(20, lambda: os.kill(os.getpid(), signal.SIGINT))
        hilo_seguridad.start()
        planificador.Command()._bucle(intervalo=3600)
        hilo_seguridad.cancel()
    finally:
        for senal, manejador in anteriores.items():
            signal.signal(senal, manejador)

    assert len(corridas) == 1
    texto = salida_consola.getvalue()
    assert "Planificador iniciado. intervalo_segundos=3600" in texto
    assert "Planificador detenido." in texto
    assert planificador.ARCHIVO_LATIDO.exists()


def test_el_bucle_repite_las_corridas_segun_el_intervalo(monkeypatch):
    corridas = []

    def correr(ahora=None):
        corridas.append(ahora)
        if len(corridas) == 3:
            os.kill(os.getpid(), signal.SIGTERM)
        return {}, []

    monkeypatch.setattr(planificador, "correr_tareas", correr)
    anteriores = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        planificador.Command()._bucle(intervalo=0.05)
    finally:
        for senal, manejador in anteriores.items():
            signal.signal(senal, manejador)

    assert len(corridas) == 3


def test_el_intervalo_por_defecto_es_una_hora(settings):
    from altiro.configuracion import leer_entero

    assert leer_entero("ALTIRO_PLANIFICADOR_VARIABLE_INEXISTENTE", por_defecto=3600) == 3600
    assert settings.ALTIRO_PLANIFICADOR_INTERVALO_SEGUNDOS > 0


# --- Avisos en el expediente del maestro (RF-35, RF-08, CA-17.1) ---


@pytest.mark.django_db
def test_el_maestro_ve_dias_restantes_por_documento(reloj, maestro):
    _documento(maestro, CEDULA, vence_en=None)
    _documento(maestro, ANTECEDENTES, vence_en=45)

    datos = _sesion(RUT_MAESTRO).get(URL_EXPEDIENTE).json()["expediente"]

    por_tipo = {d["tipo"]: d for d in datos["documentos"]}
    assert (por_tipo[CEDULA]["dias_restantes"], por_tipo[CEDULA]["vigente"]) == (None, True)
    assert (por_tipo[ANTECEDENTES]["dias_restantes"], por_tipo[ANTECEDENTES]["vigente"]) == (45, True)


@pytest.mark.django_db
@pytest.mark.parametrize(("vence_en", "dias", "vigente"), [(1, 1, True), (0, 0, False), (-3, -3, False)])
def test_el_maestro_ve_el_documento_vencido_con_dias_no_positivos(reloj, maestro, vence_en, dias, vigente):
    _documento(maestro, ANTECEDENTES, vence_en=vence_en)
    (documento,) = _sesion(RUT_MAESTRO).get(URL_EXPEDIENTE).json()["expediente"]["documentos"]
    assert (documento["dias_restantes"], documento["vigente"]) == (dias, vigente)


@pytest.mark.django_db
def test_el_maestro_ve_su_aviso_con_lista_explicita(reloj, maestro):
    servicios.declarar_oficios(_expediente(maestro), ["gas"])
    licencia = _documento(maestro, LICENCIA, vence_en=20, oficio="gas")
    tareas.emitir_avisos_por_vencer(AHORA)

    respuesta = _sesion(RUT_MAESTRO).get(URL_EXPEDIENTE)

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    assert respuesta.json()["expediente"]["avisos"] == [
        {
            "tipo": "documento_por_vencer",
            "documento": {"ref": str(licencia.ref), "tipo": "licencia_sec", "oficio": {"codigo": "gas", "nombre": "Gas"}},
            "fecha_vencimiento": "2026-11-03",
            "dias_restantes": 20,
            "creado_en": AHORA.isoformat(),
            "mensaje": "Tu licencia SEC de Gas vence en 20 días, el 3 de noviembre de 2026. "
            "Sube el documento nuevo antes de esa fecha.",
        }
    ]
    assert sin_texto_prohibido(respuesta)
    assert_campos_ausentes(respuesta, {"id", "pk", "destinatario", "destinatario_id", "destinatario_rol", "archivo"})


@pytest.mark.django_db
def test_el_aviso_se_actualiza_al_mostrarlo_y_desaparece_al_vencer(reloj, maestro):
    _documento(maestro, ANTECEDENTES, vence_en=2)
    tareas.emitir_avisos_por_vencer(AHORA)
    reloj.shift(datetime.timedelta(days=1))
    (aviso,) = _sesion(RUT_MAESTRO).get(URL_EXPEDIENTE).json()["expediente"]["avisos"]
    assert aviso["dias_restantes"] == 1
    assert aviso["mensaje"].startswith("Tu certificado de antecedentes vence mañana, el 16 de octubre de 2026.")

    reloj.shift(datetime.timedelta(days=1))
    assert _sesion(RUT_MAESTRO).get(URL_EXPEDIENTE).json()["expediente"]["avisos"] == []
    # La fila se conserva: no se vuelve a emitir.
    assert Aviso.objects.count() == 2


@pytest.mark.django_db
def test_el_aviso_de_la_licencia_reemplazada_que_cuenta_lo_explica(reloj, maestro):
    servicios.declarar_oficios(_expediente(maestro), ["gas"])
    anterior = _documento(maestro, LICENCIA, vence_en=20, oficio="gas", estado=EstadoDocumento.VALIDADO)
    nueva = _reemplazar(anterior, vence_en=800)
    tareas.emitir_avisos_por_vencer(AHORA)
    navegador = _sesion(RUT_MAESTRO)

    (aviso,) = navegador.get(URL_EXPEDIENTE).json()["expediente"]["avisos"]
    assert aviso["documento"]["ref"] == str(anterior.ref)
    assert aviso["mensaje"].endswith("Ya subiste la nueva: falta que la revisen.")

    # Curatoría valida la nueva: la anterior deja de contar y el aviso ya no se muestra.
    Documento.objects.filter(pk=nueva.pk).update(estado=EstadoDocumento.VALIDADO)
    assert navegador.get(URL_EXPEDIENTE).json()["expediente"]["avisos"] == []


@pytest.mark.django_db
def test_un_maestro_no_ve_los_avisos_de_otro(reloj, maestro, otro_maestro):
    _documento(otro_maestro, ANTECEDENTES, vence_en=10)
    tareas.emitir_avisos_por_vencer(AHORA)

    respuesta = _sesion(RUT_MAESTRO).get(URL_EXPEDIENTE)

    assert respuesta.json()["expediente"]["avisos"] == []
    assert_campos_ausentes(respuesta, set(), valores=[NOMBRE_OTRO, "222222222"])


# --- GET /api/curatoria/avisos (RF-35; ADR-011, E-2) ---


@pytest.fixture
def cura():
    _administrativo(Rol.CURATORIA, CORREO_CURATORIA, nombre="Cura Revisora")
    return _sesion(CORREO_CURATORIA)


@pytest.mark.django_db
def test_curatoria_ve_los_avisos_del_rol_con_lista_explicita(reloj, maestro, otro_maestro, cura):
    antecedentes = _documento(otro_maestro, ANTECEDENTES, vence_en=30)
    cedula = _documento(maestro, CEDULA, vence_en=3)
    tareas.emitir_avisos_por_vencer(AHORA)

    respuesta = cura.get(URL_AVISOS)

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    assert respuesta.json() == {
        "avisos": [
            {
                "tipo": "documento_por_vencer",
                "documento": {"ref": str(cedula.ref), "tipo": "cedula_identidad", "oficio": None},
                "fecha_vencimiento": "2026-10-17",
                "dias_restantes": 3,
                "creado_en": AHORA.isoformat(),
                "mensaje": "La cédula de identidad vence en 3 días, el 17 de octubre de 2026.",
                "expediente": {"ref": str(_expediente(maestro).ref), "nombre": "Maestro Uno"},
            },
            {
                "tipo": "documento_por_vencer",
                "documento": {"ref": str(antecedentes.ref), "tipo": "certificado_antecedentes", "oficio": None},
                "fecha_vencimiento": "2026-11-13",
                "dias_restantes": 30,
                "creado_en": AHORA.isoformat(),
                "mensaje": "El certificado de antecedentes vence en 30 días, el 13 de noviembre de 2026.",
                "expediente": {"ref": str(_expediente(otro_maestro).ref), "nombre": NOMBRE_OTRO},
            },
        ]
    }
    # Minimización: sin RUT, contacto ni ids internos.
    assert_campos_ausentes(
        respuesta,
        {"rut", "telefono", "correo", "id", "pk", "destinatario", "destinatario_id", "archivo"},
        valores=[RUT_MAESTRO_CANONICO, "222222222", "56910000001", "56910000002"],
    )


@pytest.mark.django_db
def test_curatoria_duena_no_ve_los_avisos_de_su_propio_expediente(reloj, maestro, otro_maestro):
    """Conflicto de interés (ADR-011, E-2; ADR-013, punto 2.5)."""
    servicios_identidad.asignar_rol_administrativo(maestro, Rol.CURATORIA)
    _documento(maestro, ANTECEDENTES, vence_en=10)
    ajeno = _documento(otro_maestro, ANTECEDENTES, vence_en=10)
    tareas.emitir_avisos_por_vencer(AHORA)
    navegador = _sesion(RUT_MAESTRO)

    respuesta = navegador.get(URL_AVISOS)

    assert respuesta.status_code == 200
    assert [a["documento"]["ref"] for a in respuesta.json()["avisos"]] == [str(ajeno.ref)]
    # Como maestro sí ve su propio aviso en su expediente.
    (propio,) = navegador.get(URL_EXPEDIENTE).json()["expediente"]["avisos"]
    assert propio["dias_restantes"] == 10


@pytest.mark.django_db
def test_curatoria_avisos_sin_sesion_responde_401():
    respuesta = Client().get(URL_AVISOS)
    assert respuesta.status_code == 401
    assert sin_texto_prohibido(respuesta)


@pytest.mark.django_db
@pytest.mark.parametrize("rol", ["cliente", "maestro", Rol.COMERCIAL, Rol.MODERACION, Rol.CONTROL_GESTION])
def test_curatoria_avisos_sin_rol_responde_403_registrado(reloj, maestro, otro_maestro, rol):
    _documento(maestro, ANTECEDENTES, vence_en=10)
    tareas.emitir_avisos_por_vencer(AHORA)
    if rol == "cliente":
        usuario = crear_cliente(correo=CORREO_CLIENTE, telefono="+56 9 1000 0003")
        navegador = _sesion(CORREO_CLIENTE)
    elif rol == "maestro":
        usuario = otro_maestro
        navegador = _sesion(RUT_OTRO)
    else:
        usuario = _administrativo(rol, "admin@example.com")
        navegador = _sesion("admin@example.com")

    respuesta = navegador.get(URL_AVISOS)

    assert respuesta.status_code == 403
    assert CABECERA_RECHAZO not in respuesta
    assert "avisos" not in respuesta.json()
    assert sin_texto_prohibido(respuesta)
    assert RegistroAccesoDenegado.objects.filter(usuario_id=usuario.pk).count() == 1


@pytest.mark.django_db
def test_curatoria_avisos_solo_admite_get(cura):
    assert cura.post(URL_AVISOS, data="{}", content_type="application/json").status_code == 405


# --- Detalle y cola de curatoría ---


@pytest.mark.django_db
def test_el_detalle_de_curatoria_trae_dias_restantes(reloj, maestro, cura):
    _documento(maestro, ANTECEDENTES, vence_en=12)
    _documento(maestro, CEDULA, vence_en=None)

    datos = cura.get(f"{URL_COLA}/{_expediente(maestro).ref}").json()["expediente"]

    assert {d["tipo"]: d["dias_restantes"] for d in datos["documentos"]} == {ANTECEDENTES: 12, CEDULA: None}


@pytest.mark.django_db
def test_cola_filtra_por_vencer(reloj, maestro, otro_maestro, cura):
    _documento(maestro, ANTECEDENTES, vence_en=30)
    _documento(otro_maestro, ANTECEDENTES, vence_en=31)
    tercero = crear_maestro(rut="33.333.333-3", telefono="+56 9 1000 0004")
    _documento(tercero, CEDULA, vence_en=None)

    respuesta = cura.get(URL_COLA, {"por_vencer": "1"})

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert [e["ref"] for e in datos["expedientes"]] == [str(_expediente(maestro).ref)]
    assert datos["total"] == 1
    # Sin el filtro aparecen los tres.
    assert cura.get(URL_COLA).json()["total"] == 3


@pytest.mark.django_db
def test_cola_por_vencer_excluye_el_expediente_propio(reloj, maestro):
    servicios_identidad.asignar_rol_administrativo(maestro, Rol.CURATORIA)
    _documento(maestro, ANTECEDENTES, vence_en=10)
    assert _sesion(RUT_MAESTRO).get(URL_COLA, {"por_vencer": "1"}).json()["total"] == 0


@pytest.mark.django_db
@pytest.mark.parametrize("valor", ["0", "true", "", "si"])
def test_cola_por_vencer_con_valor_desconocido_responde_400(cura, valor):
    respuesta = cura.get(URL_COLA, {"por_vencer": valor})
    assert respuesta.status_code == 400
    assert sin_texto_prohibido(respuesta)


def test_mensaje_de_aviso_para_cada_tipo_de_documento():
    def doc(tipo, oficio=None, estado=EstadoDocumento.EN_REVISION):
        return Documento(tipo=tipo, oficio=oficio, estado=estado, fecha_emision=datetime.date(2020, 1, 1),
                         fecha_vencimiento=_en(1))

    assert avisos.mensaje(doc(CEDULA), HOY, para_maestro=True) == (
        "Tu cédula de identidad vence mañana, el 15 de octubre de 2026. Sube el documento nuevo antes de esa fecha."
    )
    assert avisos.mensaje(doc(ANTECEDENTES), HOY, para_maestro=False) == (
        "El certificado de antecedentes vence mañana, el 15 de octubre de 2026."
    )
    licencia = doc(LICENCIA, oficio=Oficio(codigo="electricidad", nombre="Electricidad"),
                   estado=EstadoDocumento.REEMPLAZADO)
    assert avisos.mensaje(licencia, HOY, para_maestro=False) == (
        "La licencia SEC de Electricidad vence mañana, el 15 de octubre de 2026. Hay una licencia nueva sin validar."
    )
    for texto in (avisos.mensaje(doc(CEDULA), HOY, True), avisos.mensaje(licencia, HOY, False)):
        assert not {"_", "null", "None"} & set(texto.split())
        assert "licencia_sec" not in texto and "cedula_identidad" not in texto

