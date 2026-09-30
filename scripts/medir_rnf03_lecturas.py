"""Lecturas con el volumen completo (S5 inc. 8, RNF-03): conversación y ficha pública, 10 hilos.

Uso (desde la imagen de la app, igual que ``medir_rnf01.py``)::

    python medir_rnf03_lecturas.py --base https://host.docker.internal:8443 --cabecera-host localhost \
        --sesion <sessionid> --ticket <ref> --maestro <ref público>

``--sesion`` es la clave de una sesión ya creada en la base de la pila aparte (cuentas ficticias sin contraseña).
TLS sin verificar solo por el certificado autofirmado local (ADR-008).
"""
import argparse, json, ssl, statistics, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

a = argparse.ArgumentParser()
a.add_argument("--base", required=True); a.add_argument("--cabecera-host", default="localhost")
a.add_argument("--sesion", required=True); a.add_argument("--ticket", required=True); a.add_argument("--maestro", required=True)
a.add_argument("--hilos", type=int, default=10); a.add_argument("--n", type=int, default=200)
o = a.parse_args()
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE


def leer(ruta):
    r = urllib.request.Request(o.base + ruta, headers={"Host": o.cabecera_host, "Cookie": f"sessionid={o.sesion}"})
    t = time.perf_counter()
    with urllib.request.urlopen(r, context=ctx) as x:
        cuerpo = x.read()
        return time.perf_counter() - t, x.status, len(cuerpo)


for nombre, ruta in (("GET mensajes", f"/api/tickets/{o.ticket}/mensajes"), ("ficha pública", f"/api/maestros/publicos/{o.maestro}")):
    leer(ruta)
    with ThreadPoolExecutor(o.hilos) as p:
        res = list(p.map(lambda _: leer(ruta), range(o.n)))
    t = sorted(r[0] for r in res)
    print(json.dumps({"lectura": nombre, "n": o.n, "no_200": sum(r[1] != 200 for r in res), "bytes": res[0][2],
                      "p95_s": round(t[int(len(t) * .95) - 1], 3), "mediana_s": round(statistics.median(t), 3),
                      "maximo_s": round(t[-1], 3), "en_2s": sum(x <= 2 for x in t) / len(t)}))
