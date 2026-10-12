"""Ronda 2, punto 3: en «cuenta», botones de una misma sección en una fila que se envuelve (E-3.2), en cada sección."""
from lib2 import *
with sync_playwright() as p:
    b = lanzar(p)
    for w in (360, 1280):
        for quien, secc in (("DUAL", "datos"), ("DUAL", "seguridad"), ("DUAL", "perfiles"), ("CP", "perfiles"), ("C1", "perfiles")):
            c, pg = ctx(b, w); api_login(pg, D[quien]); ir(pg, "cuenta.html#" + secc); pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(500)
            r = pg.evaluate("""()=>{const bs=[...document.querySelectorAll('main button:not([type=submit]),main button[type=submit]')].filter(x=>x.getBoundingClientRect().width>0);const gs=new Map();bs.forEach(x=>{const g=x.parentElement;(gs.get(g)||gs.set(g,[]).get(g)).push(x)});return [...gs].map(([g,l])=>({cls:g.className||g.tagName,disp:getComputedStyle(g).display,wrap:getComputedStyle(g).flexWrap,n:l.length,filas:new Set(l.map(x=>Math.round(x.getBoundingClientRect().top))).size,txt:l.map(x=>x.textContent.trim().slice(0,26)),anchos:l.map(x=>Math.round(x.getBoundingClientRect().width))}))}""")
            print(w, quien, secc, r, "scrollX", pg.evaluate("document.documentElement.scrollWidth>innerWidth"))
            c.close()
    # enlaces de acción de «Mis datos» (#datos .lista-opciones a)
    for w in (360, 1280):
        for quien in ("DUAL", "C1"):
            c, pg = ctx(b, w); api_login(pg, D[quien]); ir(pg, "cuenta.html"); pg.wait_for_timeout(500)
            r = pg.evaluate("""()=>{const l=document.querySelector('#datos .lista-opciones');if(!l)return null;const as=[...l.querySelectorAll('a')].filter(x=>x.getBoundingClientRect().width>0);
              return {disp:getComputedStyle(l).display,wrap:getComputedStyle(l).flexWrap,txt:as.map(x=>x.textContent.trim()),tops:as.map(x=>Math.round(x.getBoundingClientRect().top)),lefts:as.map(x=>Math.round(x.getBoundingClientRect().left)),anchos:as.map(x=>Math.round(x.getBoundingClientRect().width)),h:as.map(x=>Math.round(x.getBoundingClientRect().height)),aw:Math.round(l.getBoundingClientRect().width)}}""")
            print("ENLACES", w, quien, r)
            c.close()
