from lib import *
def ui_login(pg, ident, query=""):
    pg.goto(BASE + "ingresar.html" + query); pg.wait_for_load_state("networkidle")
    pg.fill("#identificador", ident); pg.fill("#contrasena", D["pwd"])
    pg.locator("button[type=submit]").click()
    pg.wait_for_url(lambda u: "ingresar" not in u, timeout=15000); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(700)
    return pg.url.replace(BASE, "")
def marca(pg): return pg.evaluate("(()=>{const a=document.querySelector('header a');return a? a.getAttribute('href'):null})()")
with sync_playwright() as p:
    b = lanzar(p)
    print("== 1. INICIO POR ROL (ingreso por la pantalla, sin siguiente)")
    casos = [("cliente A","A","categorias.html"),("maestro M1","M1","mis-trabajos.html"),("curatoria","CUR","curatoria.html"),("comercial","COM","comercial.html"),
             ("moderacion","MOD","moderacion.html"),("gestion","GES","indicadores.html"),("DUAL maestro+cliente","DUAL_CORREO","mis-trabajos.html"),
             ("multi comercial+gestion","MULTI1","comercial.html"),("multi moderacion+curatoria","MULTI2","curatoria.html")]
    for w in (360, 1280):
        for nom, k, esp in casos:
            c, pg = ctx(b, w); 
            try:
                d = ui_login(pg, D.get(k, k)); m = marca(pg)
                print("w%d %-26s destino=%-18s marca=%-18s %s" % (w, nom, d.split('?')[0], m, "PASS" if d.split('?')[0]==esp and m==esp else "FAIL(esp %s)"%esp), pg.errs[:2])
            except Exception as e: print("w%d %s ERROR %s" % (w, nom, str(e)[:100]))
            c.close()
    # siguiente
    for w in (360, 1280):
        c, pg = ctx(b, w); d = ui_login(pg, D["M1"], "?siguiente=servicios"); print("w%d siguiente=servicios (M1) ->"%w, d, "PASS" if d.startswith("mis-servicios") else "FAIL"); c.close()
        c, pg = ctx(b, w); d = ui_login(pg, D["MULTI2"], "?siguiente=moderacion"); print("w%d siguiente=moderacion (multi2) ->"%w, d, "PASS" if d.startswith("moderacion") else "FAIL"); c.close()
        c, pg = ctx(b, w); d = ui_login(pg, D["A"], "?siguiente=servicios"); print("w%d siguiente=servicios (cliente sin rol) ->"%w, d); c.close()
    # sin sesion
    for w in (360, 1280):
        c, pg = ctx(b, w)
        for r in ["index.html","ingresar.html","registro-cliente.html","postulacion-maestro.html","categorias.html","buscar.html","ayuda-orden.html"]:
            ir(pg, r)
            h = pg.evaluate("[...document.querySelectorAll('header a,header button')].filter(e=>e.getBoundingClientRect().width>0).map(e=>(e.getAttribute('href')||'btn')+'|'+e.innerText.trim())")
            print("w%d sin sesion %-26s header=%s %s"%(w,r,h,"PASS" if h==["index.html|AlTiro"] else "FAIL"))
        c.close()
