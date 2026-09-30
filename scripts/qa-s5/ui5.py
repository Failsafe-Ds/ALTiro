"""QA S5: pase de navegador en 360 px con red limitada (Chromium/CDP 4/1 Mbps, 150 ms, D-19) y Firefox sin red emulada.
Uso (dentro de la imagen de Playwright, red altiro_frontal): python3 ui5.py <host-proxy> <datos.json> <datos3.json> [chromium|firefox]"""
import sys, json, socket, threading, time, re, urllib.request
from playwright.sync_api import sync_playwright
host = sys.argv[1]; D = json.load(open(sys.argv[2])); X = json.load(open(sys.argv[3])); motor = sys.argv[4] if len(sys.argv) > 4 else "chromium"


def pipe(a, b):
    try:
        while True:
            d = a.recv(65536)
            if not d: break
            b.sendall(d)
    except Exception: pass
    finally:
        for s in (a, b):
            try: s.close()
            except Exception: pass


srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("127.0.0.1", 443)); srv.listen(50)
def acc():
    while True:
        c, _ = srv.accept(); u = socket.create_connection((host, 443))
        threading.Thread(target=pipe, args=(c, u), daemon=True).start(); threading.Thread(target=pipe, args=(u, c), daemon=True).start()
threading.Thread(target=acc, daemon=True).start()
AXE = urllib.request.urlopen("https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.3/axe.min.js").read().decode()
JS = """()=>{
 const W=document.documentElement.clientWidth, o={scroll:document.documentElement.scrollWidth,W:W,fuera:[],chicos:[],texto:document.body.innerText};
 const vis=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 document.querySelectorAll('body *').forEach(e=>{ if(!vis(e))return; const r=e.getBoundingClientRect(); if(r.right>W+1||r.left<-1) o.fuera.push(e.tagName+'.'+e.className+':'+Math.round(r.left)+'-'+Math.round(r.right)); });
 document.querySelectorAll('button,a[href],input:not([type=hidden]),select,textarea,summary,label').forEach(e=>{ if(!vis(e))return;
   if(e.tagName==='LABEL'&&!e.querySelector('input')) return; const s=getComputedStyle(e); const r=e.getBoundingClientRect();
   const inl=(e.tagName==='A'&&s.display==='inline'&&e.closest('p,li,span,td')&&!e.classList.contains('boton')&&!/boton/.test(e.className));
   let w=r.width,h=r.height; if(e.tagName==='INPUT'&&(e.type==='radio'||e.type==='checkbox')){const l=e.closest('label'); if(l){const lr=l.getBoundingClientRect(); w=lr.width;h=lr.height;}}
   if(w<43.5||h<43.5) o.chicos.push((inl?'[en linea] ':'')+e.tagName+'#'+(e.id||'')+'.'+(e.className||'')+' '+Math.round(w)+'x'+Math.round(h)+' "'+(e.innerText||e.value||e.getAttribute('aria-label')||'').slice(0,25)+'"'); });
 return o;}"""
JARGON = re.compile(r"\b(ticket|API|JSON|HTTP|token|c[oó]digo de error|sesi[oó]n expir|undefined|null|NaN|Traceback|409|404|403|500)\b", re.I)
RES = []


def nuevo(b, persona):
    kw = dict(viewport={"width": 360, "height": 740}, has_touch=True, locale="es-CL", ignore_https_errors=True)
    if motor == "chromium": kw["is_mobile"] = True
    ctx = b.new_context(**kw); pg = ctx.new_page(); pg.errs = []; pg.bytes = 0
    pg.on("pageerror", lambda e: pg.errs.append("js:" + str(e)[:120]))
    pg.on("console", lambda m: pg.errs.append("console:" + m.text[:140]) if m.type == "error" and "status of 4" not in m.text and "status of 409" not in m.text else None)
    def resp(r):
        try: pg.bytes += len(r.body())
        except Exception: pass
    pg.on("response", resp)
    if motor == "chromium":
        cdp = ctx.new_cdp_session(pg); cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150, "downloadThroughput": 4_000_000 / 8, "uploadThroughput": 1_000_000 / 8})
    pg.goto("https://localhost/ingresar.html"); pg.wait_for_load_state("networkidle")
    r = pg.evaluate("""async(a)=>{await fetch('/api/sesion/csrf',{credentials:'same-origin'});
      const t=document.cookie.split('; ').find(x=>x.startsWith('csrftoken=')).split('=')[1];
      const r=await fetch('/api/sesion',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':t},body:JSON.stringify({identificador:a[0],contrasena:a[1]})}); return r.status}""", [D[persona], D["pwd"]])
    assert r == 200, (persona, r)
    return pg


