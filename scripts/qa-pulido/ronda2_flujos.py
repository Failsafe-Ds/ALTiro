"""Ronda 2 (v0.6.3), puntos 1-3: dos flujos (ADR-002 E-3.2), cerrar sesión en este dispositivo, ingresar centrada y botones de cuenta."""
from lib2 import *
CLIENTE = ["categorias", "buscar", "perfil-maestro", "pedir-trabajo", "mis-pedidos"]
MAESTRO = ["mis-trabajos", "mi-perfil", "mis-servicios", "mi-cobertura", "mi-agenda", "mis-documentos", "mi-postulacion"]
NEUTRAS = ["cuenta", "index"]
def marca(pg): return pg.evaluate("document.querySelector('header .marca').getAttribute('href')")
def menu(pg):
    return pg.evaluate("[...document.querySelectorAll('#menu-lista a')].map(a=>a.textContent.trim()+'>'+a.getAttribute('href'))")
with sync_playwright() as p:
    b = lanzar(p)
    for w in (360, 1280):
        c, pg = ctx(b, w); api_login(pg, D["DUAL"])
        for nombre in CLIENTE + MAESTRO:
            q = {"buscar": "?oficio=pintura&comuna=8101", "perfil-maestro": "?ref=" + D.get("m1pub", ""), "pedir-trabajo": ""}.get(nombre, "")
            ir(pg, nombre + ".html" + (q if nombre == "buscar" else ""))
            esperado = "categorias.html" if nombre in CLIENTE else "mis-trabajos.html"
            chk(w, 1, "marca " + nombre, marca(pg) == esperado, "href=%s esperado=%s url=%s" % (marca(pg), esperado, pg.url.split("/")[-1][:40]))
        # neutras siguen el último flujo
        for previo, esp in (("mis-pedidos", "categorias.html"), ("mis-trabajos", "mis-trabajos.html")):
            for neutra in NEUTRAS:
                ir(pg, previo + ".html"); ir(pg, neutra + ".html")
                chk(w, 1, "neutra %s tras %s" % (neutra, previo), marca(pg) == esp, "href=%s" % marca(pg))
        # sin flujo previo: contexto nuevo, orden de E-3
        c2, pg2 = ctx(b, w); api_login(pg2, D["DUAL"]); ir(pg2, "cuenta.html")
        chk(w, 1, "neutra sin flujo previo (orden E-3)", marca(pg2) in ("categorias.html", "mis-trabajos.html"), "href=%s" % marca(pg2)); c2.close()
        # el menú cambia de flujo
        ir(pg, "mis-pedidos.html"); m = menu(pg)
        chk(w, 1, "menu con ambos flujos", "Buscar maestros>categorias.html" in m and "Mi trabajo como maestro>mis-trabajos.html" in m, str(m))
        pg.click(".menu-boton"); pg.click("#menu-lista a:has-text('Mi trabajo como maestro')"); pg.wait_for_load_state("networkidle")
        chk(w, 1, "menu -> Mi trabajo como maestro cambia el flujo", pg.url.endswith("mis-trabajos.html") and marca(pg) == "mis-trabajos.html", pg.url.split("/")[-1])
        ir(pg, "cuenta.html"); chk(w, 1, "neutra tras cambiar a maestro", marca(pg) == "mis-trabajos.html", marca(pg))
        pg.click(".menu-boton"); pg.click("#menu-lista a:has-text('Buscar maestros')"); pg.wait_for_load_state("networkidle")
        chk(w, 1, "menu -> Buscar maestros cambia el flujo", marca(pg) == "categorias.html", marca(pg))
        # conversacion / evaluar por parte del pedido (DUAL es maestro en a_dual_maestro y cliente en a_dual_cliente)
        for etiqueta, pagina, ref, esp in (("conversacion como maestro", "conversacion", D["a_dual_maestro"], "mis-trabajos.html"),
                                           ("conversacion como cliente", "conversacion", D["a_dual_cliente"], "categorias.html"),
                                           ("evaluar como maestro", "evaluar", D["f_dual_maestro"], "mis-trabajos.html"),
                                           ("evaluar como cliente", "evaluar", D["f_dual_cliente"], "categorias.html")):
            ir(pg, "cuenta.html" if esp == "mis-trabajos.html" and False else ("mis-pedidos.html" if esp == "mis-trabajos.html" else "mis-trabajos.html"))  # parte del flujo contrario
            ir(pg, "%s.html?ticket=%s" % (pagina, ref)); pg.wait_for_timeout(800)
            chk(w, 1, etiqueta, marca(pg) == esp, "href=%s (venía del flujo contrario)" % marca(pg))
        pg.close(); c.close()
        # solo cliente
        c, pg = ctx(b, w); api_login(pg, D["C1"]); ir(pg, "mis-pedidos.html"); m = menu(pg)
        chk(w, 1, "cuenta solo cliente sin «Mi trabajo como maestro»", not any("Mi trabajo" in x for x in m), str(m))
        ir(pg, "cuenta.html"); chk(w, 1, "solo cliente: marca en neutra", marca(pg) == "categorias.html", marca(pg))
        # punto 2: texto de cerrar sesión
        pg.click(".menu-boton")
        sal = pg.inner_text(".menu-salir")
        chk(w, 2, "menú", sal == "Cerrar sesión en este dispositivo", repr(sal))
        txt = pg.evaluate("document.querySelector('main').innerText")
        i = txt.find("Cerrar sesión")
        chk(w, 2, "cuenta botón", pg.locator("#cerrar-sesion").inner_text() == "Cerrar sesión en este dispositivo", repr(pg.locator("#cerrar-sesion").inner_text()))
        sect = pg.evaluate("document.getElementById('cerrar-sesion').closest('section,div.seccion,form,main').innerText") if True else ""
        parrafo = pg.evaluate("document.getElementById('aviso-cerrar').previousElementSibling.innerText")
        chk(w, 2, "cuenta: ningún texto dice celular/teléfono para la sesión", not re.search(r"celular|tel[eé]fono", parrafo, re.I), repr(parrafo))
        todo = pg.evaluate("document.body.innerText")
        for m_ in re.finditer(r"[^.\n]*(celular|tel[eé]fono)[^.\n]*", todo, re.I):
            if "sesi" in m_.group(0).lower(): chk(w, 2, "texto con sesión+celular/teléfono", False, repr(m_.group(0)))
        c.close()
        # punto 3 ingresar y cuenta
        c, pg = ctx(b, w); ir(pg, "ingresar.html")
        g = pg.evaluate("""()=>{const f=document.querySelector('main form');const r=f.getBoundingClientRect();const m=document.querySelector('main').getBoundingClientRect();
          const ls=[...f.querySelectorAll('label,input,button')].filter(e=>e.getBoundingClientRect().width>0).map(e=>Math.round(e.getBoundingClientRect().left));
          const h=document.querySelector('main h1');const hr=h.getBoundingClientRect();
          return {fl:r.left,fr:innerWidth-r.right,w:r.width,fs:getComputedStyle(document.body).fontSize,lefts:[...new Set(ls)],h1left:hr.left,h1ta:getComputedStyle(h).textAlign,scrollX:document.documentElement.scrollWidth>innerWidth}}""")
        centrado = abs(g["fl"] - g["fr"]) <= 2
        chk(w, 3, "ingresar centrada (margen izq %.0f / der %.0f, ancho %.0f)" % (g["fl"], g["fr"], g["w"]), centrado and not g["scrollX"], str(g))
        c.close()
        c, pg = ctx(b, w); api_login(pg, D["DUAL"]); ir(pg, "cuenta.html")
        filas = pg.evaluate("""()=>[...document.querySelectorAll('.acciones')].filter(a=>a.getBoundingClientRect().width>0).map(a=>{const bs=[...a.querySelectorAll('button,a')].filter(b=>b.getBoundingClientRect().width>0);
          const tops=[...new Set(bs.map(b=>Math.round(b.getBoundingClientRect().top)))];return {n:bs.length,filas:tops.length,disp:getComputedStyle(a).display,wrap:getComputedStyle(a).flexWrap,anchos:bs.map(b=>Math.round(b.getBoundingClientRect().width)),aw:Math.round(a.getBoundingClientRect().width)}})""")
        chk(w, 3, "cuenta: acciones en fila que se envuelve", all(f["disp"] == "flex" and f["wrap"] == "wrap" for f in filas), str(filas))
        chk(w, 3, "cuenta: sin scroll lateral", not pg.evaluate("document.documentElement.scrollWidth>innerWidth"), "")
        multi = [f for f in filas if f["n"] > 1]
        chk(w, 3, "cuenta: con 2+ botones, en 1280 caben en una fila", w < 700 or all(f["filas"] == 1 for f in multi), str(multi))
        c.close()
    b.close()
