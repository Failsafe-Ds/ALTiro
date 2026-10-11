from lib2 import *
SUF = "".join(random.choice(string.digits) for _ in range(6))

def avanzar(pg):
    for _ in range(6):
        if pg.locator("button[type=submit]:visible").count(): return
        pg.locator("button:visible:has-text('Continuar')").first.click(); pg.wait_for_timeout(350)

def registro(b, w, tipo):
    form = "registro-cliente" if tipo == "cliente" else "postulacion-maestro"
    sel_form = "#registro-cliente" if tipo == "cliente" else "#postulacion"
    c, pg = ctx(b, w); ir(pg, form + ".html")
    chk(w, 3, form, tipear(pg, "#nombre", 160) == 150, "maxlength nombre 150, tecleando 160")
    chk(w, 3, form, tipear(pg, "#telefono", 40) == 15, "maxlength teléfono 15")
    if tipo == "cliente": chk(w, 3, form, tipear(pg, "#correo", 300) == 254, "maxlength correo 254")
    else: chk(w, 3, form, tipear(pg, "#rut", 30) == 12, "maxlength rut 12")
    pg.click("#telefono"); pg.fill("#telefono", ""); pg.keyboard.type("  +56 9 1234 5678")
    chk(w, 3, form, pg.input_value("#telefono").strip() == "+56 9 1234 5678", "teléfono con 2 espacios iniciales: queda %r (maxlength corta el número)" % pg.input_value("#telefono"))
    pg.fill("#nombre", "     "); pg.fill("#telefono", "+56 9 1234 5678")
    if tipo == "cliente": pg.fill("#correo", "")
    else: pg.fill("#rut", "")
    pg.locator("button:visible:has-text('Continuar')").first.click(); pg.wait_for_timeout(500)
    er = errores(pg, sel_form); ids = [e["id"] for e in er]
    chk(w, 4, form, "error-nombre" in ids and all(e["enVista"] for e in er), "solo espacios en nombre -> %s" % [(e["id"], e["t"][:60], e["enVista"], e["inv"]) for e in er])
    chk(w, 7, form, pg.input_value("#telefono") == "+56 9 1234 5678", "dato faltante no borra el resto (teléfono: %r)" % pg.input_value("#telefono"))
    print("   aviso:", aviso(pg)[:1], "alto ventana", pg.evaluate("innerHeight"), [(e["id"], pg.evaluate("document.getElementById('%s').getBoundingClientRect().top"%e["id"])) for e in er])
    rut = rut_valido(int(SUF) + (1 if tipo == "cliente" else 2) + w)
    pwd = "  " + "-".join("".join(random.choice(string.ascii_letters + string.digits) for _ in range(5)) for _ in range(4)) + "  "
    correo = "qa.pulido.reg%s%d@example.com" % (SUF, w)
    pg.fill("#nombre", "  Qa Pulido %s %d  " % (tipo, w)); pg.fill("#telefono", "  9 1234 %04d  " % (int(SUF) % 10000))
    pg.keyboard.press("Tab"); pg.wait_for_timeout(200)
    chk(w, 2, form, pg.input_value("#nombre") == "Qa Pulido %s %d" % (tipo, w), "al salir del campo se ve recortado: %r" % pg.input_value("#nombre"))
    if tipo == "cliente": pg.fill("#correo", "  " + correo + "  ")
    else: pg.fill("#rut", " " + rut + " ")
    pg.keyboard.press("Tab"); pg.wait_for_timeout(200)
    campo_id = "#correo" if tipo == "cliente" else "#rut"
    chk(w, 2, form, pg.input_value(campo_id) == pg.input_value(campo_id).strip(), "identificador recortado: %r" % pg.input_value(campo_id))
    pg.locator("button:visible:has-text('Continuar')").first.click(); pg.wait_for_timeout(500)
    if tipo == "cliente":
        pg.select_option("#region", index=1); pg.wait_for_timeout(600); pg.select_option("#comuna", index=1)
        pg.locator("button:visible:has-text('Continuar')").first.click(); pg.wait_for_timeout(400)
    else:
        avanzar(pg)
    pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(800)
    antes = pg.locator("button:visible:has-text('Paso anterior')").count()
    if antes:
        pg.locator("button:visible:has-text('Paso anterior')").first.click(); pg.wait_for_timeout(400)
    vals = pg.evaluate("[...document.querySelectorAll('input:not([type=checkbox]):not([type=password]),select')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.id+'='+e.value)")
    chk(w, "2b", form, antes >= 1 and len(vals) > 0, "tras recargar en el paso final, «← Paso anterior» (%d botones) lleva atrás con valores %s" % (antes, vals))
    avanzar(pg)
    pg.fill("#contrasena", pwd)
    if pg.locator("input[type=checkbox]:visible").count(): pg.locator("input[type=checkbox]:visible").first.check()
    h, est = ocupado(pg, "**/api/" + ("clientes" if tipo == "cliente" else "maestros/postulaciones"), "button[type=submit]", lambda: pg.locator("button[type=submit]:visible").click())
    chk(w, 5, form, est["dis"] and (est["busy"] == "true" or pg.evaluate("document.querySelector('form[aria-busy=true]')!==null")), "durante la espera: %s" % est)
    pg.wait_for_timeout(4500)
    texto = pg.inner_text("main"); av = aviso(pg)
    chk(w, 9, form, any(a["role"] in ("alert", "status") for a in av), "mensaje de resultado: %s | main: %r" % (av[:2], texto[:160].replace("\n", " | ")))
    vac = pg.evaluate("[...document.querySelectorAll('input:not([type=checkbox]),textarea')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.id+'='+e.value)")
    chk(w, 8, form, all(v.endswith("=") for v in vac), "campos tras el éxito: %s; borradores: %s" % (vac, claves_borrador(pg)))
    print("   ERRS", [e for e in pg.errs if "401" not in e][:3], pg.http[:4])
    c.close()
    ident = correo if tipo == "cliente" else rut
    c, pg = ctx(b, w); s1 = api_login(pg, ident, pwd)
    cuenta = pg.evaluate("async()=>{const x=await api.obtener('/api/cuenta');return x.datos}") if s1 == 200 else None
    print("   cuenta guardada:", json.dumps(cuenta, ensure_ascii=False)[:400]); c.close()
    c, pg = ctx(b, w); s2 = api_login(pg, ident, pwd.strip()); c.close()
    chk(w, 2, form, s1 == 200 and s2 != 200, "contraseña NO se recorta: login con espacios exactos=%s, recortada=%s" % (s1, s2))

with sync_playwright() as b_:
    b = lanzar(b_)
    for w in (360, 1280):
        for tipo in ("cliente", "maestro"):
            try: registro(b, w, tipo)
            except Exception as e: print("ERROR", w, tipo, repr(e)[:500])
