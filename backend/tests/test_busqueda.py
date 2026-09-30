"""Búsqueda pública (S4, incremento 2): RF-09 a RF-13, RF-06, CA-02.x, CA-03.x, CA-04.1, CA-13.2, CA-24.4,
RNF-01 (consultas constantes), RNF-15/17 y ficha con bloques (RF-14; ADR-022; ADR-020, E-1).

Reloj fijo: miércoles 7 de octubre de 2026, 08:00 en Santiago (``busqueda_ayudas.AHORA``).
Días de la semana relativos: miércoles = hoy, jueves = hoy+1, sábado = hoy+3,
domingo = hoy+4. Datos ficticios (``tests/busqueda_ayudas.py``).
"""
import datetime
import itertools
import json

import pytest
import time_machine
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from busqueda import puntaje, servicios as busqueda_servicios, sugerencias
from busqueda.vistas import MENSAJE_SIN_RESULTADOS, SIN_EVALUACIONES
from comun.api import MENSAJE_CLAVE_DESCONOCIDA
from expediente.models import Documento, EstadoExpediente, Expediente
from perfil import agenda, cobertura, ocupacion, ocurrencias, publicacion
from perfil.models import Cobertura, PerfilPublico
from tests import busqueda_ayudas as ay
from tests.ayudas import TEXTO_PROHIBIDO
from tests.privacidad import assert_campos_ausentes

pytestmark = pytest.mark.django_db

URL = ay.URL
D = datetime.timedelta


@pytest.fixture
def reloj():
    with time_machine.travel(ay.AHORA, tick=False):
        yield


@pytest.fixture
def catalogo(reloj):
    return ay.catalogo_basico()


def buscar(**parametros):
    parametros.setdefault("oficio", "pintura")
    parametros.setdefault("comuna", str(ay.CONCEPCION))
    return Client().get(URL, {k: v for k, v in parametros.items() if v is not None})


def con_bloque(fecha, inicio, fin, **parametros):
    return buscar(fecha=fecha.isoformat(), inicio=inicio, fin=fin, **parametros)


def todas_las_refs(**parametros):
    """Refs de todas las páginas."""
    primera = buscar(**parametros)
    assert primera.status_code == 200, primera.content
    datos = primera.json()
    refs = [t["ref"] for t in datos["resultados"]]
    for pagina in range(2, datos["paginas"] + 1):
        refs += ay.refs(buscar(pagina=str(pagina), **parametros))
    return refs


# --- Filtros excluyentes (RF-09) ---


@pytest.mark.regla("F-01")
def test_ca02_1_no_aparece_quien_no_declaro_la_comuna(catalogo):
    dentro = ay.maestro(1, catalogo)
    fuera = ay.maestro(2, catalogo, comunas=[(ay.CORONEL, True)])

    respuesta = buscar()

    assert respuesta.status_code == 200
    assert ay.refs(respuesta) == [ay.ref(dentro)]
    assert ay.ref(fuera) not in respuesta.content.decode()


@pytest.mark.regla("F-02", "F-08")
@pytest.mark.parametrize("estado", [EstadoExpediente.EN_REVISION, EstadoExpediente.OBSERVADO,
                                    EstadoExpediente.SUSPENDIDO, EstadoExpediente.RECHAZADO])
def test_ca02_2_no_aparece_si_el_expediente_no_esta_aprobado(catalogo, estado):
    ay.maestro(1, catalogo, estado=estado)
    respuesta = buscar()
    assert respuesta.json()["resultados"] == [] and respuesta.json()["total"] == 0


@pytest.mark.regla("F-08")
def test_sin_foto_no_aparece(catalogo):
    ay.maestro(1, catalogo, foto=False)
    assert buscar().json()["resultados"] == []


@pytest.mark.regla("F-06")
def test_rf06_sin_comuna_base_no_aparece(catalogo):
    ay.maestro(1, catalogo, comunas=[(ay.CONCEPCION, False), (ay.CORONEL, False)])
    assert buscar().json()["resultados"] == []
    assert buscar(comuna=str(ay.CORONEL)).json()["resultados"] == []


