import http.client, ssl, json, re, datetime
CTX = ssl._create_unverified_context(); ck = {}
def req(m, path, body=None):
    h = http.client.HTTPSConnection("proxy", 443, context=CTX)
    hd = {"Host": "localhost", "Content-Type": "application/json", "Origin": "https://localhost", "Referer": "https://localhost/", "Cookie": "; ".join(f"{k}={v}" for k, v in ck.items())}
    if m != "GET" and "csrftoken" in ck: hd["X-CSRFToken"] = ck["csrftoken"]
    h.request(m, path, json.dumps(body) if body is not None else None, hd); r = h.getresponse(); raw = r.read().decode("utf8", "replace")
    for v in r.headers.get_all("Set-Cookie") or []:
        k, _, rest = v.partition("="); ck[k] = rest.split(";")[0]
    return r.status, raw
req("GET", "/api/sesion/csrf"); print(req("POST", "/api/sesion", {"identificador": "qa.s5.ges.vol@example.com", "contrasena": "clave de prueba segura"})[0]); req("GET", "/api/sesion/csrf")
hoy = datetime.date.today(); q = f"?desde={(hoy - datetime.timedelta(days=365)).isoformat()}&hasta={hoy.isoformat()}"
st, raw = req("GET", "/api/gestion/exportacion" + q); print("EXPORT", st, len(raw), "filas", len(raw.splitlines()) - 1)
pat = {"correo": r"[\w.+-]+@[\w-]+\.\w+", "rut": r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b", "telefono": r"\+?56\s?9[\s\d]{8,}", "uuid": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", "nombres": r"Maestro|Cliente|Prueba|Pasaje|Calle"}
print({k: len(re.findall(v, raw)) for k, v in pat.items()})
ls = raw.lstrip("﻿").splitlines(); print(ls[0]); print("\n".join(ls[1:6]))
cols = ls[0].split(","); print("columnas", cols)
bajo = [l for l in ls[1:] if int(l.split(",")[4]) < 5]; print("filas con tickets_enviados<5:", len(bajo))
st, raw = req("GET", "/api/gestion/indicadores" + q); print("INDICADORES", st, raw[:300])
fin = [int(l.split(",")[5]) for l in ls[1:]]
print("filas:", len(fin), "finalizadas<5:", sum(1 for x in fin if x < 5), "finalizadas==1:", sum(1 for x in fin if x == 1), "finalizadas==0:", sum(1 for x in fin if x == 0))
print([l for l in ls[1:] if int(l.split(",")[5]) == 1][:3])
bajo = [l for l in ls[1:] if int(l.split(",")[5]) < 5]
print("filas con finalizadas<5:", len(bajo), "con mediana publicada:", [l for l in bajo if l.split(",")[6] != ""][:3])
print("ejemplo suprimida:", bajo[:2])
