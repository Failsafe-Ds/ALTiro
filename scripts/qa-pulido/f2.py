from lib2 import *
Q = "buscar.html?oficio=pintura&region=8&comuna=8101"
with sync_playwright() as b_:
    b = lanzar(b_)
    c, pg = ctx(b, 360, 740, lento=True); ir(pg, Q); pg.wait_for_timeout(1000)
    print(pg.evaluate("[...document.querySelectorAll('main img')].slice(0,3).map(i=>i.getAttribute('src')+' loading='+i.loading+' w='+i.getAttribute('width')+' h='+i.getAttribute('height')+' nat='+i.naturalWidth+'x'+i.naturalHeight)"))
    print("imgs total", pg.locator("main img").count())
    srcs = pg.evaluate("[...document.querySelectorAll('main img')].map(i=>i.getAttribute('src'))")
    tam = []
    for s in srcs[:20]:
        r = pg.evaluate("async(u)=>{const r=await fetch(u);const b=await r.arrayBuffer();return [r.status,b.byteLength,r.headers.get('content-type')]}", s); tam.append(r)
    print("tamaños de las 20 fotos:", [t[1] for t in tam], tam[0][2])
    # scroll a todo el listado y medir transferencia total
    c.close()
    c, pg = ctx(b, 360, 740, lento=True); tot = [0]; cdp = c.new_cdp_session(pg); cdp.send("Network.enable")
    cdp.on("Network.loadingFinished", lambda e: tot.__setitem__(0, tot[0] + e["encodedDataLength"]))
    pg.goto(BASE + Q); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(500)
    a = tot[0]
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(2500); pg.wait_for_load_state("networkidle")
    print("primera pantalla KiB:", a // 1024, "| tras bajar hasta el final KiB:", tot[0] // 1024)
