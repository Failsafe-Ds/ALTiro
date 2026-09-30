import http.client, ssl, json, sys, datetime, re
S = json.loads(sys.argv[1]); CTX = ssl._create_unverified_context()
class C:
    def __init__(s): s.ck = {}
    def req(s, m, path, body=None):
        h = http.client.HTTPSConnection("proxy", 443, context=CTX)
        hd = {"Host": "localhost", "Content-Type": "application/json", "Origin": "https://localhost", "Referer": "https://localhost/", "Cookie": "; ".join(f"{k}={v}" for k, v in s.ck.items())}
        if m != "GET" and "csrftoken" in s.ck: hd["X-CSRFToken"] = s.ck["csrftoken"]
        h.request(m, path, json.dumps(body) if body is not None else None, hd)
        r = h.getresponse(); raw = r.read()
        for v in r.headers.get_all("Set-Cookie") or []:
            k, _, rest = v.partition("="); s.ck[k] = rest.split(";")[0]
        try: d = json.loads(raw)
        except Exception: d = raw[:80]
        return r.status, d, raw.decode("utf8", "replace")
    def login(s, ident):
        s.req("GET", "/api/sesion/csrf")
        st, d, _ = s.req("POST", "/api/sesion", {"identificador": ident, "contrasena": S["pwd"]}); assert st == 200, (st, d)
        s.req("GET", "/api/sesion/csrf")
def E(d):
    x = d.get("ticket", d) if isinstance(d, dict) else d
    return (x.get("estado"), x.get("motivo_cierre")) if isinstance(x, dict) else x
def p(*a): print(*a, flush=True)
anon = C(); A = C(); B = C(); M = C()
# 1. buscar
st, d, _ = anon.req("GET", f"/api/busqueda?oficio=pintura&comuna={S['comuna']}")
refs = [r["ref"] for r in d["resultados"]]
p("BUSCAR", st, "total", d["total"], "maestro QA en resultados:", S["ref"] in refs or f"no en pag1 (pagina {d['pagina']}/{d['paginas']})")
st, d, _ = anon.req("GET", f"/api/busqueda?oficio=pintura&comuna={S['comuna']}&pagina=1")
# 2. ficha
st, d, raw = anon.req("GET", f"/api/maestros/publicos/{S['ref']}")
p("FICHA", st, "claves:", sorted(d.keys()))
bl = d["maestro"].get("bloques"); p(" bloques:", len(bl) if bl else None, json.dumps(bl[:2], ensure_ascii=False)[:300] if bl else "")
def pedido(f, i, fin, **k):
    x = {"maestro": S["ref"], "servicio": S["servicio"], "comuna": S["comuna"], "fecha": f, "inicio": i, "fin": fin,
         "direccion": "Pasaje Ficticio 123, depto 45", "descripcion": "Pintar una pieza de prueba.", "materiales": True}
    x.update(k); return x
hoy = datetime.date.today()
def prox(dow):  # proximo dia con isoweekday dow, desde manana
    d = hoy + datetime.timedelta(days=1)
    while d.isoweekday() != dow: d += datetime.timedelta(days=1)
    return d.isoformat()
