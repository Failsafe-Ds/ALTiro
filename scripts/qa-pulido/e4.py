from lib2 import *
with sync_playwright() as b_:
    b = lanzar(b_)
    for h in (740, 640):
        c, pg = ctx(b, 360, h); api_login(pg, D["M1"]); ir(pg, "mis-servicios.html")
        pg.locator("button:has-text('Cambiar precio')").first.click(); pg.wait_for_timeout(500)
        pg.fill("#cambiar-monto", "     "); pg.locator("button:has-text('Guardar el cambio')").click(); pg.wait_for_timeout(600)
        print(h, pg.evaluate("(()=>{const e=document.getElementById('error-cambiar-monto').getBoundingClientRect(),i=document.getElementById('cambiar-monto').getBoundingClientRect();return {errTop:e.top,errBottom:e.bottom,campoTop:i.top,campoBottom:i.bottom,vh:innerHeight,sy:scrollY,foco:document.activeElement.id}})()"))
        c.close()
    # agregar: paso anterior funcional tras recargar
    c, pg = ctx(b, 360); api_login(pg, D["M1"]); ir(pg, "mis-servicios.html")
    pg.click("#abrir-agregar"); pg.wait_for_timeout(400)
    pg.locator("#form-agregar input[type=radio]").first.check(); pg.click("#agregar-siguiente"); pg.wait_for_timeout(500)
    pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(900)
    vis = pg.locator("#agregar-atras:visible").count(); print("tras recargar atrás visible:", vis, "nuevo-monto visible:", pg.locator("#nuevo-monto:visible").count())
    if vis: pg.click("#agregar-atras"); pg.wait_for_timeout(400); print("después de Paso anterior: radios visibles:", pg.locator("#form-agregar input[type=radio]:visible").count(), "checked:", pg.evaluate("[...document.querySelectorAll('#form-agregar input[type=radio]')].filter(r=>r.checked).length"))
    c.close()
