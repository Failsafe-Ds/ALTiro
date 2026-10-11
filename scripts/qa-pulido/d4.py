from lib2 import *
EST = """(sel,btn)=>{const f=document.querySelector(sel),b=f.querySelector(btn);f.addEventListener('submit',()=>setTimeout(()=>sessionStorage.setItem('__est',JSON.stringify({dis:b.disabled,txt:b.innerText,busy:f.getAttribute('aria-busy')})),400))}"""

def servicios(b, w):
    F = "mis-servicios (monto)"
    c, pg = ctx(b, w); api_login(pg, D["M1"]); ir(pg, "mis-servicios.html")
    pg.locator("button:has-text('Cambiar precio')").first.click(); pg.wait_for_timeout(500)
    chk(w, 3, F, tipear(pg, "#cambiar-monto", 30) == 12, "maxlength monto 12")
    pg.fill("#cambiar-monto", "     "); pg.locator("button:has-text('Guardar el cambio')").click(); pg.wait_for_timeout(500)
    er = errores(pg); chk(w, 4, F, len(er) >= 1 and all(e["enVista"] for e in er), "solo espacios -> %s" % [(e["id"], e["t"], e["enVista"]) for e in er])
    pg.fill("#cambiar-monto", "99999999999"); pg.locator("button:has-text('Guardar el cambio')").click(); pg.wait_for_timeout(500)
    er = errores(pg); chk(w, 6, F, len(er) >= 1, "monto sobre el máximo -> %s | valor conservado %r" % ([e["t"] for e in er], pg.input_value("#cambiar-monto")))
    chk(w, 7, F, pg.input_value("#cambiar-monto") == "99999999999", "no borra lo escrito tras el error")
    nuevo = "  $ 2%d.000  " % (6 if w == 360 else 7)
    pg.fill("#cambiar-monto", nuevo); pg.keyboard.press("Tab"); pg.wait_for_timeout(200)
    chk(w, 2, F, pg.input_value("#cambiar-monto") == nuevo.strip(), "monto recortado en pantalla: %r" % pg.input_value("#cambiar-monto"))
    form_sel = "form:has(#cambiar-monto)"
    pg.evaluate("(s)=>{const f=document.querySelector(s),b=f.querySelector('button[type=submit]');f.addEventListener('submit',()=>setTimeout(()=>sessionStorage.setItem('__est',JSON.stringify({dis:b.disabled,txt:b.innerText,busy:f.getAttribute('aria-busy')})),400))}", form_sel)
    pg.route("**/api/**/servicios/**", lambda rt: (time.sleep(2.5), rt.continue_()))
    pg.route("**/api/maestros/**", lambda rt: (time.sleep(2.5), rt.continue_()) if rt.request.method in ("PATCH", "PUT", "POST") else rt.continue_())
    pg.locator("button:has-text('Guardar el cambio')").click(); pg.wait_for_timeout(4500)
    est = pg.evaluate("sessionStorage.getItem('__est')")
    chk(w, 5, F, est is not None and json.loads(est)["dis"], "durante la espera: %s" % est)
    av = aviso(pg); print("   avisos:", av[:3])
    chk(w, 9, F, any(a["role"] for a in av), "mensaje de resultado con role: %s" % [(a["t"][:60], a["role"]) for a in av[:2]])
    print("   precio visible:", [t for t in pg.inner_text("main").split("\n") if "$" in t][:3])
    # API: largos y espacios
    ref = pg.evaluate("async()=>{const x=await api.obtener('/api/maestros/yo/servicios');return JSON.stringify(x.datos).slice(0,300)}")
    print("   lista servicios:", ref[:300])
    # paso anterior en agregar
    pg.unroute_all() if hasattr(pg, "unroute_all") else None
    pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(700)
    pg.click("#abrir-agregar"); pg.wait_for_timeout(400)
    pg.locator("input[name=oficio], #form-agregar input[type=radio]").first.check()
    pg.click("#agregar-siguiente"); pg.wait_for_timeout(500)
    print("   agregar paso 2:", [x for x in campos(pg) if "agregar" in x or "nuevo" in x or "Paso" in x])
    pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(700)
    print("   tras recargar:", [x for x in campos(pg) if "agregar" in x or "nuevo" in x or "Paso" in x])
    print("   ERRS", [e for e in pg.errs if "401" not in e][:3])
    c.close()

with sync_playwright() as b_:
    b = lanzar(b_)
    for w in (360, 1280):
        try: servicios(b, w)
        except Exception as e: print("ERROR servicios", w, repr(e)[:600])
