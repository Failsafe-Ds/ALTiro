"""QA S5: sondeos de acceso ajeno contra https://localhost (TLS autofirmado). Uso: python seguridad.py datos.json export.csv"""
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


anon = C(); A = C(); B = C(); M1 = C(); M2 = C(); MOD = C(); GES = C(); CUR = C()
for c, i in ((A, D["A"]), (B, D["B"]), (M1, D["M1"]), (M2, D["M2"]), (MOD, D["MOD"]), (GES, D["GES"]), (CUR, D["CUR"])): c.login(i)
F = {"pend": D["pendiente"][0], "acep": D["aceptado"][0], "cerr": D["cerrado"][0], "fa": D["finalizado"][0], "fb": D["finalizado"][1], "fc": D["finalizado"][2]}
NOEX = "00000000-0000-4000-8000-00000000abcd"
def T(r): return f"/api/tickets/{r}"
# 0. regresión de privacidad: maestro con ticket pendiente
for ruta in (T(F["pend"]), "/api/maestros/tickets?estado=pendiente", "/api/maestros/tickets"):
    st, d, raw, _ = M1.req("GET", ruta)
    fuga = [x for x in ("Pasaje Ficticio", "depto 45", "1000 0103", "10000103", "Cliente QA S5", "qa.s5.a") if x in raw]
    p("PRIVACIDAD maestro, pendiente", ruta, st, "FUGA:", fuga)
# 1. matriz de terceros
ACC = {"precio": ("POST", "/precio-final", {"monto": 30000}), "acepta": ("POST", "/precio-final/aceptacion", {"monto": 30000}),
       "objeta": ("POST", "/precio-final/objecion", {}), "msg_get": ("GET", "/mensajes", None),
       "msg_post": ("POST", "/mensajes", {"texto": "hola", "clave_envio": "11111111-1111-4111-8111-111111111111"}),
       "eval_post": ("POST", "/evaluacion", {"puntualidad": 3, "trabajo": 3, "cordialidad": 3}), "eval_get": ("GET", "/evaluaciones", None),
       "denuncia": ("POST", "/evaluacion-recibida/denuncia", {"motivo": "No corresponde"})}
def sinref(raw): return re.sub(r"[0-9a-f-]{36}", "<ref>", raw)
for k, (m, suf, b) in ACC.items():
    res = {}
    for nombre, cli, ref in (("anon", anon, F["acep"]), ("B", B, F["acep"]), ("M2", M2, F["acep"]), ("CUR", CUR, F["acep"]), ("MOD", MOD, F["acep"]), ("inex", B, NOEX)):
        st, d, raw, _ = cli.req(m, T(ref) + suf, b); res[nombre] = (st, sinref(raw)[:90])
    ajenos = {res[n] for n in ("B", "M2", "CUR", "MOD")}
    p(f"IDOR {k}: anon={res['anon'][0]} B={res['B'][0]} M2={res['M2'][0]} CUR={res['CUR'][0]} MOD={res['MOD'][0]} inexistente={res['inex'][0]} | ajenos identicos entre si={len(ajenos)==1} identicos a inexistente={ajenos=={res['inex']}}")
st, d, raw, _ = A.req("POST", T(F["acep"]) + "/precio-final", {"monto": 30000}); p("PARTE EQUIVOCADA cliente registra precio:", st, raw[:120])
st, d, raw, _ = M1.req("POST", T(F["acep"]) + "/precio-final/aceptacion", {"monto": 30000}); p("PARTE EQUIVOCADA maestro acepta precio:", st, raw[:120])
# 2. precio
def E(d): return (d.get("ticket", d) or {}) if isinstance(d, dict) else {}
st, d, raw, _ = M1.req("POST", T(F["acep"]) + "/precio-final", {"monto": 30000}); p("PRECIO maestro registra 30000 (por trabajo, distinto de 25000):", st, E(d).get("estado"), E(d).get("precio"))
st, d, raw, _ = A.req("POST", T(F["acep"]) + "/precio-final/objecion", {}); p("PRECIO cliente objeta:", st)
st, d, raw, _ = M1.req("POST", T(F["acep"]) + "/precio-final", {"monto": 30000}); p("PRECIO maestro re-registra:", st)
st, d, raw, _ = A.req("POST", T(F["acep"]) + "/precio-final/aceptacion", {"monto": 29000}); p("PRECIO acepta monto distinto del vigente (409):", st, raw[:100])
st, d, raw, _ = A.req("POST", T(F["acep"]) + "/precio-final/aceptacion", {"monto": 30000}); p("PRECIO acepta:", st, E(d).get("estado"))
st, d, raw, _ = M1.req("POST", T(F["acep"]) + "/precio-final", {"monto": 31000}); p("PRECIO cambiar tras finalizar (409):", st, raw[:100])
st, d, raw, _ = M1.req("POST", T(F["pend"]) + "/precio-final", {"monto": 30000}); p("PRECIO sobre pendiente (409):", st)
for n, c, r in (("cliente", A, "/api/clientes/tickets"), ("maestro", M1, "/api/maestros/tickets")):
    st, d, raw, _ = c.req("GET", r); t = [x for x in d["tickets"] if x["ref"] == F["acep"]][0]
    p("HISTORIAL", n, st, t.get("estado"), t.get("precio"), "| cerrado:", [x.get("motivo_cierre_texto") for x in d["tickets"] if x["ref"] == F["cerr"]])
