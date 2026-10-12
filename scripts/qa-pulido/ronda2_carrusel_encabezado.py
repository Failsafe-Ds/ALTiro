"""Ronda 2 (v0.6.3), puntos 6, 8 (categorías y búsqueda) y 10 (consola y axe): carrusel (E-3.3), encabezado con degradado, «Otros servicios» (DA-31)."""
from lib2 import *
import urllib.request
AXE = urllib.request.urlopen("https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.3/axe.min.js").read().decode()
def axe(pg, w, ruta):
    pg.evaluate(AXE)
    r = pg.evaluate("""async()=>{const r=await axe.run(document,{runOnly:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']});
      return {v:r.violations.map(v=>v.id+':'+v.nodes.length+':'+v.nodes.slice(0,2).map(n=>n.target.join(' ')).join('|')),inc:r.incomplete.length,pasa:r.passes.length,
      cont:(r.passes.find(p=>p.id==='color-contrast')||{nodes:[]}).nodes.length}}""")
    chk(w, 10, "axe " + ruta, not r["v"], "violaciones=%s incompletos=%d contraste aprobados=%d" % (r["v"], r["inc"], r["cont"]))
def contraste_marca(pg):
    """Contraste de la marca y del botón «Menú» contra el tono más oscuro del degradado (#FBE4E7)."""
    return pg.evaluate(r"""()=>{const L=c=>{c=c.map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*c[0]+.7152*c[1]+.0722*c[2]};
      const rgb=s=>s.match(/\d+(\.\d+)?/g).slice(0,3).map(Number);const R=(a,b)=>{const x=L(a),y=L(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
      const fondo=[251,228,231];const out={};const m=document.querySelector('header .marca');out.marca=R(rgb(getComputedStyle(m).color),fondo);
      const mb=document.querySelector('header .menu-boton');if(mb){const cs=getComputedStyle(mb);out.menuTexto=R(rgb(cs.color),fondo);out.menuBg=cs.backgroundColor}
      out.bg=getComputedStyle(document.querySelector('header.encabezado')).backgroundImage;return out}""")