@pytest.mark.regla("F-03")
def test_ca02_3_con_filtro_de_bloque_no_aparece_quien_no_lo_declaro(catalogo):
    jueves = ay.maestro(1, catalogo, bloques=[(4, "08:00", "12:00")])
    ay.maestro(2, catalogo, bloques=[(3, "08:00", "20:00"), (5, "08:00", "12:00")])

    respuesta = con_bloque(ay.HOY + D(days=1), "09:00", "11:00")

    assert ay.refs(respuesta) == [ay.ref(jueves)]


@pytest.mark.regla("F-11")
def test_la_ocurrencia_debe_contener_el_rango_pedido(catalogo):
    usuario = ay.maestro(1, catalogo, bloques=[(4, "08:00", "10:00")])
    jueves = ay.HOY + D(days=1)
    assert ay.refs(con_bloque(jueves, "08:00", "10:00")) == [ay.ref(usuario)]
    assert ay.refs(con_bloque(jueves, "08:30", "09:30")) == [ay.ref(usuario)]
    assert ay.refs(con_bloque(jueves, "09:00", "11:00")) == []
    assert ay.refs(con_bloque(jueves, "07:30", "09:00")) == []


@pytest.mark.regla("F-09")
def test_rf16_un_bloque_que_empieza_en_cuatro_horas_o_menos_no_cuenta(catalogo):
    justo = ay.maestro(1, catalogo, bloques=[(3, "12:00", "14:00")])  # empieza en 4 h exactas
    holgado = ay.maestro(2, catalogo, bloques=[(3, "12:30", "14:00")])  # en 4 h 30 min

    assert ay.refs(con_bloque(ay.HOY, "12:30", "13:30")) == [ay.ref(holgado)]
    # Sin filtro de bloque, el de las 12:00 no tiene nada libre hoy: no suma los 60 de "hoy".
    candidatos = busqueda_servicios.cargar_candidatos(
        catalogo["pintura"].oficio, [ay.CONCEPCION], ay.AHORA, ay.HOY
    )
    ofrecibles = {c.maestro_id: c.ofrecibles for c in candidatos}
    assert all(u.fecha != ay.HOY for u in ofrecibles[justo.pk])
    assert any(u.fecha == ay.HOY for u in ofrecibles[holgado.pk])


@pytest.mark.regla("F-10")
def test_ca14_3_un_bloque_ocupado_no_cuenta_como_libre(catalogo, monkeypatch):
    ocupado = ay.maestro(1, catalogo, bloques=[(4, "08:00", "12:00")])
    libre = ay.maestro(2, catalogo, bloques=[(4, "08:00", "12:00")])
    jueves = ay.HOY + D(days=1)
    inicio = ocurrencias.instante(jueves, 600)

    def rangos(maestro_ids, desde, hasta):
        return {ocupado.pk: [(inicio, inicio + D(hours=1))]} if ocupado.pk in maestro_ids else {}

    monkeypatch.setattr(ocupacion, "rangos_ocupados", rangos)

    assert ay.refs(con_bloque(jueves, "08:00", "09:00")) == [ay.ref(libre)]
    # En la ficha el bloque aparece ocupado, sin ningún dato del ticket.
    bloques = Client().get(f"/api/maestros/publicos/{ay.ref(ocupado)}").json()["maestro"]["bloques"]
    del_jueves = [b for b in bloques if b["fecha"] == jueves.isoformat()]
    assert [b["estado"] for b in del_jueves] == ["ocupado"]
    assert set(del_jueves[0]) == {"fecha", "inicio", "fin", "ref", "estado"}


@pytest.mark.regla("F-04")
def test_ca02_4_todos_los_resultados_cumplen_las_tres_condiciones(catalogo):
    cumple = ay.maestro(1, catalogo, comunas=[(ay.CORONEL, True), (ay.CONCEPCION, False)],
                        bloques=[(4, "08:00", "12:00")])
    ay.maestro(2, catalogo, servicios=["gasfiteria"], bloques=[(4, "08:00", "12:00")])  # otro oficio
    ay.maestro(3, catalogo, comunas=[(ay.CORONEL, True)], bloques=[(4, "08:00", "12:00")])  # otra comuna
    ay.maestro(4, catalogo, bloques=[(5, "08:00", "12:00")])  # otro bloque

    respuesta = con_bloque(ay.HOY + D(days=1), "09:00", "11:00")

    assert ay.refs(respuesta) == [ay.ref(cumple)]
    assert respuesta.json()["total"] == 1


