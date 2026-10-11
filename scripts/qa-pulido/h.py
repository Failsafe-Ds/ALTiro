from lib2 import *
with sync_playwright() as b_:
    b = lanzar(b_)
    for w in (360, 1280):
        c, pg = ctx(b, w, 800); print(api_login(pg, D["M4"])); ir(pg, "mi-postulacion.html"); pg.wait_for_timeout(900)
        print(w, "inicio:", [x for x in campos(pg)][:10], "|", pg.inner_text("main")[:150].replace("\n", " | "))
        pg.locator('input[type=checkbox]').nth(4).check()
        # avanzar hasta un paso con «Paso anterior»
        for _ in range(4):
            if pg.locator("button:visible:has-text('Paso anterior')").count(): break
            bt = pg.locator("main button:visible:not(:has-text('Menú'))").first
            if not bt.count(): break
            print("  clic:", bt.inner_text()[:40]); bt.click(); pg.wait_for_timeout(700)
        n0 = pg.locator("button:visible:has-text('Paso anterior')").count(); h0 = pg.inner_text("main")[:80].replace("\n", " | ")
        pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(900)
        n1 = pg.locator("button:visible:has-text('Paso anterior')").count()
        if n1:
            pg.locator("button:visible:has-text('Paso anterior')").first.click(); pg.wait_for_timeout(500)
        print("  antes:", n0, h0, "| tras recargar botón:", n1, "| tras clic:", pg.inner_text("main")[:80].replace("\n", " | "))
        c.close()
