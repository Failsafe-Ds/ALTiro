from lib2 import *
with sync_playwright() as p:
    b = lanzar(p)
    # DEF-QA-020: campo y mensaje a la vista (mis-servicios, cambiar precio con espacios) a 360x740
    c, pg = ctx(b, 360); api_login(pg, D["M1"]); ir(pg, "mis-servicios.html"); pg.wait_for_timeout(800)
    pg.locator("button:has-text('Cambiar precio')").first.click(); pg.wait_for_timeout(400)
    pg.fill("#cambiar-monto", "     "); pg.locator("button:has-text('Guardar el cambio')").click(); pg.wait_for_timeout(1200)
    print("DEF-020", pg.evaluate("(()=>{const f=document.getElementById('cambiar-monto').getBoundingClientRect(),e=document.getElementById('error-cambiar-monto')||document.querySelector('#cambiar-monto ~ .error, .error-campo');const r=e&&e.getBoundingClientRect();return {campo:[f.top,f.bottom],error:r&&[r.top,r.bottom],alto:innerHeight}})()"))
    c.close()
    # DA-29: precio en resultados
    for w in (360, 1280):
        c, pg = ctx(b, w); ir(pg, "buscar.html?oficio=pintura&region=8&comuna=8101"); pg.wait_for_timeout(1500)
        r = pg.evaluate("(()=>{const t=[...document.querySelectorAll('.precio-tarjeta')];const m=document.documentElement;return {n:t.length,txt:t.slice(0,3).map(x=>x.innerText),desborde:m.scrollWidth>m.clientWidth,w:t[0]&&t[0].getBoundingClientRect().width,font:t[0]&&getComputedStyle(t[0]).fontSize,color:t[0]&&getComputedStyle(t[0]).color,anchoTarjeta:t[0]&&t[0].parentElement.getBoundingClientRect().width}})()")
        print("PRECIO", w, r)
        pg.screenshot(path="/w/precio%d.png" % w)
        c.close()