@pytest.mark.regla("F-05")
def test_ca13_2_al_quitar_una_comuna_deja_de_aparecer_en_ella(catalogo):
    usuario = ay.maestro(1, catalogo, comunas=[(ay.CORONEL, True), (ay.CONCEPCION, False)])
    assert ay.refs(buscar()) == [ay.ref(usuario)]

    cobertura.reemplazar_cobertura(usuario, [{"comuna": str(ay.CORONEL), "es_base": True}])

    assert ay.refs(buscar()) == []
    assert ay.refs(buscar(comuna=str(ay.CORONEL))) == [ay.ref(usuario)]


@pytest.mark.regla("F-07")
def test_ca24_4_sin_licencia_vigente_no_aparece_por_gas_pero_si_por_pintura(catalogo):
    usuario = ay.maestro(1, catalogo, servicios=["gas", "pintura"])
    assert ay.refs(buscar(oficio="gas")) == [ay.ref(usuario)]

    # Vence hoy (hora de Santiago): ya no está vigente (ADR-017, punto 4).
    Documento.objects.filter(expediente__perfil_maestro_id=usuario.pk).update(fecha_vencimiento=ay.HOY)

    assert ay.refs(buscar(oficio="gas")) == []
    assert ay.refs(buscar(oficio="pintura")) == [ay.ref(usuario)]


def _cumple_uno_a_uno(usuario, oficio, comuna, bloque):
    """La regla única aplicada a un solo maestro, con las funciones de a uno (sin la búsqueda)."""
    if not any(s.servicio.oficio.codigo == oficio for s in publicacion.servicios_visibles(usuario.pk, ay.HOY)):
        return False
    if comuna not in {c.comuna_id for c in cobertura.cobertura_de(usuario.pk)}:
        return False
    if bloque is None:
        return True
    fecha, inicio, fin = bloque
    for patron in agenda.bloques_activos(usuario.pk):
        una = ocurrencias.ocurrencia(patron.ref, patron.dia_semana, patron.inicio_min, patron.fin_min, fecha)
        if una and una.inicio_min <= inicio and una.fin_min >= fin and ocurrencias.ofrecible(una, ay.AHORA, ()):
            return True
    return False


@pytest.mark.regla("F-12", "F-04")
def test_propiedad_la_busqueda_coincide_con_la_regla_unica_maestro_por_maestro(catalogo):
    maestros = ay.escenario_aleatorio(catalogo, cantidad=30)
    bloques = [None, (ay.HOY, 750, 780), (ay.HOY + D(days=1), 540, 600), (ay.HOY + D(days=2), 0, 60),
               (ay.HOY + D(days=5), 1380, 1440), (ay.HOY + D(days=13), 600, 720)]
    comunas = [ay.CONCEPCION, ay.CORONEL, ay.HUALPEN, ay.LEBU]
    alguna_vez = 0
    for oficio, comuna, bloque in itertools.product(["pintura", "gas", "gasfiteria"], comunas, bloques):
        parametros = {"oficio": oficio, "comuna": str(comuna)}
        if bloque:
            parametros.update(fecha=bloque[0].isoformat(), inicio=agenda.formato_hora(bloque[1]),
                              fin=agenda.formato_hora(bloque[2]))
        obtenidos = set(todas_las_refs(**parametros))
        esperados = {ay.ref(m) for m in maestros if _cumple_uno_a_uno(m, oficio, comuna, bloque)}
        assert obtenidos == esperados, (oficio, comuna, bloque)
        alguna_vez += len(esperados)
    assert alguna_vez > 0


# --- Parámetros (ADR-022, punto 1; RNF-15) ---


