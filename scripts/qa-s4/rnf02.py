import sys, json, statistics, subprocess, time
from playwright.sync_api import sync_playwright
import socket, threading
etq, ruta, corridas, espera = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
host = sys.argv[5]  # proxy host
# reenvio 127.0.0.1:443 -> proxy:443
def pipe(a,b):
    try:
        while True:
            d=a.recv(65536)
            if not d: break
            b.sendall(d)
    except Exception: pass
    finally:
        for s in (a,b):
            try: s.close()
            except Exception: pass
srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1); srv.bind(("127.0.0.1",443)); srv.listen(50)
def acc():
    while True:
        c,_=srv.accept(); u=socket.create_connection((host,443))
        threading.Thread(target=pipe,args=(c,u),daemon=True).start(); threading.Thread(target=pipe,args=(u,c),daemon=True).start()
threading.Thread(target=acc,daemon=True).start()
INIT = """
(function(){ 
 function ok(){ try{ return (%s);}catch(e){return false;} }
 const t=()=>{ if(ok()){ performance.mark('listo'); } else requestAnimationFrame(t); };
 document.addEventListener('DOMContentLoaded',()=>requestAnimationFrame(t));
})();""" % espera
res=[]
with sync_playwright() as p:
    b=p.chromium.launch(args=["--ignore-certificate-errors","--host-resolver-rules=MAP localhost 127.0.0.1"])
    for i in range(corridas+1):
        ctx=b.new_context(viewport={"width":390,"height":800},is_mobile=True,has_touch=True,bypass_csp=True,locale="es-CL",ignore_https_errors=True)
        pg=ctx.new_page(); pg.add_init_script(INIT)
        cdp=ctx.new_cdp_session(pg)
        cdp.send("Network.enable"); cdp.send("Network.setCacheDisabled",{"cacheDisabled":True})
        cdp.send("Network.emulateNetworkConditions",{"offline":False,"latency":150,"downloadThroughput":500000,"uploadThroughput":125000})
        enc=[0]
        cdp.on("Network.loadingFinished",lambda e: enc.__setitem__(0,enc[0]+e["encodedDataLength"]))
        t0=time.time()
        pg.goto("https://localhost"+ruta,wait_until="commit")
        pg.wait_for_function("performance.getEntriesByName('listo').length>0",timeout=30000)
        pared=time.time()-t0
        listo=pg.evaluate("performance.getEntriesByName('listo')[0].startTime")
        pg.wait_for_timeout(1500)
        ts=pg.evaluate("""()=>{const n=performance.getEntriesByType('navigation')[0];let s=n.transferSize;const rs=performance.getEntriesByType('resource');rs.forEach(r=>s+=r.transferSize);return [s,rs.length+1]}""")
        if i>0: res.append((listo/1000,pared,ts[0],enc[0],ts[1]))
        ctx.close()
    b.close()
print(etq,ruta)
for r in res: print("listo %.3f s  pared %.3f s  transfer %d  cdp %d  peticiones %d"%r)
print("mediana listo %.3f max %.3f ; bytes max %d (%.1f KiB)"%(statistics.median(r[0] for r in res),max(r[0] for r in res),max(r[2] for r in res),max(r[2] for r in res)/1024))
