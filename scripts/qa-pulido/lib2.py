from lib import *
import random, string
def chk(w, punto, form, ok, det=""):
    print("[%s] w%d P%s %s: %s" % ("PASS" if ok else "FAIL", w, punto, form, det), flush=True)
def tipear(pg, sel, n):
    pg.click(sel); pg.fill(sel, ""); pg.keyboard.type("a" * n, delay=0)
    return pg.eval_on_selector(sel, "e=>e.value.length")
def api(pg, ruta, datos, m="enviar"):
    return pg.evaluate("async([r,d])=>{const x=await api.%s(r,d);return [x.estado,x.datos]}" % m, [ruta, datos])
def errores(pg, form="body"):
    return pg.evaluate("""(f)=>[...document.querySelectorAll(f+' .error-campo')].filter(e=>e.textContent.trim()).map(e=>{const r=e.getBoundingClientRect();const c=document.querySelector('[aria-describedby~="'+e.id+'"]');return {id:e.id,t:e.textContent.trim(),enVista:r.top>=0&&r.bottom<=innerHeight,inv:c?c.getAttribute('aria-invalid'):null}})""", form)
def aviso(pg, sel=".aviso"):
    return pg.evaluate("""(s)=>[...document.querySelectorAll(s)].filter(e=>e.textContent.trim()&&e.getBoundingClientRect().width>0).map(e=>({t:e.textContent.trim().slice(0,160),role:e.getAttribute('role'),cls:e.className}))""", sel)
def ocupado(pg, patron, boton, accion, espera=2500):
    def h(route):
        time.sleep(espera / 1000); route.continue_()
    pg.route(patron, h)
    accion()
    pg.wait_for_timeout(500)
    est = pg.evaluate("(s)=>{const b=document.querySelector(s);return {dis:b.disabled||b.getAttribute('aria-disabled')==='true',busy:b.getAttribute('aria-busy'),txt:b.innerText}}", boton)
    return h, est
def rut_valido(n):
    c = 32_000_000 + n; s = 0; f = 2
    for d in reversed(str(c)):
        s += int(d) * f; f = 2 if f == 7 else f + 1
    dv = 11 - s % 11
    return "%d-%s" % (c, "0" if dv == 11 else "K" if dv == 10 else dv)
def con_puntos(r):
    c, dv = r.split("-"); return "{:,}".format(int(c)).replace(",", ".") + "-" + dv
def claves_borrador(pg):
    return pg.evaluate("[...Object.keys(sessionStorage),...Object.keys(localStorage)].filter(k=>k.startsWith('altiro'))")