@pytest.mark.regla("F-13")
@pytest.mark.parametrize(
    ("parametros", "campos"),
    [
        ({"oficio": None}, {"oficio"}),
        ({"comuna": None}, {"comuna"}),
        ({"oficio": "no-existe"}, {"oficio"}),
        ({"comuna": "99999"}, {"comuna"}),
        ({"comuna": "abc"}, {"comuna"}),
        ({"fecha": "2026-10-08"}, {"inicio", "fin"}),
        ({"inicio": "08:00", "fin": "10:00"}, {"fecha"}),
        ({"fecha": "2026-10-06", "inicio": "08:00", "fin": "10:00"}, {"fecha"}),  # ayer
        ({"fecha": "2026-10-21", "inicio": "08:00", "fin": "10:00"}, {"fecha"}),  # hoy+14
        ({"fecha": "2026-02-30", "inicio": "08:00", "fin": "10:00"}, {"fecha"}),
        ({"fecha": "8/10/2026", "inicio": "08:00", "fin": "10:00"}, {"fecha"}),
        ({"fecha": "2026-10-08", "inicio": "25:00", "fin": "10:00"}, {"inicio"}),
        ({"fecha": "2026-10-08", "inicio": "08:15", "fin": "10:00"}, {"inicio"}),
        ({"fecha": "2026-10-08", "inicio": "8am", "fin": "10:00"}, {"inicio"}),
        ({"fecha": "2026-10-08", "inicio": "10:00", "fin": "10:00"}, {"fin"}),
        ({"fecha": "2026-10-08", "inicio": "22:00", "fin": "02:00"}, {"fin"}),
        ({"fecha": "2026-10-08", "inicio": "24:00", "fin": "24:00"}, {"inicio"}),
        ({"pagina": "0"}, {"pagina"}),
        ({"pagina": "abc"}, {"pagina"}),
        ({"pagina": "-1"}, {"pagina"}),
    ],
)
def test_parametros_invalidos_responden_400_en_el_campo(catalogo, parametros, campos):
    respuesta = buscar(**parametros)
    assert respuesta.status_code == 400
    datos = respuesta.json()
    assert set(datos) == {"mensaje", "errores"}
    assert set(datos["errores"]) == campos
    assert respuesta["Cache-Control"] == "no-store"
    texto = respuesta.content.decode()
    assert not [t for t in TEXTO_PROHIBIDO if t in texto]


@pytest.mark.regla("F-13")
def test_parametro_desconocido_responde_400_general_sin_repetirlo(catalogo):
    respuesta = buscar(orden="puntaje")
    assert respuesta.status_code == 400
    assert respuesta.json() == {"mensaje": MENSAJE_CLAVE_DESCONOCIDA, "errores": {}}
    assert "orden" not in respuesta.content.decode() and "puntaje" not in respuesta.content.decode()


@pytest.mark.regla("F-13")
def test_parametro_repetido_responde_400_en_el_campo(catalogo):
    respuesta = Client().get(f"{URL}?oficio=pintura&oficio=gas&comuna={ay.CONCEPCION}")
    assert respuesta.status_code == 400 and set(respuesta.json()["errores"]) == {"oficio"}


def test_el_ultimo_dia_del_horizonte_se_acepta(catalogo):
    usuario = ay.maestro(1, catalogo, bloques=[(2, "08:00", "12:00")])  # martes
    assert ay.refs(con_bloque(ay.HOY + D(days=13), "08:00", "12:00")) == [ay.ref(usuario)]


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_la_busqueda_es_solo_de_lectura(catalogo, metodo):
    assert getattr(Client(), metodo)(URL).status_code == 405


def test_rnf15_rnf17_los_mensajes_nuevos_no_tienen_jerga(catalogo):
    textos = [
        busqueda_servicios.MENSAJE_OFICIO_FALTA, busqueda_servicios.MENSAJE_OFICIO_INVALIDO,
        busqueda_servicios.MENSAJE_COMUNA_FALTA, busqueda_servicios.MENSAJE_COMUNA_INVALIDA,
        busqueda_servicios.MENSAJE_BLOQUE_INCOMPLETO, busqueda_servicios.MENSAJE_FECHA_INVALIDA,
        busqueda_servicios.MENSAJE_FECHA_FUERA, busqueda_servicios.MENSAJE_FIN_NO_POSTERIOR,
        busqueda_servicios.MENSAJE_PAGINA_INVALIDA, busqueda_servicios.MENSAJE_TEXTO_INVALIDO,
        MENSAJE_SIN_RESULTADOS, SIN_EVALUACIONES, *sugerencias.TEXTOS.values(),
    ]
    prohibidas = ["parámetro", "param", "query", "null", "None", "id ", "ref", "UUID", "HTTP", "400", "ticket",
                  "puntaje", "score", "filtro", "error", "inválid", "campo"]
    for texto in textos:
        assert texto.strip() and texto[0].isupper(), texto
        assert not [p for p in prohibidas if p.lower() in texto.lower()], texto
        assert not [t for t in TEXTO_PROHIBIDO if t in texto], texto


