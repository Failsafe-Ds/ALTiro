import sys, socket, threading, json, urllib.request
from playwright.sync_api import sync_playwright
host=sys.argv[1]; REF=sys.argv[2]
def pipe(a,b):
    try:
        while True:
            d=a.recv(65536)
            if not d: break
            b.sendall(d)
    except Exception: pass
    finally:
        for s in (a,b):
            try: s.close()
            except Exception: pass
srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1); srv.bind(("127.0.0.1",443)); srv.listen(50)
def acc():
    while True:
        c,_=srv.accept(); u=socket.create_connection((host,443))
        threading.Thread(target=pipe,args=(c,u),daemon=True).start(); threading.Thread(target=pipe,args=(u,c),daemon=True).start()
threading.Thread(target=acc,daemon=True).start()
AXE=urllib.request.urlopen("https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.3/axe.min.js").read().decode()
def axe(pg,etq):
    pg.evaluate(AXE)
    r=pg.evaluate("async()=>{const r=await axe.run(document,{runOnly:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']});return r.violations.map(v=>v.id+':'+v.nodes.length)}")
    print("AXE",etq,r if r else "0 violaciones")
with sync_playwright() as p:
    b=p.chromium.launch(args=["--ignore-certificate-errors","--host-resolver-rules=MAP localhost 127.0.0.1"])
    ctx=b.new_context(viewport={"width":390,"height":800},is_mobile=True,has_touch=True,locale="es-CL",ignore_https_errors=True,bypass_csp=True)
    pg=ctx.new_page(); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.goto("https://localhost/buscar.html"); pg.wait_for_load_state("networkidle")
    axe(pg,"buscar inicial")
    # validacion: enviar vacio
    pg.click("#paso-que button[type=submit]"); pg.wait_for_timeout(400)
    print("ERR vacio:", pg.inner_text("#error-oficio"), "|", pg.inner_text("#error-comuna"), "| foco en:", pg.evaluate("document.activeElement.id"))
    pg.select_option("#oficio","cerrajeria"); pg.select_option("#region","8"); pg.wait_for_timeout(500); pg.select_option("#comuna","8111")
    pg.click("#ir-cuando"); pg.wait_for_timeout(300)
    opts=pg.eval_on_selector_all("#fecha option","o=>o.map(x=>x.value)"); print("fechas ofrecidas:",len(opts),opts[:2],opts[-1])
    pg.select_option("#fecha",opts[3]); pg.select_option("#inicio-hora","03"); pg.select_option("#inicio-minutos","00"); pg.select_option("#fin-hora","04"); pg.select_option("#fin-minutos","00")
    axe(pg,"buscar paso cuando")
    pg.click("#paso-cuando button[type=submit]"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(800)
    print("URL:",pg.url.replace("https://localhost",""))
    txt=pg.inner_text("main"); 
    print("CA-04.1 mensaje explicito:", "No encontramos maestros con esos criterios" in txt)
    print("CA-04.2 seccion rotulada:", "Sugerencias: no cumplen todo lo que pediste" in txt)
    print("CA-04.3 criterio por tarjeta:", txt.count("No cumple:"), "tarjetas;", "No tiene libre el horario" in txt)
    # orden en DOM: seccion de resultados antes/separada
    print("secciones:", pg.eval_on_selector_all("main h2","h=>h.map(x=>x.innerText)"))
    print("foco tras buscar:", pg.evaluate("document.activeElement.tagName+'#'+document.activeElement.id"))
    axe(pg,"buscar sugerencias")
    # tarjeta de sugerencia: ver perfil
    pg.click("text=Ver perfil >> nth=0"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(600)
    print("ficha URL:", pg.url.replace("https://localhost",""))
    axe(pg,"ficha")
    print("pageerrors:",errs)
    b.close()
