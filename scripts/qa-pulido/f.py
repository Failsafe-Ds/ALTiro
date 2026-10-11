from lib2 import *
import urllib.request, statistics
AXE = urllib.request.urlopen("https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.3/axe.min.js").read().decode()
Q = "buscar.html?oficio=pintura&region=8&comuna=8101"
RES = """()=>{
 const m=document.querySelector('main'); const items=[...document.querySelectorAll('#resultados li, .resultados li, main ul li, main article')].filter(e=>e.querySelector('img'));
 const out=[];
 items.slice(0,3).forEach(li=>{const cs=getComputedStyle(li),img=li.querySelector('img'),ir=img.getBoundingClientRect(),
   txt=[...li.querySelectorAll('*')].filter(e=>e.children.length===0&&e.textContent.trim()&&e!==img);
   const primero=txt.map(e=>e.getBoundingClientRect().top).sort((a,b)=>a-b)[0];
   out.push({borde:cs.borderTopWidth+' '+cs.borderTopStyle, sombra:cs.boxShadow.slice(0,30), fondo:cs.backgroundColor, enlaces:li.querySelectorAll('a').length, fotoArriba:ir.bottom<=primero+1, imgSrc:(img.getAttribute('src')||'').replace(/^.*\\/api/,'/api').slice(0,70), imgAlt:img.getAttribute('alt'), w:Math.round(ir.width), h:Math.round(ir.height), texto:li.innerText.split(String.fromCharCode(10)).join(' | ').slice(0,110), estrellas:[...li.querySelectorAll('[aria-label],[title],.sr-only,.solo-lectores')].map(e=>(e.getAttribute('aria-label')||e.getAttribute('title')||e.textContent).slice(0,40)).slice(0,3), a_href:(li.querySelector('a')||{getAttribute:()=>null}).getAttribute('href')})});
 return {n:items.length,out}}"""
with sync_playwright() as b_:
    b = lanzar(b_)
    for w in (360, 1280):
        c, pg = ctx(b, w, 800); ir(pg, "categorias.html")
        cats = pg.evaluate("[...document.querySelectorAll('main a')].map(a=>a.getAttribute('href')+'|'+a.innerText.split(String.fromCharCode(10)).join(' ').slice(0,30))")
        print("w%d categorias: %d enlaces, ejemplos %s" % (w, len(cats), cats[:4]))
        a = pg.locator("main a[href*='buscar.html?oficio=']").first
        href = a.get_attribute("href"); a.click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(900)
        sel = pg.evaluate("[...document.querySelectorAll('select,input')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.id+'='+e.value)")
        chk(w, 5, "categoría→búsqueda", "oficio=" in pg.url and any("oficio" in s and not s.endswith("=") for s in sel), "href %s -> %s ; campos %s" % (href, pg.url.replace(BASE, ""), sel[:4]))
        pg.close() if False else None
        ir(pg, Q); pg.wait_for_timeout(1200)
        r = pg.evaluate(RES); print("   resultados con foto:", r["n"])
        for o in r["out"]: print("   ", json.dumps(o, ensure_ascii=False)[:640])
        if r["out"]:
            o = r["out"][0]
            chk(w, 5, "resultado Fiverr", o["fotoArriba"] and o["enlaces"] == 1 and o["borde"].startswith("0") and o["sombra"] in ("none", "") , "foto arriba=%s, enlaces=%d, borde=%s, sombra=%s, fondo=%s" % (o["fotoArriba"], o["enlaces"], o["borde"], o["sombra"], o["fondo"]))
        print("   errs", [e for e in pg.errs if "401" not in e and "404" not in e][:3], [h for h in pg.http if "foto" not in h][:3])
        c.close()

    print("== RNF-02 (Chromium CDP 4 Mbps bajada, 1 Mbps subida, 150 ms) buscar.html con resultados, contexto nuevo (sin caché)")
    tiempos = []; tams = []
    for i in range(6):
        c, pg = ctx(b, 360, 740, lento=True)
        tot = [0]; cdp = c.new_cdp_session(pg); cdp.send("Network.enable")
        cdp.on("Network.loadingFinished", lambda e: tot.__setitem__(0, tot[0] + e["encodedDataLength"]))
        t = time.time(); pg.goto(BASE + Q); pg.wait_for_load_state("load"); t_load = time.time() - t
        pg.wait_for_function("document.querySelectorAll('main img').length>0", timeout=15000); pg.wait_for_load_state("networkidle"); t_idle = time.time() - t
        tiempos.append((t_load, t_idle)); tams.append(tot[0])
        c.close()
    print("   tiempos load  :", ["%.2f" % x[0] for x in tiempos])
    print("   tiempos idle  :", ["%.2f" % x[1] for x in tiempos])
    print("   bytes transferidos (KiB):", [t // 1024 for t in tams])
    chk(360, "RNF-02", "buscar.html", max(tams) <= 1.5 * 1024 * 1024 and max(x[1] for x in tiempos) <= 3.0, "máx %.0f KiB (umbral 1536 KiB), máx tiempo (red inactiva) %.2f s, máx load %.2f s (umbral 3 s)" % (max(tams) / 1024, max(x[1] for x in tiempos), max(x[0] for x in tiempos)))
    # desglose
    c, pg = ctx(b, 360, 740, lento=True); reg = []
    pg.on("response", lambda r: reg.append((r.url.replace(BASE, "/")[:70], r.headers.get("content-length", "?"), r.headers.get("content-encoding", ""))))
    pg.goto(BASE + Q); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(800)
    imgs = [x for x in reg if "foto" in x[0]]; print("   archivos:", len(reg), "fotos:", len(imgs), "tamaño de foto típico:", imgs[:2], "| fuentes:", [x for x in reg if "fuentes" in x[0]][:2]); c.close()

    print("== RNF-16 axe (wcag2a/aa; color-contrast aparte)")
    casos = [("index.html", None), (Q, None), ("cuenta.html", "M1"), ("curatoria.html", "CUR"), ("categorias.html", None), ("moderacion.html", "MOD"), ("mis-trabajos.html", "M1")]
    for w in (360, 1280):
        for ruta, quien in casos:
            c, pg = ctx(b, w, 800)
            if quien: api_login(pg, D[quien])
            ir(pg, ruta); pg.wait_for_timeout(1200)
            pg.evaluate(AXE)
            v = pg.evaluate("""async()=>{const r=await axe.run(document,{runOnly:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']});
              const cc=r.violations.find(v=>v.id==='color-contrast'); const pas=r.passes.find(v=>v.id==='color-contrast');
              return {viol:r.violations.map(v=>v.id+':'+v.nodes.length), contrastePases: pas?pas.nodes.length:0, contrasteFallas: cc? cc.nodes.map(n=>n.any[0]&&n.any[0].message.slice(0,90)).slice(0,2):0, incompletos:(r.incomplete.find(v=>v.id==='color-contrast')||{nodes:[]}).nodes.length}}""")
            print("w%d %-34s %s" % (w, ruta[:34], json.dumps(v, ensure_ascii=False)[:420]))
            c.close()