# --- Puntaje y orden (RF-10, RF-11) ---


@pytest.mark.regla("P-01", "P-02", "P-03", "P-04", "P-07")
def test_escala_de_disponibilidad():
    hoy = ay.HOY
    assert puntaje.disponibilidad(set(), hoy, con_bloque=True) == 100
    assert puntaje.disponibilidad({hoy}, hoy, con_bloque=False) == 60
    for dias in (1, 2, 3):
        assert puntaje.disponibilidad({hoy + D(days=dias)}, hoy, con_bloque=False) == 30
    # CA-03.4: el horizonte sin filtro son los próximos tres días; hoy+4 ya no cuenta.
    assert puntaje.disponibilidad({hoy + D(days=4), hoy + D(days=10)}, hoy, con_bloque=False) == 0
    assert puntaje.disponibilidad(set(), hoy, con_bloque=False) == 0


@pytest.mark.regla("P-05", "P-06")
def test_cercania_y_ejemplo_literal_del_informe():
    assert puntaje.cercania(True) == 100 and puntaje.cercania(False) == 60
    assert puntaje.cercania(False, en_cobertura=False) == 0
    # §3.3.2: "obtiene 60 puntos, mientras uno de la comuna base [...] obtiene 58".
    assert puntaje.puntaje(60, 60) / 10 == 60
    assert puntaje.puntaje(30, 100) / 10 == 58
    assert puntaje.puntaje(100, 100) == 1000


@pytest.mark.regla("P-06", "P-02", "P-03", "P-05", "P-08")
def test_ca03_2_libre_hoy_en_comuna_secundaria_va_antes_que_la_base_en_tres_dias(catalogo):
    secundaria_hoy = ay.maestro(1, catalogo, comunas=[(ay.CORONEL, True), (ay.CONCEPCION, False)],
                                bloques=[(3, "14:00", "18:00")])
    base_en_dos_dias = ay.maestro(2, catalogo, comunas=[(ay.CONCEPCION, True)], bloques=[(5, "14:00", "18:00")])

    assert ay.refs(buscar()) == [ay.ref(secundaria_hoy), ay.ref(base_en_dos_dias)]


@pytest.mark.regla("P-04", "P-07", "P-08")
def test_sin_nada_en_tres_dias_vale_cero_aunque_sea_su_comuna_base(catalogo):
    # 6·0 + 4·100 = 400 contra 6·30 + 4·60 = 420.
    base_sin_nada = ay.maestro(1, catalogo, comunas=[(ay.CONCEPCION, True)], bloques=[(7, "08:00", "12:00")])
    secundaria_sabado = ay.maestro(2, catalogo, comunas=[(ay.CORONEL, True), (ay.CONCEPCION, False)],
                                   bloques=[(6, "08:00", "12:00")])
    assert ay.refs(buscar()) == [ay.ref(secundaria_sabado), ay.ref(base_sin_nada)]


@pytest.mark.regla("P-01", "P-05", "P-08")
def test_con_filtro_de_bloque_ordena_por_cercania(catalogo):
    secundaria = ay.maestro(1, catalogo, comunas=[(ay.CORONEL, True), (ay.CONCEPCION, False)],
                            bloques=[(3, "14:00", "18:00"), (4, "08:00", "12:00")])
    base = ay.maestro(2, catalogo, comunas=[(ay.CONCEPCION, True)], bloques=[(4, "08:00", "12:00")])
    # Sin filtro: el de hoy va primero (600 contra 580).
    assert ay.refs(buscar()) == [ay.ref(secundaria), ay.ref(base)]
    # Con el bloque del jueves los dos valen 100 en disponibilidad: decide la cercanía.
    assert ay.refs(con_bloque(ay.HOY + D(days=1), "09:00", "11:00")) == [ay.ref(base), ay.ref(secundaria)]


@pytest.mark.regla("P-09")
def test_ca03_3_desempate_por_calificacion_y_luego_cantidad():
    hoy = ay.HOY
    claves = {
        "sin_evaluaciones": puntaje.clave_orden(600, None, 0, "a", hoy),
        "4.5_con_2": puntaje.clave_orden(600, 4.5, 2, "b", hoy),
        "4.5_con_9": puntaje.clave_orden(600, 4.5, 9, "c", hoy),
        "4.9_con_1": puntaje.clave_orden(600, 4.9, 1, "d", hoy),
        "mas_puntaje": puntaje.clave_orden(640, None, 0, "e", hoy),
    }
    orden = sorted(claves, key=claves.get)
    assert orden == ["mas_puntaje", "4.9_con_1", "4.5_con_9", "4.5_con_2", "sin_evaluaciones"]


