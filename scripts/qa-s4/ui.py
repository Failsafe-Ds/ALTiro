import sys, json, socket, threading, datetime
from playwright.sync_api import sync_playwright
host=sys.argv[1]; REF=sys.argv[2]; FECHA=sys.argv[3]; tag=sys.argv[4]
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
ESTADOS={
 "buscar-inicial":"/buscar.html",
 "buscar-resultados":"/buscar.html?oficio=cerrajeria&region=8&comuna=8111",
 "buscar-sugerencias":"/buscar.html?oficio=cerrajeria&region=8&comuna=8111&fecha=%s&inicio=03:00&fin=04:00"%FECHA,
 "buscar-sin-nada":"/buscar.html?oficio=gas&region=8&comuna=8101",
 "ficha":"/perfil-maestro.html?m=%s"%REF,
 "ficha-inexistente":"/perfil-maestro.html?m=00000000-0000-4000-8000-000000000000",
}
JS="""()=>{
 const W=document.documentElement.clientWidth, out={scroll:document.documentElement.scrollWidth,W:W,fuera:[],chicos:[],texto:document.body.innerText};
 const vis=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 document.querySelectorAll('body *').forEach(e=>{ if(!vis(e))return; const r=e.getBoundingClientRect(); if(r.right>W+1||r.left<-1) out.fuera.push(e.tagName+'.'+e.className+':'+Math.round(r.left)+'-'+Math.round(r.right)); });
 document.querySelectorAll('button,a[href],input:not([type=hidden]),select,textarea,summary,label.casilla,label.casilla-grande').forEach(e=>{ if(!vis(e))return; const s=getComputedStyle(e); const r=e.getBoundingClientRect(); const inl=(e.tagName==='A'&&s.display==='inline'); if((r.width<44||r.height<44)){ out.chicos.push((inl?'[en linea] ':'')+e.tagName+'.'+e.className+' '+Math.round(r.width)+'x'+Math.round(r.height)+' '+(e.innerText||e.name||'').slice(0,30)); } });
 return out;}"""
res={}
with sync_playwright() as p:
    for motor in ("chromium","firefox"):
        b=getattr(p,motor).launch(args=["--ignore-certificate-errors","--host-resolver-rules=MAP localhost 127.0.0.1"] if motor=="chromium" else [], firefox_user_prefs={"network.dns.localDomains":"localhost"} if motor=="firefox" else None)
        print(motor, b.version)
        for ancho in (320,390):
            kw=dict(viewport={"width":ancho,"height":800},has_touch=True,locale="es-CL",ignore_https_errors=True)
            if motor=="chromium": kw["is_mobile"]=True
            for nombre,ruta in ESTADOS.items():
                ctx=b.new_context(**kw); pg=ctx.new_page(); errs=[]
                pg.on("pageerror",lambda e: errs.append(str(e)[:120]))
                pg.on("console",lambda m: errs.append("console:"+m.text[:100]) if m.type=="error" and "status of 4" not in m.text and "404" not in m.text else None)
                pg.goto("https://localhost"+ruta); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(700)
                if nombre=="ficha":
                    # elegir un servicio para ver bloques
                    r=pg.locator("#opciones-servicio input").first
                    if r.count(): r.check(); pg.wait_for_timeout(600)
                o=pg.evaluate(JS)
                malo=o["scroll"]>o["W"] or len(o["fuera"])>0
                nchic=[c for c in o["chicos"] if not c.startswith("[en linea]")]
                print("%s %d %-20s scroll=%d/%d fuera=%d chicos=%d enlinea=%d errores=%d"%(motor,ancho,nombre,o["scroll"],o["W"],len(o["fuera"]),len(nchic),len(o["chicos"])-len(nchic),len(errs)))
                for c in nchic[:6]: print("    chico:",c)
                for c in o["fuera"][:3]: print("    fuera:",c)
                for e in errs[:3]: print("    err:",e)
                if ancho==390 and motor=="chromium": res[nombre]=o["texto"]
                ctx.close()
        b.close()
json.dump(res,open("/out/textos-%s.json"%tag,"w"),ensure_ascii=False,indent=1)