jue, vie, sab, dom = prox(4), prox(5), prox(6), prox(7)
A.login(S["clientes"][0]); B.login(S["clientes"][1]); M.login("RUT" if False else S["rut"])
T = {}
st, d, raw = M.req("GET", "/api/maestros/tickets?estado=pendiente")
ts = sorted(d["tickets"], key=lambda x: x["numero"]); assert len(ts) == 6, len(ts)
for i, t in enumerate(ts): T["T%d" % (i + 1)] = t["ref"]
p("MAPA", {k: (v[:8]) for k, v in T.items()})
st, d, raw = A.req("GET", f"/api/tickets/{T['T1']}"); p("CLIENTE A ve T1 (detalle) claves:", st, sorted(d.keys()) if isinstance(d, dict) else d)
# repetido
st, d, _ = A.req("POST", "/api/tickets", pedido(jue, "08:00", "12:00")); p("REPETIDO T1 (D-10)", st)
# bloque a <4h o ya pasado
st, d, _ = A.req("POST", "/api/tickets", pedido(hoy.isoformat(), "19:30", "21:00")); p("BLOQUE <=4h / hoy", st, d.get("errores") if isinstance(d, dict) else d)
# maestro: bandeja pendiente sin datos personales
st, d, raw = M.req("GET", "/api/maestros/tickets?estado=pendiente")
fuga = [x for x in ("Pasaje Ficticio", "depto 45", "+56 9 7000", "Cliente QA", "qa.s4.") if x in raw]
p("MAESTRO BANDEJA pendiente", st, "tickets:", len(d.get("tickets", d.get("resultados", []))) if isinstance(d, dict) else d, "FUGA:", fuga)
st, d, raw = M.req("GET", f"/api/tickets/{T['T1']}"); p("MAESTRO DETALLE T1 pendiente", st, "FUGA:", [x for x in ("Pasaje Ficticio", "depto 45", "+56 9 7000", "Cliente QA", "qa.s4.") if x in raw])
# terceros: cliente B accede a T1 de A; ticket inexistente
st, d, _ = B.req("GET", f"/api/tickets/{T['T1']}"); p("IDOR B->T1", st)
st, d, _ = B.req("POST", f"/api/tickets/{T['T1']}/cancelacion"); p("IDOR B cancela T1", st)
st, d, _ = M.req("GET", "/api/tickets/00000000-0000-4000-8000-000000000000"); p("INEXISTENTE", st)
st, d, _ = anon.req("GET", f"/api/tickets/{T['T1']}"); p("ANONIMO T1", st)
st, d, _ = A.req("POST", f"/api/tickets/{T['T1']}/aceptacion"); p("CLIENTE acepta (parte equivocada)", st)
# aceptar T1
st, d, raw = M.req("POST", f"/api/tickets/{T['T1']}/aceptacion"); p("ACEPTAR T1", st, E(d))
st, d, raw = M.req("GET", f"/api/tickets/{T['T1']}"); p("MAESTRO ve contacto tras aceptar:", "Pasaje Ficticio" in raw, "+56" in raw or "9 7000" in raw or "700000" in raw)
st, d, _ = B.req("GET", f"/api/tickets/{T['T2']}"); p("T2 (B) tras aceptar T1:", E(d))
st, d, _ = B.req("GET", "/api/avisos"); av = json.dumps(d, ensure_ascii=False); p("AVISOS B:", st, "bloque_tomado/enlace:", "enlace" in av, re.findall(r'"tipo": "(\w+)"', av)[:6])
# ficha: jue 08-12 ocupado; nuevo ticket ahi -> 409
st, d, _ = B.req("POST", "/api/tickets", pedido(jue, "08:00", "12:00")); p("PEDIR bloque ocupado", st, (d.get("mensaje") if isinstance(d, dict) else d), "horarios libres:", len(d.get("bloques", d.get("alternativas", []))) if isinstance(d, dict) else "")
# rechazar T3 -> bloque libre
st, d, _ = M.req("POST", f"/api/tickets/{T['T3']}/rechazo", {}); p("RECHAZAR T3", st, E(d))
# cancelar T4; aceptar despues
st, d, _ = A.req("POST", f"/api/tickets/{T['T4']}/cancelacion", {}); p("CANCELAR T4", st, E(d))
st, d, _ = M.req("POST", f"/api/tickets/{T['T4']}/aceptacion", {}); p("ACEPTAR T4 tras cancelar", st, (d.get("mensaje") if isinstance(d, dict) else d))
# busqueda con bloque: jue 08-12 ocupado, vie 08-12 libre
for f, lab in ((jue, "jue (ocupado)"), (vie, "vie (libre tras rechazo)")):
    st, d, _ = anon.req("GET", f"/api/busqueda?oficio=pintura&comuna={S['comuna']}&fecha={f}&inicio=08:00&fin=12:00")
    p("BUSCAR bloque", lab, "en resultados:", S["ref"] in [r["ref"] for r in d["resultados"]], "en sugerencias:", S["ref"] in [r["ref"] for r in d["sugerencias"]])
print("TICKETS", json.dumps(T))