@pytest.mark.regla("P-10")
def test_desempate_final_por_sorteo_diario_determinista(catalogo):
    maestros = [ay.maestro(n, catalogo) for n in range(1, 5)]
    esperado = sorted((ay.ref(m) for m in maestros), key=lambda r: puntaje.sorteo(r, ay.HOY))
    assert ay.refs(buscar()) == esperado
    assert ay.refs(buscar()) == esperado  # estable dentro del día
    assert puntaje.sorteo("x", ay.HOY) != puntaje.sorteo("x", ay.HOY + D(days=1))


# --- Respuesta: tarjeta, privacidad, caché y páginas ---


def test_rf13_tarjeta_con_lista_explicita_de_campos(catalogo):
    usuario = ay.maestro(1, catalogo, nombre="Rosa Ficticia")
    respuesta = buscar()

    assert respuesta.status_code == 200
    assert respuesta["Cache-Control"] == "no-store"
    datos = respuesta.json()
    assert set(datos) == {"resultados", "total", "pagina", "paginas", "mensaje", "sugerencias"}
    assert datos["mensaje"] is None and datos["sugerencias"] == []
    ref = ay.ref(usuario)
    assert datos["resultados"] == [{
        "ref": ref,
        "nombre": "Rosa Ficticia",
        "foto": f"/api/maestros/publicos/{ref}/foto?tam=160",
        "oficio": {"codigo": "pintura", "nombre": "Pintura"},
        "calificacion": None,
        "calificacion_texto": "Todavía no tiene evaluaciones",
    }]


@pytest.mark.regla("P-11")
def test_el_puntaje_la_comuna_base_y_los_datos_personales_no_van_en_la_respuesta(catalogo):
    usuario = ay.maestro(1, catalogo, comunas=[(ay.CORONEL, True), (ay.CONCEPCION, False)])
    expediente = Expediente.objects.get(perfil_maestro_id=usuario.pk)
    for respuesta in (buscar(), buscar(comuna=str(ay.CORONEL)), con_bloque(ay.HOY, "14:00", "15:00"),
                      buscar(comuna=str(ay.HUALPEN))):
        assert respuesta.status_code == 200
        assert_campos_ausentes(
            respuesta,
            {"puntaje", "score", "disponibilidad", "cercania", "es_base", "base", "comuna_base", "principal",
             "comunas", "rut", "telefono", "correo", "id", "perfil_maestro_id", "expediente", "estado", "monto"},
            valores=[usuario.perfil_maestro.rut, "910000001", str(expediente.ref), "Coronel"],
        )


def test_paginas_de_veinte_y_consultas_constantes(catalogo, django_assert_max_num_queries):
    """RNF-01: el número de consultas no crece con los maestros (5 contra 50)."""
    for n in range(1, 6):
        ay.maestro(n, catalogo)
    with CaptureQueriesContext(connection) as con_cinco:
        assert buscar().json()["total"] == 5
    for n in range(6, 51):
        ay.maestro(n, catalogo)
    with django_assert_max_num_queries(len(con_cinco.captured_queries)):
        primera = buscar().json()
    print("consultas por búsqueda:", len(con_cinco.captured_queries))
    # 14: la consulta de rangos ocupados sobre ``ticket`` se suma desde el incremento 4 (ADR-023, punto 4).
    # 15: la calificación en lote sobre ``evaluacion`` (S5, incremento 5; una sola consulta, sin N+1).
    assert len(con_cinco.captured_queries) <= 15
    assert primera["total"] == 50 and primera["paginas"] == 3 and len(primera["resultados"]) == 20
    tercera = buscar(pagina="3").json()
    assert len(tercera["resultados"]) == 10
    todas = todas_las_refs()
    assert len(todas) == len(set(todas)) == 50
    assert buscar(pagina="4").json()["resultados"] == []


# --- Resultado vacío y sugerencias (CA-04.1 a CA-04.3, RF-12) ---


