from lib import *
PAGS = ["cuenta.html","mi-perfil.html","mis-servicios.html","mi-cobertura.html","mi-agenda.html","mis-documentos.html","mi-postulacion.html"]
INFO = """()=>{const n=document.querySelector('nav.opciones-menu'), m=document.querySelector('main'); if(!n) return null;
 const r=n.getBoundingClientRect(), c=document.querySelector('.opciones-contenido').getBoundingClientRect(), vis=r.width>0;
 const act=[...n.querySelectorAll('a[aria-current]')].map(a=>a.getAttribute('aria-current')+':'+a.textContent.trim()+':'+a.getAttribute('href'));
 const links=[...n.querySelectorAll('a')].map(a=>a.textContent.trim()+(a.getBoundingClientRect().width>0?'':'(oculto)'));
 const pl=n.querySelector('.opciones-plegable');
 return {izq: Math.round(r.left), arriba: Math.round(r.top), w: Math.round(r.width), contenidoLeft: Math.round(c.left), contenidoTop: Math.round(c.top), lateral: c.left>=r.right-1, encima: c.top>=r.bottom-1, act, links, plegable: pl? pl.tagName+':'+(pl.open===undefined?'':pl.open):null, scrollX: document.documentElement.scrollWidth>document.documentElement.clientWidth}}"""
with sync_playwright() as p:
    b = lanzar(p)
    for w in (360, 1280):
        c, pg = ctx(b, w, 800); api_login(pg, D["M1"])
        for r in PAGS:
            ir(pg, r, True); pg.wait_for_timeout(600)
            i = pg.evaluate(INFO); print("w%d %-18s"%(w,r), i)
        # teclado en 'mi-cobertura'
        ir(pg, "cuenta.html"); pg.wait_for_timeout(600)
        if w < 768:
            # abrir menú plegable con teclado
            pl = pg.locator(".opciones-plegable"); print("   plegable:", pl.evaluate("e=>e.outerHTML.slice(0,160)"))
        # tab hasta un enlace del menú lateral
        pg.keyboard.press("Tab"); seen=[]
        for k in range(30):
            f = pg.evaluate("(()=>{const e=document.activeElement;return e? e.tagName+':'+(e.textContent||'').trim().slice(0,22)+':'+(e.closest('nav.opciones-menu')?'NAV':'')+':'+(e.getAttribute('href')||''):''})()")
            seen.append(f)
            if f.endswith(':NAV:mi-cobertura.html') or 'mi-cobertura.html' in f: break
            pg.keyboard.press("Tab")
        print("   tab recorre:", [s for s in seen if 'NAV' in s][:8])
        if 'mi-cobertura.html' in seen[-1]:
            pg.keyboard.press("Enter"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(700)
            print("   Enter ->", pg.url.replace(BASE,""), pg.evaluate(INFO)["act"] if pg.evaluate(INFO) else None)
        else: print("   FAIL no se alcanzó con Tab; vistos:", seen[-4:])
        print("   http:", pg.http[:3], "errs:", [e for e in pg.errs if "401" not in e][:3])
        c.close()
