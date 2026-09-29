"""Medición de RNF-01 sobre una pila local cargada con el volumen de prueba (propuesta del S4, §7; ADR-022, punto 8).

RNF-01: "Al menos 19 de cada 20 búsquedas responden en 2 segundos o menos,
con 100 maestros, 1.000 tickets y 10 personas usando el sistema a la vez".
Se revisan **todos** los tiempos, no el promedio (informe §4.3.2).

Sin dependencias (solo la biblioteca estándar). Uso, contra la pila aparte::

    python scripts/medir_rnf01.py --base https://localhost:8443 --hilos 10 --busquedas 200

Si el equipo no tiene Python (Windows), desde la imagen de la app::

    docker run --rm -v "$PWD/scripts:/s:ro" --entrypoint python altiro-app:local /s/medir_rnf01.py \
        --base https://host.docker.internal:8443 --cabecera-host localhost:8443

- 10 hilos simultáneos; al menos 200 búsquedas variadas (oficio, comuna del
  Gran Concepción, con y sin bloque horario, páginas 1 y 2), generadas con
  una semilla fija.
- Informa la proporción que respondió en 2 s o menos, el p95, la mediana y el
  máximo, y cuántas respuestas no fueron 200.
- **TLS sin verificar solo para la demostración local**: el certificado es
  autofirmado (ADR-008). No usar este script contra otro servidor.
"""
import argparse
import datetime
import json
import random
import ssl
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OFICIOS = ["gasfiteria", "carpinteria", "pintura", "albanileria", "cerrajeria", "jardineria"]
COMUNAS = [8101, 8102, 8103, 8104, 8105, 8106, 8107, 8108, 8109, 8110, 8111, 8112]
UMBRAL_SEGUNDOS = 2.0
# host.docker.internal: cuando el script corre en un contenedor del mismo equipo (Windows sin Python).
LOCALES = {"localhost", "127.0.0.1", "host.docker.internal"}


def consultas(cantidad, semilla):
    azar = random.Random(semilla)
    hoy = datetime.date.today()
    lista = []
    for _ in range(cantidad):
        parametros = {"oficio": azar.choice(OFICIOS), "comuna": str(azar.choice(COMUNAS))}
        if azar.random() < 0.5:
            inicio = azar.randint(16, 36) * 30
            parametros.update(
                fecha=(hoy + datetime.timedelta(days=azar.randint(1, 13))).isoformat(),
                inicio=f"{inicio // 60:02d}:{inicio % 60:02d}",
                fin=f"{(inicio + 60) // 60:02d}:{(inicio + 60) % 60:02d}",
            )
        if azar.random() < 0.1:
            parametros["pagina"] = "2"
        lista.append(urllib.parse.urlencode(parametros))
    return lista


def medir(base, consulta, contexto, cabecera_host=None):
    inicio = time.perf_counter()
    try:
        peticion = urllib.request.Request(f"{base}/api/busqueda?{consulta}")
        if cabecera_host:
            peticion.add_header("Host", cabecera_host)
        with urllib.request.urlopen(peticion, context=contexto, timeout=30) as respuesta:
            cuerpo = respuesta.read()
            estado = respuesta.status
            json.loads(cuerpo)
    except urllib.error.HTTPError as error:
        estado = error.code
    except (urllib.error.URLError, TimeoutError, ValueError):
        estado = 0
    return time.perf_counter() - inicio, estado


def percentil(valores, p):
    ordenados = sorted(valores)
    indice = max(0, min(len(ordenados) - 1, int(round(p / 100 * len(ordenados) + 0.5)) - 1))
    return ordenados[indice]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="https://localhost:8443")
    parser.add_argument("--hilos", type=int, default=10)
    parser.add_argument("--busquedas", type=int, default=200)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--calentamiento", type=int, default=10)
    parser.add_argument("--cabecera-host", default=None, help="Host a enviar (p. ej. localhost:8443) si se usa host.docker.internal.")
    argumentos = parser.parse_args()
    if urllib.parse.urlsplit(argumentos.base).hostname not in LOCALES:
        sys.exit("Solo se mide contra la pila local (localhost o 127.0.0.1).")
    # Certificado autofirmado de la demostración local (ADR-008): no se verifica.
    contexto = ssl._create_unverified_context()  # noqa: S323 (solo pila local)

    for consulta in consultas(argumentos.calentamiento, argumentos.semilla + 1):
        medir(argumentos.base, consulta, contexto, argumentos.cabecera_host)

    lista = consultas(argumentos.busquedas, argumentos.semilla)
    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=argumentos.hilos) as grupo:
        resultados = list(grupo.map(lambda c: medir(argumentos.base, c, contexto, argumentos.cabecera_host), lista))
    total = time.perf_counter() - inicio

    tiempos = [t for t, _ in resultados]
    no_200 = sum(1 for _, estado in resultados if estado != 200)
    dentro = sum(1 for t, estado in resultados if t <= UMBRAL_SEGUNDOS and estado == 200)
    proporcion = dentro / len(resultados)
    informe = {
        "busquedas": len(resultados),
        "hilos": argumentos.hilos,
        "respuestas_no_200": no_200,
        "proporcion_en_2s_o_menos": round(proporcion, 4),
        "p95_s": round(percentil(tiempos, 95), 3),
        "mediana_s": round(statistics.median(tiempos), 3),
        "maximo_s": round(max(tiempos), 3),
        "duracion_total_s": round(total, 1),
        "cumple_rnf01": proporcion >= 19 / 20 and no_200 == 0,
    }
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0 if informe["cumple_rnf01"] else 1


if __name__ == "__main__":
    sys.exit(main())
