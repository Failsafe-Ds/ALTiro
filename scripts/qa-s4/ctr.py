import sys, socket, threading
from playwright.sync_api import sync_playwright
host=sys.argv[1]; REF=sys.argv[2]; FECHA=sys.argv[3]
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
E={"buscar-inicial":"/buscar.html","buscar-resultados":"/buscar.html?oficio=cerrajeria&region=8&comuna=8111","buscar-sugerencias":"/buscar.html?oficio=cerrajeria&region=8&comuna=8111&fecha=%s&inicio=03:00&fin=04:00"%FECHA,"buscar-sin-nada":"/buscar.html?oficio=gas&region=8&comuna=8101","ficha":"/perfil-maestro.html?m="+REF}
JS="""()=>{
const pr=c=>{const m=c.match(/[\d.]+/g).map(Number);return {r:m[0],g:m[1],b:m[2],a:m.length>3?m[3]:1}};
const lum=({r,g,b})=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)};
const over=(t,u)=>({r:t.r*t.a+u.r*(1-t.a),g:t.g*t.a+u.g*(1-t.a),b:t.b*t.a+u.b*(1-t.a),a:1});
const bg=e=>{let cs=[];for(let x=e;x;x=x.parentElement){const c=pr(getComputedStyle(x).backgroundColor);if(c.a>0)cs.push(c);if(c.a>=1)break}let base={r:255,g:255,b:255,a:1};for(let i=cs.length-1;i>=0;i--)base=over(cs[i],base);return base};
const out=[];const seen=new Set();
const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
while(w.nextNode()){const n=w.currentNode;if(!n.textContent.trim())continue;const e=n.parentElement;const s=getComputedStyle(e);const r=e.getBoundingClientRect();if(r.width<=0||s.visibility==='hidden'||s.display==='none')continue;
 const f=over(pr(s.color),bg(e));const b=bg(e);const L1=lum(f),L2=lum(b);const ratio=(Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
 const px=parseFloat(s.fontSize),bold=parseInt(s.fontWeight)>=700;const grande=px>=24||(px>=18.66&&bold);const k=e.tagName+'.'+e.className+'|'+s.color+'|'+s.backgroundColor;if(seen.has(k))continue;seen.add(k);
 out.push({el:e.tagName+'.'+e.className,ratio:Math.round(ratio*100)/100,min:grande?3:4.5,txt:n.textContent.trim().slice(0,28)});}
return out;}"""
with sync_playwright() as p:
    b=p.chromium.launch(args=["--ignore-certificate-errors","--host-resolver-rules=MAP localhost 127.0.0.1"])
    for n,ruta in E.items():
        ctx=b.new_context(viewport={"width":390,"height":800},is_mobile=True,has_touch=True,ignore_https_errors=True); pg=ctx.new_page()
        pg.goto("https://localhost"+ruta); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(600)
        if n=="ficha":
            r=pg.locator("#opciones-servicio input").first
            if r.count(): r.check(); pg.wait_for_timeout(500)
        o=pg.evaluate(JS); malos=[x for x in o if x["ratio"]<x["min"]]
        print(n,"pares:",len(o),"min:",min(x["ratio"] for x in o),"bajo umbral:",malos)
        ctx.close()
