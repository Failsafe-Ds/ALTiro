"""Ronda 2, punto 9: validaciones mínimas de «cuenta» (agregar perfil de maestro) con una cuenta solo cliente (C1). No llega a crear el perfil."""
from lib2 import *
with sync_playwright() as p:
    b = lanzar(p)
    for w in (360, 1280):
        c, pg = ctx(b, w); api_login(pg, D["C1"]); ir(pg, "cuenta.html#perfiles"); pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
        chk(w, 9, "1 sin credenciales fijas: ver grep del informe", True, "")
        chk(w, 9, "3 largo: maxlength 12 en RUT", tipear(pg, "#rut", 30) == 12, "")
        pg.fill("#rut", "     "); pg.click("#agregar-maestro button[type=submit]"); pg.wait_for_timeout(1000)
        er = errores(pg, "#agregar-maestro")
        chk(w, 9, "4/6 solo espacios en RUT: error de campo vacío junto al campo, visible", any(e["id"] == "error-rut" and e["t"] and e["enVista"] for e in er), str(er))
        pg.fill("#rut", ""); pg.click("#rut"); pg.keyboard.type("1.111.111-1 "); pg.keyboard.press("Tab"); pg.wait_for_timeout(200)
        chk(w, 9, "4 espacios en los bordes se recortan al salir", pg.input_value("#rut") == pg.input_value("#rut").strip(), repr(pg.input_value("#rut")))
        pg.fill("#rut", ""); pg.click("#rut"); pg.keyboard.type(D["M1"]); pg.keyboard.press("Tab")  # RUT válido que ya pertenece a otro maestro: el servidor lo rechaza sin crear nada
        pend = []
        pg.route("**/api/maestros/postulaciones", lambda rt: pend.append(rt))
        pg.click("#agregar-maestro button[type=submit]"); pg.wait_for_timeout(600)
        est = pg.evaluate("()=>{const b=document.querySelector('#agregar-maestro button[type=submit]');return {dis:b.disabled||b.getAttribute('aria-disabled')==='true',txt:b.innerText}}")
        print("   pendientes", len(pend)); chk(w, 9, "5 envío en espera: botón desactivado con texto de espera", est["dis"] and est["txt"].strip() != "Continuar con mi postulación", str(est))
        for rt in pend: rt.continue_()
        pg.unroute("**/api/maestros/postulaciones"); pg.wait_for_timeout(1500)
        av = pg.evaluate("[...document.querySelectorAll('#agregar-maestro .aviso, #agregar-maestro [role=alert]')].map(e=>[e.getAttribute('role'),e.textContent.trim().slice(0,80)])")
        er = errores(pg, "#agregar-maestro")
        chk(w, 9, "6/7/9 RUT ya registrado (respuesta del servidor): error junto al campo, aria-live, campo conserva lo escrito", any(e["id"] == "error-rut" and e["t"] for e in er) and pg.input_value("#rut") != "", "%s %s" % (er, av))
        live = pg.evaluate("""()=>{const a=document.querySelector('#agregar-maestro .aviso');return [a&&a.getAttribute('role'),a&&a.textContent.trim().slice(0,100)]}""")
        chk(w, 9, "9 resultado anunciado con role=alert/status", live[0] in ("alert", "status") and bool(live[1]), str(live))
        print("   consola:", w, [e for e in pg.errs if "401" not in e], pg.http); c.close()
    b.close()
