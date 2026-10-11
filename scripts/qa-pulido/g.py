from lib2 import *
PAG = {None: ["index.html","categorias.html","buscar.html?oficio=pintura&region=8&comuna=8101","ingresar.html","registro-cliente.html","postulacion-maestro.html","recuperar.html","ayuda-orden.html","perfil-maestro.html?m="+D["m1_pub"]],
 "A": ["categorias.html","mis-pedidos.html","cuenta.html","conversacion.html?ticket="+D["acep"],"evaluar.html?ticket="+D["fin3"]],
 "M1": ["mis-trabajos.html","mi-perfil.html","mis-servicios.html","mi-cobertura.html","mi-agenda.html","mis-documentos.html","mi-postulacion.html","cuenta.html"],
 "CUR": ["curatoria.html","curatoria-expediente.html?ref=82f2613c-b0a5-4933-88e0-9efae1ce3096"], "COM": ["comercial.html"], "MOD": ["moderacion.html"], "GES": ["indicadores.html"]}
with sync_playwright() as b_:
    b = lanzar(b_)
    for w in (360, 1280):
        csp = 0; otros = []; n = 0
        for who, pags in PAG.items():
            c, pg = ctx(b, w, 800)
            if who: api_login(pg, D[who]); pg.errs.clear(); pg.http.clear()
            for r in pags:
                pg.errs.clear(); pg.http.clear(); ir(pg, r); pg.wait_for_timeout(700); n += 1
                for e in pg.errs:
                    if "Content Security Policy" in e or "Refused" in e: csp += 1
                    otros.append((r.split("?")[0], e[:110], [h for h in pg.http][:3]))
            c.close()
        print("w%d: %d pantallas; violaciones CSP=%d; otros errores de consola=%d" % (w, n, csp, len(otros)))
        agr = {}
        for r, e, h in otros: agr.setdefault((e, tuple(x for x in h if not x.startswith("401 /api/cuenta"))[:2] if True else ()), []).append(r)
        for k, v in agr.items(): print("   ", k[0][:90], "|", k[1], "|", sorted(set(v))[:6])
