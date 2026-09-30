"""QA S5: sondeos de acceso ajeno contra https://localhost (TLS autofirmado). Uso: python seguridad2.py datos.json datos2.json export.csv"""
import http.client, ssl, json, sys, datetime, re
D = json.load(open(sys.argv[1])); CTX = ssl._create_unverified_context(); PWD = D["pwd"]


class C:
    def __init__(s): s.ck = {}

    def req(s, m, path, body=None):
        h = http.client.HTTPSConnection("127.0.0.1", 443, context=CTX, timeout=40)
        hd = {"Host": "localhost", "Content-Type": "application/json", "Origin": "https://localhost", "Referer": "https://localhost/",
              "Cookie": "; ".join(f"{k}={v}" for k, v in s.ck.items())}
        if m != "GET" and "csrftoken" in s.ck: hd["X-CSRFToken"] = s.ck["csrftoken"]
        h.request(m, path, json.dumps(body) if body is not None else None, hd)
        r = h.getresponse(); raw = r.read().decode("utf8", "replace")
        for v in r.headers.get_all("Set-Cookie") or []:
            k, _, rest = v.partition("="); s.ck[k] = rest.split(";")[0]
        try: d = json.loads(raw)
        except Exception: d = raw
        return r.status, d, raw, r.headers

    def login(s, ident):
        s.req("GET", "/api/sesion/csrf")
        st, d, _, _ = s.req("POST", "/api/sesion", {"identificador": ident, "contrasena": PWD}); assert st == 200, (ident, st, d)
        s.req("GET", "/api/sesion/csrf")


def p(*a): print(*a, flush=True)



D2 = json.load(open(sys.argv[2]))
sys.stdout.reconfigure(encoding="utf-8")
anon = C(); A = C(); B = C(); M1 = C(); M2 = C(); GES = C()
for c, i in ((A, D["A"]), (B, D["B"]), (M1, D["M1"]), (M2, D["M2"]), (GES, D["GES"])): c.login(i)
def T(r): return f"/api/tickets/{r}"
def E(d): return (d.get("ticket", d) or {}) if isinstance(d, dict) else {}
# privacidad de la bandeja completa (historial) para el maestro: pendiente y cerrado sin datos del cliente
st, d, raw, _ = M1.req("GET", "/api/maestros/tickets")
for t in d["tickets"]:
    if t["estado"] in ("pendiente", "cerrado"):
        txt = json.dumps(t, ensure_ascii=False)
        f = [x for x in ("Pasaje Ficticio", "depto 45", "10000103", "1000 0103", "Cliente QA S5", "qa.s5.a") if x in txt]
        if f: p("FUGA historial maestro", t["estado"], t["ref"][:8], f)
p("HISTORIAL maestro revisado:", len(d["tickets"]), "tickets; estados:", sorted({t["estado"] for t in d["tickets"]}))
# precio por trabajo distinto
R = D2["precio"]
st, d, raw, _ = M1.req("POST", T(R) + "/precio-final", {"monto": 30000}); p("P1 por trabajo 30000 vs 25000:", st, E(d).get("estado"), E(d).get("precio"))
for n, c in (("B", B), ("M2", M2)):
    st, d, raw, _ = c.req("POST", T(R) + "/precio-final/aceptacion", {"monto": 30000}); p("P1 aceptar por", n, st)
