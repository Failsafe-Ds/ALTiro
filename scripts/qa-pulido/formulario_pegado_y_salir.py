"""Auditoría 2, hallazgo 8 (v0.6.4): prueba en el navegador de formulario.js y de las correcciones 1, 2, 3 y 5.
- pegado real (Ctrl+V desde el portapapeles) en un campo email y en uno text: queda recortado;
- texto largo pegado con espacios: no pasa del maxlength;
- contraseña pegada con espacios: no se recorta, tampoco con «Mostrar contraseña»;
- error de campo que se limpia al corregir y salir del campo (observación QA ronda 2);
- región cambiada rápido: las comunas son las de la última región (hallazgo 3);
- petición colgada: corta a los 20 s con aviso de conectividad (hallazgo 5);
- cerrar sesión desde el menú: localStorage y sessionStorage sin claves altiro.* (hallazgo 1).
Uso: run.sh formulario_pegado_y_salir.py (cuentas de prep_ronda2.py en datos.json)."""
from lib2 import *

def pegar(pg, sel, texto):
    pg.evaluate("(t)=>navigator.clipboard.writeText(t)", texto)
    pg.focus(sel)
    pg.keyboard.press("Control+V")
    pg.wait_for_timeout(150)
    return pg.eval_on_selector(sel, "e=>e.value")

def vaciar(pg, sel):
    pg.eval_on_selector(sel, "e=>{e.value='';}")

