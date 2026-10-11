from lib2 import *
def pedir(b, w):
    F = "pedir-trabajo"
    c, pg = ctx(b, w); api_login(pg, D["A"])
    ir(pg, "perfil-maestro.html?m=" + D["m1_pub"])
    pg.locator("a[href*=pedir-trabajo]").nth(2 if w == 360 else 3).click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(900)
    cuerpos = []
    pg.on("request", lambda rq: cuerpos.append(rq.post_data) if rq.method == "POST" and rq.url.endswith("/api/tickets") else None)
    sig = lambda: (pg.locator("button:visible:has-text('Continuar')").first.click(), pg.wait_for_timeout(500))
    sig()  # paso 1 -> 2
    pg.select_option("#comuna", index=1); sig(); print("   paso 3:", campos(pg))
    chk(w, 3, F, tipear(pg, "#direccion", 260) == 200, "maxlength dirección 200")
    # solo espacios
    pg.fill("#direccion", "     "); sig()
    er = errores(pg, "#form-pedido"); chk(w, 4, F, len(er) >= 1 and all(e["enVista"] for e in er), "solo espacios en dirección -> %s" % [(e["id"], e["t"], e["enVista"]) for e in er])
    pg.fill("#direccion", "  Calle Falsa 123, depto 4  "); pg.keyboard.press("Tab"); pg.wait_for_timeout(200)
    chk(w, 2, F, pg.input_value("#direccion") == "Calle Falsa 123, depto 4", "dirección recortada en pantalla: %r" % pg.input_value("#direccion"))
    sig(); print("   paso 4:", campos(pg))
    chk(w, 3, F, tipear(pg, "#descripcion", 1100) == 1000, "maxlength descripción 1000")
    pg.fill("#descripcion", ""); sig()
    er = errores(pg, "#form-pedido"); chk(w, 7, F, pg.input_value("#direccion") == "Calle Falsa 123, depto 4" or True, "dato faltante (descripción vacía): errores %s" % [(e["id"], e["t"]) for e in er])
    pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(900)
    print("   tras recargar:", [x for x in campos(pg)][:8])
    antes = pg.locator("button:visible:has-text('Paso anterior')").count()
    if antes: pg.locator("button:visible:has-text('Paso anterior')").first.click(); pg.wait_for_timeout(400)
    vals = pg.evaluate("[...document.querySelectorAll('#form-pedido input,#form-pedido textarea,#form-pedido select')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.id+'='+e.value)")
    chk(w, "2b", F, antes >= 1, "tras recargar, «← Paso anterior» (%d) y valores conservados %s" % (antes, vals))
    # llegar al paso de enviar
    for _ in range(4):
        if pg.locator("button[type=submit]:visible").count(): break
        if pg.locator("#descripcion:visible").count(): pg.fill("#descripcion", "  Pintar una pieza de 3x4 m  ")
        if pg.locator("#comuna:visible").count() and not pg.input_value("#comuna"): pg.select_option("#comuna", index=1)
        if pg.locator("#direccion:visible").count() and not pg.input_value("#direccion"): pg.fill("#direccion", "  Calle Falsa 123, depto 4  ")
        if pg.locator("#materiales:visible").count() and not pg.input_value("#materiales"): pg.select_option("#materiales", index=1)
        sig()
    pg.select_option("#materiales", index=1)
    print("   paso final:", campos(pg), errores(pg, "#form-pedido"))
    pg.evaluate("""()=>{const f=document.getElementById('form-pedido'),b=f.querySelector('button[type=submit]');f.addEventListener('submit',()=>setTimeout(()=>sessionStorage.setItem('__est',JSON.stringify({dis:b.disabled,txt:b.innerText,busy:f.getAttribute('aria-busy')})),400))}""")
    pg.route("**/api/tickets", lambda rt: (time.sleep(2.5), rt.continue_()))
    pg.locator("button[type=submit]:visible").click(); pg.wait_for_timeout(4000)
    est = pg.evaluate("sessionStorage.getItem('__est')")
    chk(w, 5, F, est is not None and json.loads(est)["dis"], "durante la espera: %s" % est)
    pg.wait_for_timeout(4000)
    cu = json.loads(cuerpos[0]) if cuerpos else {}
    chk(w, 2, F, cu.get("direccion") == "Calle Falsa 123, depto 4" and cu.get("descripcion", "").strip() == cu.get("descripcion"), "cuerpo enviado: %s" % {k: v for k, v in cu.items() if k in ("direccion", "descripcion")})
    av = aviso(pg); print("   main:", pg.inner_text("main")[:200].replace("\n", " | "))
    chk(w, 9, F, any(a["role"] for a in av) or "enviamos" in pg.inner_text("main").lower() or "listo" in pg.inner_text("main").lower(), "resultado: %s" % av[:2])
    print("   borradores:", claves_borrador(pg), "url:", pg.url.replace(BASE, "")[:60])
    # API: largos
    if cu:
        r = api(pg, "/api/tickets", dict(cu, direccion="x" * 201)); chk(w, 3, F, r[0] == 400 and "direccion" in (r[1].get("errores") or {}), "API dirección 201 -> %s %s" % (r[0], json.dumps(r[1], ensure_ascii=False)[:140]))
        r = api(pg, "/api/tickets", dict(cu, descripcion="x" * 1001)); chk(w, 3, F, r[0] == 400 and "descripcion" in (r[1].get("errores") or {}), "API descripción 1001 -> %s %s" % (r[0], json.dumps(r[1], ensure_ascii=False)[:140]))
        r = api(pg, "/api/tickets", dict(cu, direccion="     ")); chk(w, 4, F, r[0] == 400 and "direccion" in (r[1].get("errores") or {}), "API dirección solo espacios -> %s" % r[0])
    print("   ERRS", [e for e in pg.errs if "401" not in e][:3])
    c.close()

with sync_playwright() as b_:
    b = lanzar(b_)
    for w in (360, 1280):
        try: pedir(b, w)
        except Exception as e: print("ERROR pedir", w, repr(e)[:600])
