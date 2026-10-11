from lib import *
ACT = "(()=>{const e=document.activeElement;return e? e.tagName+':'+(e.textContent||'').trim().slice(0,20)+':'+(e.closest('nav.opciones-menu')?'NAV':'-')+':'+(e.getAttribute('href')||''):''})()"
with sync_playwright() as p:
    b = lanzar(p)
    for w in (360, 1280):
        c, pg = ctx(b, w, 800); api_login(pg, D["M1"]); ir(pg, "cuenta.html"); pg.wait_for_timeout(600)
        seen = []; abierto = False
        for k in range(40):
            pg.keyboard.press("Tab"); f = pg.evaluate(ACT); seen.append(f)
            if f.startswith("SUMMARY") and not abierto:
                pg.keyboard.press("Enter"); abierto = True; pg.wait_for_timeout(300)
            if "NAV" in f and "mi-cobertura" in f: break
        nav = [s for s in seen if ":NAV:" in s or s.startswith("SUMMARY")]
        print("w%d tab alcanza en el menú:"%w, nav)
        ok = bool(nav) and "mi-cobertura" in seen[-1]
        if ok:
            pg.keyboard.press("Enter"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(500)
            cur = pg.evaluate("[...document.querySelectorAll('nav.opciones-menu a[aria-current]')].map(a=>a.textContent.trim())")
            print("   Enter ->", pg.url.replace(BASE,""), cur, "PASS" if cur==["Mi cobertura"] else "FAIL")
        else: print("   FAIL no alcanzable")
        # foco visible
        pg.keyboard.press("Tab")
        print("   foco visible (outline):", pg.evaluate("(()=>{const s=getComputedStyle(document.activeElement);return s.outlineStyle+' '+s.outlineWidth+' '+s.boxShadow.slice(0,40)})()"))
        c.close()