with sync_playwright() as p:
    b = lanzar(p)
    for w in (360, 1280):
        c, pg = ctx(b, w)
        c.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE.rstrip("/"))
        ir(pg, "registro-cliente.html")
        # Pasos 2 y 3 a la vista para pegar en ellos (solo para la prueba).
        pg.evaluate("document.querySelectorAll('.paso').forEach(p=>p.hidden=false)")

        v = pegar(pg, "#correo", "ana.prueba@example.cl ")
        chk(w, 2, "pegar correo con espacio final (email)", v == "ana.prueba@example.cl", repr(v))
        vaciar(pg, "#correo")
        v = pegar(pg, "#correo", "  ana.prueba@example.cl")
        chk(w, 2, "pegar correo con espacios al inicio (email)", v == "ana.prueba@example.cl", repr(v))
        v = pegar(pg, "#nombre", "  Ana Prueba  ")
        chk(w, 2, "pegar nombre con espacios (text)", v == "Ana Prueba", repr(v))
        vaciar(pg, "#nombre")
        v = pegar(pg, "#nombre", "  " + "x" * 200 + "  ")
        chk(w, 2, "pegado largo respeta maxlength 150", len(v) == 150, "largo=%d" % len(v))
        v = pegar(pg, "#contrasena", "  clave  ")
        chk(w, 2, "contraseña pegada sin recortar", v == "  clave  ", repr(v))
        pg.check("[data-mostrar='contrasena']")
        vaciar(pg, "#contrasena")
        v = pegar(pg, "#contrasena", "  clave  ")
        chk(w, 2, "contraseña con «Mostrar contraseña» sin recortar", v == "  clave  ",
            "%r type=%s" % (v, pg.eval_on_selector("#contrasena", "e=>e.type")))
        pg.dispatch_event("#contrasena", "change")
        v = pg.eval_on_selector("#contrasena", "e=>e.value")
        chk(w, 2, "contraseña sin recortar al salir del campo", v == "  clave  ", repr(v))

        # Observación QA: corregir y salir limpia el error del campo.
        ir(pg, "registro-cliente.html")
        pg.fill("#nombre", "Ana Prueba"); pg.fill("#telefono", "+56912345678"); pg.fill("#correo", "ana@malo")
        pg.click("fieldset.paso:not([hidden]) [data-paso='siguiente']"); pg.wait_for_timeout(300)
        antes = pg.eval_on_selector("#error-correo", "e=>e.textContent.trim()")
        pg.fill("#correo", "ana@example.cl"); pg.focus("#nombre"); pg.wait_for_timeout(200)
        despues = pg.evaluate("[document.getElementById('error-correo').textContent.trim(), document.getElementById('correo').getAttribute('aria-invalid')]")
        chk(w, 11, "error de correo visible antes de corregir", bool(antes), antes[:60])
        chk(w, 11, "error de correo limpio al corregir y salir", despues == ["", None], repr(despues))

        # Hallazgo 3: la respuesta lenta de la primera región no pisa la segunda.
        ir(pg, "registro-cliente.html")
        pg.evaluate("document.querySelectorAll('.paso').forEach(p=>p.hidden=false)")
        regiones = pg.evaluate("[...document.querySelectorAll('#region option')].map(o=>o.value).filter(Boolean)")
        r1, r2 = regiones[0], regiones[1]
        def lenta(route):
            time.sleep(2.5); route.continue_()
        pg.route("**/api/territorio/regiones/%s/comunas" % r1, lenta)
        pg.select_option("#region", r1); pg.wait_for_timeout(100); pg.select_option("#region", r2)
        pg.wait_for_timeout(3500)
        esperadas = pg.evaluate("async(r)=>(await (await fetch('/api/territorio/regiones/'+r+'/comunas')).json()).comunas.map(c=>String(c.codigo))", r2)
        vistas = pg.evaluate("[...document.querySelectorAll('#comuna option')].map(o=>o.value).filter(Boolean)")
        chk(w, 3, "comunas de la última región elegida", vistas == esperadas, "region=%s vistas=%d esperadas=%d" % (r2, len(vistas), len(esperadas)))
        pg.unroute("**/api/territorio/regiones/%s/comunas" % r1)
        c.close()

    # Hallazgo 5: una petición colgada se corta a los 20 s (solo a 360).
    c, pg = ctx(b, 360)
    ir(pg, "registro-cliente.html")
    pg.evaluate("document.querySelectorAll('.paso').forEach(p=>p.hidden=false)")
    regiones = pg.evaluate("[...document.querySelectorAll('#region option')].map(o=>o.value).filter(Boolean)")
    pg.route("**/api/territorio/regiones/%s/comunas" % regiones[2], lambda route: None)  # nunca responde
    inicio = time.time(); pg.select_option("#region", regiones[2])
    pg.wait_for_selector(".aviso-territorio", timeout=30000)
    seg = time.time() - inicio
    txt = pg.inner_text(".aviso-territorio")
    chk(360, 5, "petición colgada cortada con aviso de conectividad", 19 <= seg <= 25 and "señal" in txt, "%.1f s: %s" % (seg, txt[:90]))
    c.close()

    # Hallazgo 1: cerrar sesión desde el menú borra todos los borradores.
    for w in (360, 1280):
        c, pg = ctx(b, w)
        st = api_login(pg, D["C1"]); ir(pg, "mis-pedidos.html")
        pg.evaluate("""()=>{const g=Date.now();
          sessionStorage.setItem('altiro.pedir-trabajo.x', JSON.stringify({valores:{direccion:'Pasaje Ficticio 1'},guardado:g}));
          localStorage.setItem('altiro.conversacion.prueba', JSON.stringify({texto:'depto 402',guardado:g}));
          localStorage.setItem('altiro.evaluar.prueba', JSON.stringify({texto:'{}',guardado:g}));}""")
        chk(w, 1, "borradores sembrados", len(claves_borrador(pg)) >= 3, repr(claves_borrador(pg)))
        pg.click(".menu-boton"); pg.click(".menu-salir")
        pg.wait_for_url("**/index.html?aviso=sesion-cerrada", timeout=10000); pg.wait_for_load_state("networkidle")
        quedan = claves_borrador(pg)
        chk(w, 1, "cerrar sesión desde el menú deja sin altiro.*", quedan == [], "login=%s quedan=%r" % (st, quedan))
        chk(w, 0, "sin errores de JavaScript ni CSP", not [e for e in pg.errs if "js:" in e or "Content Security" in e], repr(pg.errs[:3]))
        c.close()
    b.close()
