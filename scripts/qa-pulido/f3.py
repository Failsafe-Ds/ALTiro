from lib2 import *
Q = "buscar.html?oficio=pintura&region=8&comuna=8101"
with sync_playwright() as b_:
    b = lanzar(b_)
    c, pg = ctx(b, 360, 740); api_login(pg, D["M1"]); ir(pg, "mi-perfil.html"); pg.wait_for_timeout(800)
    # JPEG de mucha entropía (peor caso) 1600x1200 generado en el navegador
    data = pg.evaluate("""async()=>{const c=document.createElement('canvas');c.width=1600;c.height=1200;const x=c.getContext('2d');const im=x.createImageData(1600,1200);
      for(let i=0;i<im.data.length;i+=4){im.data[i]=Math.random()*255;im.data[i+1]=Math.random()*255;im.data[i+2]=Math.random()*255;im.data[i+3]=255}
      x.putImageData(im,0,0);const b=await new Promise(r=>c.toBlob(r,'image/jpeg',0.92));const a=new Uint8Array(await b.arrayBuffer());return Array.from(a)}""")
    open("/tmp/ruido.jpg", "wb").write(bytes(data)); print("JPEG de entrada (ruido 1600x1200):", len(data) // 1024, "KiB")
    pg.set_input_files("#selector-foto input[type=file]", "/tmp/ruido.jpg"); pg.wait_for_timeout(2500)
    pg.click("#guardar-foto"); pg.wait_for_timeout(4000)
    print("aviso:", [a["t"] for a in aviso(pg)][:2], "| progreso:", pg.inner_text("#progreso-foto")[:80])
    for t in (160, 480):
        r = pg.evaluate("async(u)=>{const r=await fetch(u);const b=await r.arrayBuffer();return [r.status,b.byteLength,r.headers.get('content-type')]}", "/api/maestros/publicos/%s/foto?tam=%d" % (D["m1_pub"], t))
        print("foto tam=%d ->" % t, r)
    c.close()
    tiempos = []; tams = []
    for i in range(6):
        c, pg = ctx(b, 360, 740, lento=True); tot = [0]; cdp = c.new_cdp_session(pg); cdp.send("Network.enable")
        cdp.on("Network.loadingFinished", lambda e: tot.__setitem__(0, tot[0] + e["encodedDataLength"]))
        t = time.time(); pg.goto(BASE + Q); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300); dt = time.time() - t - 0.3
        tiempos.append(dt); tams.append(tot[0]); c.close()
    print("con foto real de peor caso en el primer resultado: tiempos", ["%.2f" % x for x in tiempos], "KiB", [t // 1024 for t in tams])
