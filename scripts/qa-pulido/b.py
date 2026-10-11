from lib import *
VOL = """()=>[...document.querySelectorAll('a,button,[role=button]')].filter(e=>/volver|atr[aá]s|anterior/i.test(e.textContent)||e.hasAttribute('data-volver')).map(e=>e.tagName+'#'+e.id+'['+(e.getAttribute('href')||'')+']"'+e.textContent.trim().slice(0,40)+'" visible='+(e.getBoundingClientRect().width>0))"""
PAG = {"A": ["index.html","categorias.html","buscar.html","mis-pedidos.html","cuenta.html","pedir-trabajo.html?m=%s&b=e55c1649-55df-462c-88e2-8ce07ef8b4e5&f=2026-10-12&s=65fb1cf9-3bf6-4a9f-9cc7-17ffa885c452"%D["m1_pub"],"perfil-maestro.html?m="+D["m1_pub"],"conversacion.html?ticket="+D["acep"],"evaluar.html?ticket="+D["fin1"],"registro-cliente.html","ayuda-orden.html"],
 "M1": ["mis-trabajos.html","mi-perfil.html","mis-servicios.html","mi-cobertura.html","mi-agenda.html","mis-documentos.html","mi-postulacion.html","conversacion.html?ticket="+D["acep"]],
 "CUR": ["curatoria.html","curatoria-expediente.html?ref=82f2613c-b0a5-4933-88e0-9efae1ce3096"], "COM": ["comercial.html"], "MOD": ["moderacion.html"], "GES": ["indicadores.html"]}
with sync_playwright() as p:
    b = lanzar(p)
    print("== 2a. Volver en DOM (todas las páginas, 360)")
    for who, pags in PAG.items():
        c, pg = ctx(b, 360); api_login(pg, D[who])
        for r in pags:
            ir(pg, r); v = pg.evaluate(VOL)
            print("%-48s %s" % (r.split('&')[0][:48], v))
        c.close()
    c, pg = ctx(b, 360)
    for r in ["login","ingresar.html","recuperar.html","postulacion-maestro.html","nueva-contrasena.html"]:
        if r=="login": continue
        ir(pg, r); print("%-48s %s" % (r, pg.evaluate(VOL)))
    c.close()