def test_ca04_1_mensaje_explicito_sin_resultados_ni_sugerencias(catalogo):
    respuesta = buscar()
    datos = respuesta.json()
    assert datos["resultados"] == [] and datos["total"] == 0
    assert datos["mensaje"] == MENSAJE_SIN_RESULTADOS
    assert datos["sugerencias"] == []


def test_ca04_2_ca04_3_sugerencias_separadas_con_el_criterio_que_incumplen(catalogo):
    otro_horario = ay.maestro(1, catalogo, bloques=[(5, "08:00", "12:00")])
    otra_comuna = ay.maestro(2, catalogo, comunas=[(ay.CORONEL, True)], bloques=[(4, "08:00", "12:00")])
    ay.maestro(3, catalogo, comunas=[(ay.LEBU, True)], bloques=[(4, "08:00", "12:00")])  # otra provincia
    ay.maestro(4, catalogo, servicios=["gasfiteria"], bloques=[(4, "08:00", "12:00")])  # otro oficio
    ay.maestro(5, catalogo, estado=EstadoExpediente.SUSPENDIDO, bloques=[(4, "08:00", "12:00")])  # no publicado

    respuesta = con_bloque(ay.HOY + D(days=1), "09:00", "11:00")

    datos = respuesta.json()
    assert datos["resultados"] == [] and datos["mensaje"] == MENSAJE_SIN_RESULTADOS
    assert [(s["ref"], s["incumple"]) for s in datos["sugerencias"]] == [
        (ay.ref(otro_horario), "bloque"), (ay.ref(otra_comuna), "comuna"),
    ]
    for sugerencia in datos["sugerencias"]:
        assert sugerencia["incumple_texto"] == sugerencias.TEXTOS[sugerencia["incumple"]]
        assert set(sugerencia) == {"ref", "nombre", "foto", "oficio", "calificacion", "calificacion_texto",
                                   "incumple", "incumple_texto"}


def test_sugerencias_como_maximo_cinco_y_nunca_con_resultados(catalogo):
    for n in range(1, 8):
        ay.maestro(n, catalogo, bloques=[(5, "08:00", "12:00")])
    sin_resultados = con_bloque(ay.HOY + D(days=1), "09:00", "11:00").json()
    assert len(sin_resultados["sugerencias"]) == sugerencias.MAXIMO
    assert {s["incumple"] for s in sin_resultados["sugerencias"]} == {"bloque"}

    con_resultados = con_bloque(ay.HOY + D(days=2), "09:00", "11:00").json()
    assert con_resultados["total"] == 7 and con_resultados["sugerencias"] == []


def test_sin_filtro_de_bloque_solo_se_sugiere_otra_comuna(catalogo):
    vecino = ay.maestro(1, catalogo, comunas=[(ay.HUALPEN, True)])
    datos = buscar().json()
    assert [(s["ref"], s["incumple"]) for s in datos["sugerencias"]] == [(ay.ref(vecino), "comuna")]


# --- Ficha con bloques (RF-14; ADR-022, punto 4) ---


def test_la_ficha_muestra_los_bloques_de_catorce_dias(catalogo):
    usuario = ay.maestro(1, catalogo, bloques=[(3, "12:00", "14:00"), (3, "14:00", "18:00"), (6, "20:00", "24:00")])
    patrones = {(p.inicio_min, p.dia_semana): str(p.ref) for p in agenda.bloques_activos(usuario.pk)}

    respuesta = Client().get(f"/api/maestros/publicos/{ay.ref(usuario)}")

    assert respuesta["Cache-Control"] == "no-store"
    bloques = respuesta.json()["maestro"]["bloques"]
    # Hoy 12:00 empieza en 4 horas exactas: se omite. El horizonte llega al martes 20 (hoy+13).
    assert [(b["fecha"], b["inicio"], b["fin"], b["estado"]) for b in bloques] == [
        ("2026-10-07", "14:00", "18:00", "libre"),
        ("2026-10-10", "20:00", "24:00", "libre"),
        ("2026-10-14", "12:00", "14:00", "libre"),
        ("2026-10-14", "14:00", "18:00", "libre"),
        ("2026-10-17", "20:00", "24:00", "libre"),
    ]
    assert bloques[0]["ref"] == patrones[(840, 3)]
    servicio = respuesta.json()["maestro"]["servicios"][0]
    assert servicio["ref"] == str(catalogo["pintura"].ref)