with sync_playwright() as p:
    b = lanzar(p)
    for w in (360, 1280):
        c, pg = ctx(b, w); ir(pg, "categorias.html")
        li = pg.evaluate("[...document.querySelectorAll('#lista-categorias li')].map(l=>({t:l.innerText.trim(),svg:l.querySelectorAll('svg').length}))")
        chk(w, 6, "categorías muestra 9 oficios incluido «Otros servicios» con ícono", len(li) == 9 and any(x["t"] == "Otros servicios" and x["svg"] >= 1 for x in li), str(li))
        chk(w, 6, "todos los oficios tienen ícono", all(x["svg"] >= 1 for x in li), "")
        centro = pg.evaluate("""()=>[...document.querySelectorAll('#lista-categorias a')].slice(0,9).map(a=>{const r=a.getBoundingClientRect();const i=a.querySelector('.icono-categoria').getBoundingClientRect();const n=a.querySelector('.nombre-categoria');const nr=document.createRange();nr.selectNodeContents(n);const t=nr.getBoundingClientRect();
          return [Math.abs((i.left+i.right)/2-(r.left+r.right)/2)<=2, Math.abs((t.left+t.right)/2-(r.left+r.right)/2)<=2, getComputedStyle(a).textAlign]})""")
        chk(w, 6, "contenido centrado en las tarjetas (ícono y nombre)", all(x[0] and x[1] for x in centro), str(centro))
        sx = pg.evaluate("document.documentElement.scrollWidth>innerWidth"); chk(w, 6, "sin desplazamiento lateral de la página", not sx, "")
        info = pg.evaluate("""()=>{const l=document.getElementById('lista-categorias');return {sobra:l.scrollWidth-l.clientWidth,ctrlHidden:document.getElementById('carrusel-controles').hidden,
          ant:document.getElementById('carrusel-anterior').innerText.trim(),sig:document.getElementById('carrusel-siguiente').innerText.trim(),snap:getComputedStyle(l).scrollSnapType,live:document.getElementById('carrusel-estado').getAttribute('aria-live'),bh:document.getElementById('carrusel-siguiente').getBoundingClientRect().height}}""")
        print("   info", w, info)
        if w == 360:
            chk(w, 6, "360: hay desborde y los botones se ven (44 px)", info["sobra"] > 1 and not info["ctrlHidden"] and info["bh"] >= 44, str(info))
        else:
            chk(w, 6, "1280: los botones se ocultan solo si caben todos", (info["sobra"] <= 1) == info["ctrlHidden"], str(info))
        if not info["ctrlHidden"]:
            est = lambda: pg.inner_text("#carrusel-estado")
            pg.click("#carrusel-siguiente", force=True); pg.wait_for_timeout(900); e1 = est()
            for _ in range(8):
                pg.click("#carrusel-siguiente", force=True); pg.wait_for_timeout(700)
            e2 = est(); dis = pg.get_attribute("#carrusel-siguiente", "aria-disabled")
            chk(w, 6, "botones: anuncia el final", "final" in e2 and dis == "true", "%r | %r aria-disabled=%s" % (e1, e2, dis))
            for _ in range(10):
                pg.click("#carrusel-anterior", force=True); pg.wait_for_timeout(700)
            e3 = est(); chk(w, 6, "botones: anuncia el inicio", "inicio" in e3 and pg.get_attribute("#carrusel-anterior", "aria-disabled") == "true", repr(e3))
        pg.evaluate("document.getElementById('lista-categorias').scrollLeft=0"); pg.wait_for_timeout(300)
        pg.focus("#lista-categorias a >> nth=0")
        for _ in range(8):
            pg.keyboard.press("Tab"); pg.wait_for_timeout(450)
        vis = pg.evaluate("""()=>{const a=document.activeElement;const l=document.getElementById('lista-categorias').getBoundingClientRect();const r=a.getBoundingClientRect();return [a.textContent.trim(),r.left>=l.left-2&&r.right<=l.right+2]}""")
        chk(w, 6, "teclado: Tab llega a «Otros servicios» y queda entera en el carrusel", vis[0] == "Otros servicios" and vis[1], str(vis))
        sx = pg.evaluate("document.documentElement.scrollWidth>innerWidth"); chk(w, 6, "tras recorrer con teclado, sin desplazamiento lateral de la página", not sx, "")
        enc = contraste_marca(pg)
        chk(w, 6, "encabezado sin sesión: degradado #FBE4E7 -> blanco", "linear-gradient" in enc["bg"] and "251, 228, 231" in enc["bg"] and "255, 255, 255" in enc["bg"], enc["bg"][:140])
        chk(w, 6, "contraste de la marca sobre #FBE4E7 >= 4,5", enc["marca"] >= 4.5, "%.2f:1" % enc["marca"])
        axe(pg, w, "categorias"); print("   consola categorias:", w, pg.errs, pg.http); c.close()
        c = b.new_context(viewport={"width": w, "height": 740}, locale="es-CL", ignore_https_errors=True, reduced_motion="reduce", **({"has_touch": True, "is_mobile": True} if w < 700 else {}))
        pg = c.new_page(); ir(pg, "categorias.html")
        r = pg.evaluate("""async()=>{const l=document.getElementById('lista-categorias');const sb=getComputedStyle(l).scrollBehavior;const b=document.getElementById('carrusel-siguiente');if(document.getElementById('carrusel-controles').hidden)return {sb,sin:true};
          const a=l.scrollLeft;b.click();await new Promise(r=>requestAnimationFrame(r));const d=l.scrollLeft-a;return {sb,saltoEn1Frame:d,trans:getComputedStyle(document.querySelector('.carrusel-boton')).transitionDuration}}""")
        chk(w, 6, "prefers-reduced-motion: sin animación", r["sb"] == "auto" and (r.get("sin") or r["saltoEn1Frame"] > 50), str(r)); c.close()
        c, pg = ctx(b, w); api_login(pg, D["C1"]); ir(pg, "categorias.html"); enc = contraste_marca(pg)
        chk(w, 6, "encabezado con sesión: degradado", "linear-gradient" in enc["bg"] and "251, 228, 231" in enc["bg"], enc["bg"][:120])
        chk(w, 6, "contraste marca y botón «Menú» sobre #FBE4E7 >= 4,5", enc["marca"] >= 4.5 and enc["menuTexto"] >= 4.5, "marca %.2f:1 | Menú texto %.2f:1 fondo %s" % (enc["marca"], enc["menuTexto"], enc["menuBg"]))
        axe(pg, w, "categorias (con sesión)")
        ir(pg, "cuenta.html"); axe(pg, w, "cuenta")
        c.close()
        c, pg = ctx(b, w); ir(pg, "ingresar.html"); axe(pg, w, "ingresar"); enc = contraste_marca(pg); chk(w, 6, "ingresar: marca sobre degradado", enc["marca"] >= 4.5 and "251, 228, 231" in enc["bg"], "%.2f:1" % enc["marca"]); print("   consola ingresar:", pg.errs, pg.http); c.close()
        c, pg = ctx(b, w); api_login(pg, D["DUAL"]); ir(pg, "mi-perfil.html"); axe(pg, w, "mi-perfil"); ir(pg, "mi-perfil.html#sobre-mi"); axe(pg, w, "mi-perfil#sobre-mi"); print("   consola mi-perfil:", pg.errs, pg.http); c.close()
        c, pg = ctx(b, w); ir(pg, "buscar.html?oficio=otros&comuna=8101"); pg.wait_for_timeout(1500)
        r = pg.evaluate(r"""()=>{const t=[...document.querySelectorAll('main a')].filter(a=>a.href.includes('perfil-maestro'));return {n:t.length,precios:t.map(a=>(a.innerText.match(/\$[\d.]+[^\n]*/)||[''])[0]).slice(0,3)}}""")
        chk(w, 8, "buscar oficio=otros&comuna=8101: >= 1 resultado con precio", r["n"] >= 1 and all(r["precios"]), str(r))
        print("   consola buscar:", pg.errs, pg.http); c.close()
    b.close()
