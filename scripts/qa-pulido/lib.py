import sys, json, socket, threading, time, re
from playwright.sync_api import sync_playwright
D = json.loads(open("/w/datos.json").read().split("JSON:",1)[1])
host = "proxy"
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
BASE = "https://localhost/"
def lanzar(p):
    return p.chromium.launch(args=["--ignore-certificate-errors", "--host-resolver-rules=MAP localhost 127.0.0.1"])
def ctx(b, w=360, h=740, lento=False):
    kw = dict(viewport={"width": w, "height": h}, locale="es-CL", ignore_https_errors=True)
    if w < 700: kw.update(has_touch=True, is_mobile=True)
    c = b.new_context(**kw); pg = c.new_page(); pg.errs = []; pg.bytes = 0
    pg.on("pageerror", lambda e: pg.errs.append("js:" + str(e)[:150]))
    pg.on("console", lambda m: pg.errs.append("console:" + m.text[:200]) if m.type == "error" else None)
    pg.http = []
    pg.on('response', lambda r: pg.http.append('%d %s' % (r.status, r.url.replace(BASE,'/'))) if r.status >= 400 else None)
    if lento:
        cdp = c.new_cdp_session(pg); cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150, "downloadThroughput": 4_000_000/8, "uploadThroughput": 1_000_000/8})
    return c, pg
def api_login(pg, ident, pwd=None):
    pg.goto(BASE + "ingresar.html"); pg.wait_for_load_state("networkidle")
    return pg.evaluate("""async(a)=>{await fetch('/api/sesion/csrf',{credentials:'same-origin'});
      const t=document.cookie.split('; ').find(x=>x.startsWith('csrftoken=')).split('=')[1];
      const r=await fetch('/api/sesion',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':t},body:JSON.stringify({identificador:a[0],contrasena:a[1]})}); return r.status}""", [ident, pwd or D["pwd"]])
def ir(pg, ruta, esperar=True):
    pg.goto(BASE + ruta)
    if esperar: pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(500)
CAMPOS = """()=>[...document.querySelectorAll('input,textarea,select,button')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&e.type!=='hidden'}).map(e=>e.tagName[0]+':'+(e.id||e.name||'')+':'+(e.type||'')+':'+(e.maxLength>0&&e.maxLength<100000?'max'+e.maxLength:'')+':'+(e.innerText||e.value||'').slice(0,22).split(String.fromCharCode(10)).join(' '))"""
def campos(pg): return pg.evaluate(CAMPOS)
