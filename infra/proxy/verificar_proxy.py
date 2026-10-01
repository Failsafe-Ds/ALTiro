"""Verificación del proxy contra la pila local (ADR-029; hallazgos B-1, B-2, B-3).

No forma parte de pytest: las pruebas corren dentro de "app", que no ve la
configuración de Nginx. Se ejecuta desde el equipo anfitrión con la pila arriba:

    python infra/proxy/verificar_proxy.py [--https-port 443] [--http-port 80]

Solo usa la biblioteca estándar. La ráfaga estricta envía POST a /api/sesion
sin token CSRF: la app responde 403 antes de la vista (sin efectos y sin
contar para el limitador de ADR-007, que solo cuenta 401). Deja la zona
estricta agotada unos segundos para esa IP.
Devuelve 0 si todo cumple.
"""
import argparse
import collections
import http.client
import json
import ssl
import sys
import threading
import time

CABECERAS = {
    "content-security-policy": None,
    "x-content-type-options": "nosniff",
    "referrer-policy": "same-origin",
    "permissions-policy": None,
    "cross-origin-opener-policy": "same-origin",
}
CTX = ssl._create_unverified_context()  # certificado autofirmado local (ADR-008)
fallas = []


def revisar(condicion, texto):
    print(("OK    " if condicion else "FALLA ") + texto)
    if not condicion:
        fallas.append(texto)


def pedir(puerto, metodo, ruta, host="localhost", cuerpo=None, tls=True, cabeceras=None):
    clase = http.client.HTTPSConnection if tls else http.client.HTTPConnection
    argumentos = {"context": CTX} if tls else {}
    con = clase("127.0.0.1", puerto, timeout=10, **argumentos)
    extra = {"Host": host, "Accept": "application/json", "Content-Type": "application/json"}
    extra.update(cabeceras or {})
    con.request(metodo, ruta, body=cuerpo, headers=extra)
    respuesta = con.getresponse()
    datos = respuesta.read()
    con.close()
    return respuesta, datos


def cabeceras_de_seguridad(puerto):
    for ruta, cache in (("/", "no-cache"), ("/index.html", "no-cache"), ("/js/api.js", "no-cache"),
                        ("/css/base.css", "no-cache"), ("/api/oficios", None), ("/no-existe.html", "no-store")):
        respuesta, _ = pedir(puerto, "GET", ruta)
        for nombre, valor in CABECERAS.items():
            obtenido = respuesta.getheader(nombre)
            revisar(obtenido is not None and (valor is None or obtenido == valor), f"{ruta}: {nombre}")
        if cache:
            revisar(respuesta.getheader("cache-control") == cache, f"{ruta}: Cache-Control {cache}")
    respuesta, _ = pedir(puerto, "GET", "/js/api.js")
    etag = respuesta.getheader("etag")
    respuesta, _ = pedir(puerto, "GET", "/js/api.js", cabeceras={"If-None-Match": etag or ""})
    revisar(respuesta.status == 304, "/js/api.js revalida con ETag (304)")


def redireccion(puerto_http):
    for host, esperado in (("localhost", "localhost"), ("127.0.0.1", "127.0.0.1"),
                           ("192.168.1.20", "192.168.1.20"), ("otro.example", "localhost")):
        respuesta, _ = pedir(puerto_http, "GET", "/x?y=1", host=host, tls=False)
        destino = respuesta.getheader("location") or ""
        revisar(destino.startswith(f"https://{esperado}:"), f"http Host {host} -> {destino}")


def rafaga(puerto, metodo, ruta, total, hilos, cuerpo=None):
    cuenta = collections.Counter()
    muestra = {}
    candado = threading.Lock()
    restantes = [total]

    def trabajar():
        con = http.client.HTTPSConnection("127.0.0.1", puerto, context=CTX, timeout=10)
        while True:
            with candado:
                if restantes[0] == 0:
                    break
                restantes[0] -= 1
            con.request(metodo, ruta, body=cuerpo,
                        headers={"Host": "localhost", "Accept": "application/json",
                                 "Content-Type": "application/json"})
            respuesta = con.getresponse()
            datos = respuesta.read()
            with candado:
                cuenta[respuesta.status] += 1
                if respuesta.status == 429 and not muestra:
                    muestra.update(tipo=respuesta.getheader("content-type"),
                                   retry=respuesta.getheader("retry-after"), cuerpo=datos)
        con.close()

    ts = [threading.Thread(target=trabajar) for _ in range(hilos)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return cuenta, muestra


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--https-port", type=int, default=443)
    parser.add_argument("--http-port", type=int, default=80)
    a = parser.parse_args()

    cabeceras_de_seguridad(a.https_port)
    redireccion(a.http_port)

    cuenta, _ = rafaga(a.https_port, "GET", "/api/oficios", 60, 10)
    revisar(set(cuenta) == {200}, f"uso normal (60 GET, 10 hilos) sin 429: {dict(cuenta)}")

    cuenta, muestra = rafaga(a.https_port, "POST", "/api/sesion", 45, 5, cuerpo=b"{}")
    revisar(cuenta[429] > 0, f"ráfaga estricta en POST /api/sesion recibe 429: {dict(cuenta)}")
    if muestra:
        cuerpo = json.loads(muestra["cuerpo"].decode("utf-8"))
        revisar(muestra["tipo"] == "application/json" and set(cuerpo) == {"mensaje", "errores"},
                "429 en JSON con el formato común")
        revisar(muestra["retry"] == "30", "429 con Retry-After")
        print("      mensaje:", cuerpo["mensaje"])

    time.sleep(1)
    respuesta, _ = pedir(a.https_port, "GET", "/api/oficios")
    revisar(respuesta.status == 200, "la zona estricta no afecta a las demás rutas")

    print(f"\n{len(fallas)} fallas")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