# 3. mensajes
st, d, raw, _ = M1.req("POST", T(F["pend"]) + "/mensajes", {"texto": "hola", "clave_envio": "22222222-2222-4222-8222-222222222222"}); p("MSG escribir en pendiente (409):", st)
st, d, raw, _ = A.req("GET", T(F["pend"]) + "/mensajes"); p("MSG leer pendiente (409):", st)
st, d, raw, _ = A.req("GET", T(F["cerr"]) + "/mensajes"); p("MSG cerrado:", st, raw[:140])
st, d, raw, _ = A.req("POST", T(F["fa"]) + "/mensajes", {"texto": "hola", "clave_envio": "33333333-3333-4333-8333-333333333333"}); p("MSG escribir en finalizado (409):", st)
st, d, raw, _ = A.req("GET", T(F["fa"]) + "/mensajes"); p("MSG leer finalizado:", st)
# 4. evaluaciones
ev = {"puntualidad": 2, "trabajo": 3, "cordialidad": 2, "comentario": "Llegó tarde. QA ficticio."}
st, d, raw, _ = A.req("POST", T(F["fc"]) + "/evaluacion", ev); p("EVAL cliente evalúa finalizado:", st)
st, d, raw, _ = A.req("POST", T(F["fc"]) + "/evaluacion", ev); p("EVAL segunda del cliente (409):", st, raw[:100])
st, d, raw, _ = M1.req("POST", T(F["fc"]) + "/evaluacion", ev); p("EVAL maestro evalúa cliente:", st)
st, d, raw, _ = M1.req("POST", T(F["fc"]) + "/evaluacion", ev); p("EVAL segunda del maestro (409):", st)
st, d, raw, _ = A.req("POST", T(F["pend"]) + "/evaluacion", ev); p("EVAL sobre pendiente (409):", st)
st, d, raw, _ = A.req("POST", T(F["cerr"]) + "/evaluacion", ev); p("EVAL sobre cerrado (409):", st)
for bad in ({"puntualidad": 6, "trabajo": 3, "cordialidad": 3}, {"puntualidad": 0, "trabajo": 3, "cordialidad": 3}, {"puntualidad": 3, "trabajo": 3}, {"puntualidad": 3, "trabajo": 3, "cordialidad": 3, "comentario": "x" * 501}):
    st, d, raw, _ = A.req("POST", T(F["fb"]) + "/evaluacion", bad); p("EVAL invalida", list(bad.items())[0], st, raw[:80])
st, d, raw, _ = M1.req("GET", T(F["fc"]) + "/evaluaciones"); p("EVAL GET maestro:", st, json.dumps(d, ensure_ascii=False)[:300])
st, d, raw, _ = anon.req("GET", f"/api/maestros/publicos/{D['m1_pub']}")
mm = d.get("maestro", d) if isinstance(d, dict) else {}
p("FICHA calificacion:", st, json.dumps(mm.get("calificacion"), ensure_ascii=False)[:300], "| claves:", sorted(mm.keys())[:20])
p("  ficha con autor/cliente?", [x for x in ("Cliente QA S5", "qa.s5.a") if x in raw])
# 5. denuncia
st, d, raw, _ = B.req("POST", T(F["fc"]) + "/evaluacion-recibida/denuncia", {"motivo": "x"}); p("DENUNCIA tercero (404):", st)
st, d, raw, _ = A.req("POST", T(F["fc"]) + "/evaluacion-recibida/denuncia", {"motivo": "x"}); p("DENUNCIA por el evaluador (sin evaluacion recibida):", st, raw[:100])
st, d, raw, _ = M1.req("POST", T(F["fc"]) + "/evaluacion-recibida/denuncia", {"motivo": "El cliente no estaba en el lugar; la evaluación no corresponde."}); p("DENUNCIA por el maestro evaluado:", st)
st, d, raw, _ = M1.req("POST", T(F["fc"]) + "/evaluacion-recibida/denuncia", {"motivo": "otra vez"}); p("DENUNCIA repetida:", st, raw[:100])
# 6. moderación
for n, c in (("anon", anon), ("cliente", A), ("maestro", M1), ("curatoria", CUR), ("gestion", GES)):
    st, d, raw, _ = c.req("GET", "/api/moderacion/denuncias"); p("MOD lista", n, st)