def revisar(pg, nombre, espera=800, axe=True):
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(espera)
    o = pg.evaluate(JS); ch = [c for c in o["chicos"] if not c.startswith("[en linea]")]
    v = []
    if axe:
        pg.evaluate(AXE)
        v = pg.evaluate("async()=>{const r=await axe.run(document,{runOnly:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']});return r.violations.map(v=>v.id+':'+v.nodes.length)}")
    jg = sorted(set(m.group(0) for m in JARGON.finditer(o["texto"])))
    print("%-34s scroll=%d/%d fuera=%d chicos=%d axe=%s jerga=%s errores=%d" % (nombre, o["scroll"], o["W"], len(o["fuera"]), len(ch), v if axe else "-", jg, len(pg.errs)), flush=True)
    for c in ch[:5]: print("     chico:", c)
    for c in o["fuera"][:3]: print("     fuera:", c)
    for e in pg.errs[:3]: print("     err:", e)
    pg.errs.clear(); return o["texto"]


def ir(pg, ruta):
    pg.bytes = 0; t = time.time(); pg.goto("https://localhost/" + ruta); pg.wait_for_load_state("networkidle"); dt = time.time() - t
    print("   carga %-44s %.2f s %d KiB" % (ruta[:44], dt, pg.bytes // 1024), flush=True)


with sync_playwright() as p:
    b = getattr(p, motor).launch(args=["--ignore-certificate-errors", "--host-resolver-rules=MAP localhost 127.0.0.1"] if motor == "chromium" else [],
                                 firefox_user_prefs={"network.dns.localDomains": "localhost"} if motor == "firefox" else None)
    print(motor, b.version)
    # ---- Cliente A
    pg = nuevo(b, "A")
    ir(pg, "mis-pedidos.html"); revisar(pg, "A mis-pedidos (pendientes)")
    if pg.locator("[data-tab=historial]").count():
        pg.locator("[data-tab=historial]").click(); pg.wait_for_timeout(900); t = revisar(pg, "A mis-pedidos (Historial)")
        print("     texto clave:", [x for x in ("Precio", "acordado", "Finalizado", "Cerrado", "Ver conversación", "Evaluar", "Denunciar") if x in t])
    pg.locator("[data-tab=aceptado]").click() if pg.locator("[data-tab=aceptado]").count() else None
    pg.wait_for_timeout(700); t = revisar(pg, "A mis-pedidos (aceptados)")
    print("     texto clave (precio por aceptar):", [x for x in ("Aceptar", "No estoy de acuerdo", "por aceptar", "Precio") if x in t])
    ir(pg, "conversacion.html?ticket=" + X["msgs"]); t = revisar(pg, "A conversacion (aceptado, 2 mensajes)")
    print("     mensajes visibles:", [x for x in ("Hola, ¿a qué hora llegas?", "A las 8 en punto", "Tú", "Maestro") if x in t])
    ir(pg, "conversacion.html?ticket=" + D["finalizado"][0]); t = revisar(pg, "A conversacion (finalizado, lectura)")
    ir(pg, "conversacion.html?ticket=" + D["cerrado"][0]); t = revisar(pg, "A conversacion (cerrado)", axe=False); print("     ", t[:160].replace("\n", " | "))
    ir(pg, "evaluar.html?ticket=" + D["finalizado"][1]); revisar(pg, "A evaluar (sin evaluar)")
    if pg.locator("#formulario-evaluacion:visible").count():
        for n in (4, 9, 14): pg.locator("#formulario-evaluacion input[type=radio]").nth(n).check()
        pg.fill("#comentario", "Muy buen trabajo (QA ficticio)."); pg.locator("#formulario-evaluacion button[type=submit]").click(); pg.wait_for_timeout(1500)
    t = revisar(pg, "A evaluar (tras enviar / ya evaluado)"); print("     estado:", t[:220].replace(chr(10), " | "))
    ir(pg, "perfil-maestro.html?m=" + X["pub"]); t = revisar(pg, "A ficha con calificación")
    print("     ficha:", [x for x in ("Puntualidad", "Trabajo", "Cordialidad", "5,0", "5.0", "Muy buen trabajo", "Todavía no tiene") if x in t])
    ir(pg, "buscar.html?oficio=pintura&region=8&comuna=8101"); t = revisar(pg, "A buscar (resultados con calificación)")
    print("     tarjeta con calificación:", "5,0" in t or "5.0" in t, "| Todavía no tiene:", "Todavía no tiene" in t)
    pg.context.close()
    # ---- Maestro M1
    pg = nuevo(b, "M1")
    ir(pg, "mis-trabajos.html"); revisar(pg, "M1 mis-trabajos (pendientes)")
    for nom in ("aceptado", "historial"):
        pg.locator("[data-tab=%s]" % nom).click(); pg.wait_for_timeout(1000); t = revisar(pg, "M1 mis-trabajos (%s)" % nom)
        print("     texto clave:", [x for x in ("Registrar precio final", "Ver conversación", "Evaluar", "Precio", "acordado", "Lo rechazaste", "Ver detalle") if x in t])
    pg.locator("[data-tab=aceptado]").click(); pg.wait_for_timeout(900)
    n = pg.get_by_role("button", name=re.compile("Ver detalle")).count(); print("     aceptados con detalle:", n)
    for i in range(n):
        pg.get_by_role("button", name=re.compile("Ver detalle")).nth(i).click(); pg.wait_for_timeout(700)
        if pg.locator("#monto-final:visible").count(): break
    print("     campo de monto visible:", pg.locator("#monto-final:visible").count())
    if pg.locator("#monto-final:visible").count():
        t = revisar(pg, "M1 mis-mis-trabajos (detalle con precio)"); pg.fill("#monto-final", "27000"); pg.wait_for_timeout(300)
        print("     explicación:", pg.locator("#explicacion-precio").inner_text()[:140])
        pg.locator("#registrar-precio").click(); pg.wait_for_timeout(1500); t = revisar(pg, "M1 mis-trabajos (tras registrar)", axe=False)
        print("     tras registrar:", [x for x in ("tendrá que aceptar", "Esperando que el cliente", "27.000") if x in t])
    ir(pg, "conversacion.html?ticket=" + X["msgs"]); revisar(pg, "M1 conversacion (aceptado)")
    ir(pg, "evaluar.html?ticket=" + D["finalizado"][2]); t = revisar(pg, "M1 evaluar (con recibida y denuncia)"); print("     ", [x for x in ("Evaluación que recibiste", "Denunciar", "En revisión") if x in t])
    pg.context.close()
    # ---- Moderación
    pg = nuevo(b, "MOD")
    ir(pg, "moderacion.html"); revisar(pg, "MOD moderacion (lista)")
    it = pg.locator("#lista-denuncias button, #lista-denuncias a").first
    if it.count():
        it.click(); pg.wait_for_timeout(1200); t = revisar(pg, "MOD moderacion (detalle)"); print("     detalle sin dirección/teléfono:", not any(x in t for x in ("Pasaje Ficticio", "1000 0103", "10000103")))
        if pg.locator("#ver-conversacion:visible").count():
            pg.locator("#ver-conversacion").click(); pg.wait_for_timeout(1200); t = revisar(pg, "MOD moderacion (conversación)", axe=False); print("     ", [x for x in ("no hubo mensajes", "Hola") if x in t])
        print("     formulario de resolución visible:", pg.locator("#formulario-resolucion:visible").count())
    pg.context.close()
    # ---- Gestión
    pg = nuevo(b, "GES")
    ir(pg, "indicadores.html"); revisar(pg, "GES indicadores (inicial)")
    pg.fill("#desde", X["desde"]); pg.fill("#hasta", X["hasta"]); pg.locator("#formulario-periodo button[type=submit]").first.click(); pg.wait_for_timeout(1500)
    t = revisar(pg, "GES indicadores (resultados)"); print("     ", [x for x in ("Tasa de concreción", "Tiempo de primera respuesta", "Vigencia documental", "Exportar CSV") if x in t])
    pg.fill("#desde", "2026-09-29"); pg.fill("#hasta", "2026-09-30"); pg.locator("#formulario-periodo button[type=submit]").first.click(); pg.wait_for_timeout(1200)
    t = revisar(pg, "GES indicadores (período inválido)", axe=False); print("     error:", t[t.find("período") - 60: t.find("período") + 120].replace("\n", " | ") if "período" in t else "sin mensaje")
    pg.context.close(); b.close()
