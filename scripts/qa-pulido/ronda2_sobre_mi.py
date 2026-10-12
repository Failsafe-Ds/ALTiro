"""Ronda 2 (v0.6.3), puntos 7 y 9 (DA-30 «Sobre mí»): edición en mi-perfil, ficha pública y API. Cuenta DUAL (maestro) y C1 (cliente)."""
from lib2 import *
import json
PUT = """async(c)=>{await fetch('/api/sesion/csrf',{credentials:'same-origin'});const t=document.cookie.split('; ').find(x=>x.startsWith('csrftoken=')).split('=')[1];
  const r=await fetch('/api/maestros/perfil',{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':t},body:c});return [r.status,(await r.text()).slice(0,260)]}"""
def pub(pg, ref):
    return pg.evaluate("async(r)=>{const x=await fetch('/api/maestros/publicos/'+r);const j=await x.json();const m=j.maestro||j.perfil||j;return [x.status,m.descripcion]}", ref)
with sync_playwright() as p:
    b = lanzar(p)
    # --- API: terceros
    c, pg = ctx(b, 360); ir(pg, "ingresar.html")
    pg.evaluate("fetch('/api/sesion/csrf',{credentials:'same-origin'})"); pg.wait_for_timeout(300)
    r = pg.evaluate("async()=>{const t=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='));const r=await fetch('/api/maestros/perfil',{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':t?t.split('=')[1]:''},body:JSON.stringify({descripcion:'x'})});return r.status}")
    chk(0, 7, "API visitante sin sesión no edita la descripción", r in (401, 403), "estado %s" % r); c.close()
    c, pg = ctx(b, 360); api_login(pg, D["C1"]); ir(pg, "mis-pedidos.html")
    r = pg.evaluate(PUT, json.dumps({"descripcion": "Intento de un cliente"}))
    chk(0, 7, "API cliente (sin perfil de maestro) no puede editar: 403", r[0] == 403, str(r))
    c.close()
    c, pg = ctx(b, 360); api_login(pg, D["DUAL"]); ir(pg, "mi-perfil.html")
    r = pg.evaluate(PUT, json.dumps({"descripcion": "Texto propio del dual", "maestro": D["pub_m1"]}))
    chk(0, 7, "API campo ajeno «maestro» en el cuerpo: 400 en el campo, sin 500", r[0] == 400 and "maestro" in r[1], str(r))
    r = pg.evaluate(PUT, json.dumps({"descripcion": "Texto propio del dual", "ref": D["pub_m1"]}))
    chk(0, 7, "API campo ajeno «ref» en el cuerpo: 400", r[0] == 400, str(r))
    antes = pub(pg, D["pub_m1"])
    r = pg.evaluate(PUT, json.dumps({"descripcion": "Solo cambia la mía"}))
    chk(0, 7, "API maestro edita la propia: 200", r[0] == 200, str(r))
    chk(0, 7, "API la descripción de otro maestro no cambia", pub(pg, D["pub_m1"]) == antes and pub(pg, D["pub_dual"])[1] == "Solo cambia la mía", "m1=%s dual=%s" % (pub(pg, D["pub_m1"]), pub(pg, D["pub_dual"])))
    for etiqueta, cuerpo, esp in (("501 caracteres", {"descripcion": "a" * 501}, 400), ("500 caracteres", {"descripcion": "a" * 500}, 200), ("solo espacios", {"descripcion": "     "}, 200),
                                  ("no es texto", {"descripcion": 123}, 400), ("sin la clave (borra: el servicio documenta que vacío o null borra)", {}, 200), ("espacios en bordes", {"descripcion": "  valor  "}, 200)):
        r = pg.evaluate(PUT, json.dumps(cuerpo)); chk(0, 9, "API descripción " + etiqueta, r[0] == esp and r[0] != 500, str(r)[:200])
    r = pg.evaluate(PUT, json.dumps({"descripcion": "  valor  "})); chk(0, 9, "API recorta espacios: se guarda «valor»", pub(pg, D["pub_dual"])[1] == "valor", repr(pub(pg, D["pub_dual"])))
    pg.evaluate(PUT, json.dumps({"descripcion": ""})); c.close()
    for w in (360, 1280):
        c, pg = ctx(b, w); api_login(pg, D["DUAL"]); ir(pg, "mi-perfil.html#sobre-mi"); pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1000)
        ta = "#descripcion"
        chk(w, 7, "campo visible, maxlength 500, contador", pg.is_visible(ta) and pg.get_attribute(ta, "maxlength") == "500" and "500" in pg.inner_text("#contador-descripcion"), pg.inner_text("#contador-descripcion"))
        pg.click(ta); pg.keyboard.type("b" * 510, delay=0)
        chk(w, 7, "510 tecleados -> recorte a 500 y contador en 0", pg.eval_on_selector(ta, "e=>e.value.length") == 500 and "0 caracteres" in pg.inner_text("#contador-descripcion"), pg.inner_text("#contador-descripcion"))
        chk(w, 7, "ayuda del campo advierte no poner teléfono ni correo", "teléfono" in pg.inner_text("#ayuda-descripcion"), pg.inner_text("#ayuda-descripcion")[:120])
        # 501 sin maxlength: error junto al campo y se conserva lo escrito
        pg.evaluate("document.getElementById('descripcion').removeAttribute('maxlength')")
        pg.fill(ta, "c" * 501); pg.click("#form-sobre-mi button[type=submit]"); pg.wait_for_timeout(1200)
        er = errores(pg, "#form-sobre-mi")
        chk(w, 7, "501 caracteres: error junto al campo y visible", any(e["id"] == "error-descripcion" and e["t"] and e["enVista"] for e in er), str(er))
        chk(w, 7, "501 caracteres: se conserva lo escrito (501)", pg.eval_on_selector(ta, "e=>e.value.length") == 501, "")
        pg.evaluate("document.getElementById('descripcion').setAttribute('maxlength','500')")
        # borrador tras recargar
        pg.fill(ta, "Borrador sin guardar"); pg.wait_for_timeout(300); pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1000)
        chk(w, 7, "borrador tras recargar", pg.input_value(ta) == "Borrador sin guardar", repr(pg.input_value(ta)) + " " + str(aviso(pg)[:1]))
        # guardar con espacios y saltos; indicador de carga
        texto = "  Línea uno\nLínea dos <b>negrita</b> <script>alert(1)</script>  "
        pg.fill(ta, texto)
        pend = []
        pg.route("**/api/maestros/perfil", lambda rt: pend.append(rt))
        pg.click("#form-sobre-mi button[type=submit]"); pg.wait_for_timeout(600)
        est = pg.evaluate("()=>{const b=document.querySelector('#form-sobre-mi button[type=submit]');return {dis:b.disabled||b.getAttribute('aria-disabled')==='true',txt:b.innerText}}")
        chk(w, 9, "guardar: botón desactivado con texto de espera", est["dis"] and "Guardando" in est["txt"], str(est))
        for rt in pend: rt.continue_()
        pg.unroute("**/api/maestros/perfil"); pg.wait_for_timeout(1500)
        av = aviso(pg, "#form-sobre-mi .aviso")
        chk(w, 9, "mensaje de resultado anunciado (role)", bool(av) and av[0]["role"] in ("alert", "status") and "guardamos" in av[0]["t"], str(av))
        chk(w, 7, "recorte al guardar (sin espacios en los bordes)", pg.input_value(ta) == texto.strip(), repr(pg.input_value(ta)))
        alm = pg.evaluate("[...Object.keys(sessionStorage),...Object.keys(localStorage)].filter(k=>k.includes('descripcion'))")
        chk(w, 9, "tras guardar el borrador se elimina", alm == [], str(alm))
        # ficha pública
        pg.goto(BASE + "perfil-maestro.html?m=" + D["pub_dual"]); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1200)
        f = pg.evaluate("""()=>{const s=document.getElementById('seccion-sobre-mi'),p=document.getElementById('descripcion-maestro');const cs=getComputedStyle(p);
          return {oculta:s.hidden,ws:cs.whiteSpace,txt:p.textContent,tieneB:!!p.querySelector('b,script'),alto:p.getBoundingClientRect().height,lh:parseFloat(cs.lineHeight)||0,hdr:getComputedStyle(document.querySelector('h1')||document.body).fontSize}}""")
        chk(w, 7, "ficha: saltos de línea respetados (white-space)", f["ws"] in ("pre-line", "pre-wrap") and f["alto"] >= 2 * (f["lh"] or 20) - 2, str(f)[:260])
        chk(w, 7, "ficha: el HTML se muestra como texto, sin elementos", f["tieneB"] is False and "<b>negrita</b>" in f["txt"], f["txt"][:120])
        html = pg.evaluate("document.getElementById('descripcion-maestro').innerHTML")
        chk(w, 7, "ficha: HTML escapado en el DOM", "&lt;b&gt;" in html and "<script" not in html, html[:120])
        pg.screenshot(path="/tmp/ficha_%d.png" % w) if False else None
        # vaciar -> sección oculta
        pg.goto(BASE + "mi-perfil.html#sobre-mi"); pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1000)
        pg.fill(ta, "      "); pg.click("#form-sobre-mi button[type=submit]"); pg.wait_for_timeout(1500)
        av = aviso(pg, "#form-sobre-mi .aviso"); print("   solo espacios ->", pg.input_value(ta) == "", av[:1])
        pg.goto(BASE + "perfil-maestro.html?m=" + D["pub_dual"]); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1200)
        chk(w, 7, "ficha: descripción vacía oculta la sección", pg.evaluate("document.getElementById('seccion-sobre-mi').hidden") is True or not pg.is_visible("#seccion-sobre-mi"), "")
        print("   consola:", w, [e for e in pg.errs if "401" not in e and "404" not in e], pg.http); c.close()
    b.close()