st, d, raw, _ = MOD.req("GET", "/api/moderacion/denuncias?estado=abierta")
lst = d.get("denuncias", d.get("resultados", [])) if isinstance(d, dict) else []
p("MOD lista abierta:", st, len(lst), "claves:", sorted(d.keys()) if isinstance(d, dict) else d)
dref = None; det = ""
for x in lst:
    s2, d2, raw2, _ = MOD.req("GET", f"/api/moderacion/denuncias/{x['ref']}")
    if "no estaba en el lugar" in raw2: dref = x["ref"]; det = raw2; break
p("MOD detalle:", dref and dref[:8], "| fuga (direccion/telefono):", [x for x in ("Pasaje Ficticio", "1000 0103", "10000103", "1000 0101") if x in det])
for n, c in (("B cliente", B), ("M2", M2), ("anon", anon), ("MOD inexistente", MOD)):
    for suf in ("", "/conversacion", "/resolucion"):
        ref = NOEX if "inexist" in n else dref
        st, d, raw, _ = c.req("POST" if suf == "/resolucion" else "GET", f"/api/moderacion/denuncias/{ref}{suf}", {"decision": "mantener", "motivo": "x"} if suf == "/resolucion" else None)
        p("MOD", n, suf or "detalle", st)
st, d, raw, _ = MOD.req("GET", f"/api/moderacion/denuncias/{dref}/conversacion"); p("MOD conversacion (abierta):", st, raw[:140])
st, d, raw, _ = MOD.req("POST", f"/api/moderacion/denuncias/{dref}/resolucion", {"decision": "retirar"}); p("MOD resolver sin motivo (400):", st, raw[:100])
st, d, raw, _ = MOD.req("POST", f"/api/moderacion/denuncias/{dref}/resolucion", {"decision": "retirar", "motivo": "La evaluación no corresponde al trabajo realizado."}); p("MOD resolver:", st)
st, d, raw, _ = MOD.req("POST", f"/api/moderacion/denuncias/{dref}/resolucion", {"decision": "mantener", "motivo": "otra"}); p("MOD resolver de nuevo (409):", st)
st, d, raw, _ = MOD.req("GET", f"/api/moderacion/denuncias/{dref}/conversacion"); p("MOD conversacion tras resolver (404):", st)
st, d, raw, _ = anon.req("GET", f"/api/maestros/publicos/{D['m1_pub']}"); p("FICHA tras retirar:", json.dumps((d.get("maestro", d) if isinstance(d, dict) else {}).get("calificacion"), ensure_ascii=False)[:200])
# 7. gestión
hoy = datetime.date.today(); q = f"?desde={(hoy - datetime.timedelta(days=60)).isoformat()}&hasta={hoy.isoformat()}"
for n, c in (("anon", anon), ("cliente", A), ("maestro", M1), ("moderacion", MOD), ("curatoria", CUR)):
    st, d, raw, _ = c.req("GET", "/api/gestion/indicadores" + q); st2, _, _, _ = c.req("GET", "/api/gestion/exportacion" + q); p("GESTION", n, st, st2)
st, d, raw, _ = GES.req("GET", "/api/gestion/indicadores" + q); p("INDICADORES:", st, json.dumps(d, ensure_ascii=False)[:500])
for qq in ("", "?desde=2026-01-01&hasta=2026-01-10", f"?desde={hoy}&hasta={hoy}&x=1", "?desde=abc&hasta=2026-01-10"):
    st, d, raw, _ = GES.req("GET", "/api/gestion/indicadores" + qq); p("INDICADORES entrada", qq[:45] or "(vacia)", st, raw[:90])
st, d, raw, hd = GES.req("GET", "/api/gestion/exportacion" + q); p("EXPORT:", st, hd.get("Content-Type"), hd.get("Content-Disposition"), "bytes", len(raw))
open(sys.argv[2], "w", encoding="utf-8", newline="").write(raw)
pat = {"correo": r"[\w.+-]+@[\w-]+\.\w+", "rut": r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b", "telefono": r"\+?56\s?9[\s\d]{8,}", "uuid": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", "nombres": r"QA S5|Maestro QA|Cliente QA|Pasaje"}
p("EXPORT cabecera:", raw.splitlines()[0] if raw else "", "| filas:", max(0, len(raw.splitlines()) - 1), "| patrones personales:", {k: len(re.findall(v, raw)) for k, v in pat.items()})