st, d, raw, _ = A.req("POST", T(R) + "/precio-final/objecion", {}); p("P1 cliente objeta:", st, E(d).get("estado"), E(d).get("precio"))
st, d, raw, _ = M1.req("POST", T(R) + "/precio-final", {"monto": 30000}); p("P1 re-registra:", st, E(d).get("precio"))
st, d, raw, _ = A.req("POST", T(R) + "/precio-final/aceptacion", {"monto": 29000}); p("P1 acepta monto distinto (409):", st, raw[:110])
st, d, raw, _ = A.req("POST", T(R) + "/precio-final/aceptacion", {"monto": 30000}); p("P1 acepta:", st, E(d).get("estado"), E(d).get("precio"))
st, d, raw, _ = A.req("POST", T(R) + "/precio-final/aceptacion", {"monto": 30000}); p("P1 repetir aceptación (200 idempotente):", st)
st, d, raw, _ = M1.req("POST", T(R) + "/precio-final", {"monto": 31000}); p("P1 cambiar tras finalizar (409):", st, raw[:100])
st, d, raw, _ = A.req("POST", T(R) + "/precio-final/objecion", {}); p("P1 objetar tras finalizar (409):", st)
ha = [x for x in A.req("GET", "/api/clientes/tickets")[1]["tickets"] if x["ref"] == R][0]; hm = [x for x in M1.req("GET", "/api/maestros/tickets")[1]["tickets"] if x["ref"] == R][0]
p("P1 historial cliente vs maestro mismo precio (CA-16.3):", ha["precio"] == hm["precio"], ha["precio"], "| estado:", ha["estado"], hm["estado"])
# por hora
R = D2["hora"]
st, d, raw, _ = M1.req("POST", T(R) + "/precio-final", {"monto": 12000}); p("P2 por hora, monto igual al publicado:", st, E(d).get("estado"), (E(d).get("precio") or {}).get("estado"))
st, d, raw, _ = A.req("POST", T(R) + "/precio-final/aceptacion", {"monto": 12000}); p("P2 cliente acepta:", st, E(d).get("estado"))
# por trabajo igual
R = D2["igual"]
st, d, raw, _ = M1.req("POST", T(R) + "/precio-final", {"monto": 25000}); p("P3 por trabajo igual (finaliza sin aceptación):", st, E(d).get("estado"), (E(d).get("precio") or {}).get("estado"))
# mensajes en aceptado futuro
R = D2["msgs"]
st, d, raw, _ = M1.req("POST", T(R) + "/precio-final", {"monto": 25000}); p("P4 precio antes del inicio del bloque (409, P-27):", st, raw[:100])
k = "44444444-4444-4444-8444-444444444444"
st, d, raw, _ = A.req("POST", T(R) + "/mensajes", {"texto": "Hola, ¿a qué hora llegas?", "clave_envio": k}); m1 = d.get("mensaje") if isinstance(d, dict) else None; p("M1 cliente envía:", st, json.dumps(d, ensure_ascii=False)[:200])
st, d2, raw, _ = A.req("POST", T(R) + "/mensajes", {"texto": "Hola, ¿a qué hora llegas?", "clave_envio": k}); p("M2 reenvío misma clave (200, mismo mensaje):", st, d2 == d)
st, d, raw, _ = M1.req("POST", T(R) + "/mensajes", {"texto": "A las 8 en punto", "clave_envio": "55555555-5555-4555-8555-555555555555"}); p("M3 maestro responde:", st)
st, d, raw, _ = M1.req("GET", T(R) + "/mensajes"); p("M4 maestro lee:", st, [(x["autor"], x["texto"][:20]) for x in d["mensajes"]])
st, d, raw, _ = A.req("GET", T(R) + "/mensajes"); p("M4 cliente lee:", st, [(x["autor"]) for x in d["mensajes"]], "claves mensaje:", sorted(d["mensajes"][0].keys()))
st, d, raw, _ = A.req("GET", T(R) + "/mensajes?despues=" + d["mensajes"][0]["ref"]); p("M5 incremental:", st, len(d["mensajes"]))
for mal in ("", "   ", "x" * 1001):
    st, d, raw, _ = A.req("POST", T(R) + "/mensajes", {"texto": mal, "clave_envio": "66666666-6666-4666-8666-666666666666"}); p("M6 texto inválido", repr(mal[:5]), len(mal), st, raw[:80])
for c, n in ((B, "B"), (M2, "M2")):
    st, d, raw, _ = c.req("GET", T(R) + "/mensajes"); p("M7 lectura ajena", n, st)
# exportación (utf-8)
hoy = datetime.date.today(); q = f"?desde={(hoy - datetime.timedelta(days=60)).isoformat()}&hasta={hoy.isoformat()}"
st, d, raw, hd = GES.req("GET", "/api/gestion/exportacion" + q)
open(sys.argv[3], "w", encoding="utf-8", newline="").write(raw)
pat = {"correo": r"[\w.+-]+@[\w-]+\.\w+", "rut": r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b", "telefono": r"\+?56\s?9[\s\d]{8,}", "uuid": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", "nombres": r"QA S5|Maestro|Cliente|Pasaje|Demo"}
p("EXPORT", st, hd.get("Content-Type"), hd.get("Content-Disposition"), "| filas:", len(raw.splitlines()) - 1, "| patrones:", {k: len(re.findall(v, raw)) for k, v in pat.items()})
p(raw.replace("﻿", "<BOM>")[:400])
