from lib2 import *
with sync_playwright() as b_:
    b = lanzar(b_)
    for w in (360, 1280):
        c, pg = ctx(b, w, 800); ir(pg, "buscar.html?oficio=pintura&region=8&comuna=8101"); pg.wait_for_timeout(1500)
        pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(2500)
        r = pg.evaluate("[...document.querySelectorAll('main img')].filter(i=>i.complete&&i.naturalWidth===0).map(i=>i.closest('li,article').innerText.split(String.fromCharCode(10))[0]+' | '+i.currentSrc.slice(-40)+' | dpr='+devicePixelRatio)")
        print("w%d fotos rotas:" % w, r, "| total", pg.locator("main img").count(), [h for h in pg.http if 'foto' in h][:3])
        c.close()
