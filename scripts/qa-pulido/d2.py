from lib2 import *
with sync_playwright() as b_:
    b = lanzar(b_)
    for w in (360, 1280):
        F = "ingresar"
        c, pg = ctx(b, w); ir(pg, "ingresar.html")
        chk(w, 3, F, tipear(pg, "#identificador", 300) == 254 and tipear(pg, "#contrasena", 200) == 128, "maxlength 254 / 128")
        r = api(pg, "/api/sesion", {"identificador": "a" * 255, "contrasena": "x"})
        chk(w, 3, F, r[0] == 400 and "identificador" in (r[1].get("errores") or {}), "API identificador 255 -> %s %s" % (r[0], json.dumps(r[1], ensure_ascii=False)[:160]))
        r = api(pg, "/api/sesion", {"identificador": D["A"], "contrasena": "x" * 129})
        chk(w, 3, F, r[0] in (400, 401) and r[0] != 500, "API contraseña 129 -> %s %s" % (r[0], json.dumps(r[1], ensure_ascii=False)[:160]))
        # solo espacios y faltante
        pg.fill("#identificador", "    "); pg.fill("#contrasena", "")
        pg.locator("button[type=submit]").click(); pg.wait_for_timeout(500)
        er = errores(pg, "#ingresar")
        chk(w, 4, F, len(er) >= 1 and all(e["enVista"] for e in er), "solo espacios/vacío -> %s" % [(e["id"], e["t"], e["enVista"]) for e in er])
        pg.fill("#identificador", "  " + D["A"] + "  "); pg.fill("#contrasena", "")
        pg.locator("button[type=submit]").click(); pg.wait_for_timeout(400)
        chk(w, 7, F, pg.input_value("#identificador") == D["A"], "contraseña vacía no borra el identificador (valor %r)" % pg.input_value("#identificador"))
        # contraseña incorrecta: mensaje
        pg.fill("#contrasena", "incorrecta-1234"); pg.locator("button[type=submit]").click(); pg.wait_for_timeout(800)
        av = aviso(pg); er = errores(pg, "#ingresar")
        chk(w, 6, F, bool(av or er), "contraseña mala -> aviso %s errores %s" % ([a["t"] for a in av], [e["t"] for e in er]))
        chk(w, 7, F, pg.input_value("#identificador") == D["A"], "tras el error se conserva el identificador; contraseña=%r (se limpia por seguridad)" % pg.input_value("#contrasena"))
        # carga con red limitada
        pg.fill("#contrasena", D["pwd"])
        pg.evaluate("""()=>{const f=document.getElementById('ingresar'),b=f.querySelector('button[type=submit]');f.addEventListener('submit',()=>setTimeout(()=>sessionStorage.setItem('__est',JSON.stringify({dis:b.disabled,txt:b.innerText,busy:f.getAttribute('aria-busy')})),400))}""")
        pg.route("**/api/sesion", lambda rt: (time.sleep(2.5), rt.continue_()))
        pg.locator("button[type=submit]").click()
        pg.wait_for_url(lambda u: "ingresar" not in u, timeout=15000); pg.wait_for_timeout(500)
        est = pg.evaluate("sessionStorage.getItem('__est')")
        chk(w, 5, F, est is not None and json.loads(est)["dis"], "durante la espera: %s" % est)
        chk(w, 9, F, "categorias" in pg.url, "éxito redirige al inicio del rol: %s" % pg.url.replace(BASE, ""))
        # contraseña con borde de espacios con 'Mostrar contraseña' activado
        c.close()
        c, pg = ctx(b, w); ir(pg, "ingresar.html"); cu = []
        pg.on("request", lambda rq: cu.append(rq.post_data) if rq.method == "POST" and "/api/sesion" in rq.url else None)
        pg.fill("#identificador", "x@example.com"); pg.fill("#contrasena", "  abc  ")
        pg.locator("input[type=checkbox]").first.check()
        pg.locator("button[type=submit]").click(); pg.wait_for_timeout(1500)
        pw = json.loads(cu[0])["contrasena"] if cu else None
        chk(w, 2, F, pw == "  abc  ", "contraseña con «Mostrar contraseña» activado se envía tal cual: %r" % pw)
        c.close()
        # P2: cerrar la pestaña/navegador y volver
        c, pg = ctx(b, w); ir(pg, "ingresar.html"); pg.fill("#identificador", D["A"]); pg.fill("#contrasena", "x")
        c.close()
        c, pg = ctx(b, w); ir(pg, "ingresar.html")
        pg.fill("#identificador", D["A"]); pg.fill("#contrasena", D["pwd"]); pg.locator("button[type=submit]").click()
        try:
            pg.wait_for_url(lambda u: "ingresar" not in u, timeout=15000); ok = True
        except Exception: ok = False
        chk(w, "2cierre", F, ok and pg.input_value("#x") if False else ok, "contexto nuevo (cerró el navegador): ingresa de nuevo -> %s" % pg.url.replace(BASE, ""))
        # sesión vigente (pestaña cerrada con sesión viva): abrir ingresar.html otra vez
        estado = c.storage_state(); c.close()
        c2 = b.new_context(storage_state=estado, viewport={"width": w, "height": 740}, ignore_https_errors=True, locale="es-CL"); pg2 = c2.new_page()
        pg2.goto(BASE + "ingresar.html"); pg2.wait_for_load_state("networkidle"); pg2.wait_for_timeout(1000)
        print("   con sesión vigente, ingresar.html ->", pg2.url.replace(BASE, ""), "| form visible:", pg2.locator("#ingresar:visible").count(), "| texto:", pg2.inner_text("main")[:200].replace("\n", " | "))
        chk(w, "2cierre", F, pg2.locator("#ingresar:visible").count() == 1 or "Ya " in pg2.inner_text("main") or "categorias" in pg2.url, "con sesión vigente no queda bloqueado")
        c2.close()
