"""Ronda 2, puntos 4, 5, 7(API), 8 y 9: postular desde una cuenta cliente existente y los pasos de documentos (ADR-017 E-4).
Uso: run.sh ronda2_postulacion.py <ancho> <CP|CP2>"""
from lib2 import *
import sys
W = int(sys.argv[1]) if len(sys.argv) > 1 else 360
cuenta = sys.argv[2] if len(sys.argv) > 2 else "CP"
RUT = D["rut_post"] if cuenta == "CP" else D["rut_post2"]
JPG = """async()=>{const c=document.createElement('canvas');c.width=300;c.height=200;const x=c.getContext('2d');for(let i=0;i<300;i+=10)for(let j=0;j<200;j+=10){x.fillStyle='rgb('+(i%255)+','+(j%255)+','+((i*j)%255)+')';x.fillRect(i,j,10,10)}
 const b=await new Promise(r=>c.toBlob(r,'image/jpeg',0.9));return Array.from(new Uint8Array(await b.arrayBuffer()))}"""
def paso(pg):
    return pg.evaluate("""()=>{const t=document.getElementById('titulo-documento');const f=document.getElementById('form-documento');
      return {visible:!f.classList.contains('oculto')&&f.getBoundingClientRect().width>0,titulo:t.textContent.trim(),ayuda:document.getElementById('ayuda-documento').textContent.trim(),
      emi:document.querySelector('label[for=fecha_emision]').textContent,emiAy:document.getElementById('ayuda-fecha_emision').textContent,
      ven:document.getElementById('etiqueta-fecha_vencimiento').textContent,venAy:document.getElementById('ayuda-fecha_vencimiento').textContent,
      venReq:document.getElementById('fecha_vencimiento').required}}""")
def imgs(pg): return pg.evaluate("document.querySelectorAll('#fotos img').length")
with sync_playwright() as p:
    b = lanzar(p); c, pg = ctx(b, W); print("login", api_login(pg, D[cuenta]))
    open("/tmp/a.jpg", "wb").write(bytes(pg.evaluate(JPG)))
    ir(pg, "cuenta.html#perfiles"); pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(600)
    pg.wait_for_timeout(1500)
    print("DBG", pg.url, pg.evaluate("[document.getElementById('perfiles').hidden, document.getElementById('seccion-maestro').className, document.getElementById('rut').getBoundingClientRect().width, document.querySelector('main').className]"))
    print("SECCION:", pg.evaluate("document.getElementById('seccion-maestro').innerText")[:700].replace("\n", " | "))
    pg.evaluate("document.getElementById('rut').scrollIntoView({block:'center'})"); pg.click("#rut", timeout=8000); pg.keyboard.type("1.111.111-1"); pg.keyboard.press("Tab"); pg.wait_for_timeout(200)
    pg.click("#agregar-maestro button[type=submit]"); pg.wait_for_timeout(1200)
    e = pg.evaluate("""()=>{const e=document.getElementById('error-rut');const i=document.getElementById('rut');const r=e.getBoundingClientRect();return {t:e.textContent.trim(),v:r.top>=0&&r.bottom<=innerHeight,inv:i.getAttribute('aria-invalid'),url:location.pathname}}""")
    chk(W, 4, "RUT inválido 1.111.111-1 rechazado junto al campo", bool(e["t"]) and e["v"] and e["inv"] == "true" and "cuenta" in e["url"], str(e))
    pg.fill("#rut", ""); pg.click("#rut"); pg.keyboard.type(RUT); pg.keyboard.press("Tab"); pg.wait_for_timeout(200)
    v = pg.input_value("#rut"); chk(W, 4, "RUT se formatea al salir", v == con_puntos(RUT), "%r (de %s)" % (v, RUT))
    print("OBS w%d P4 error del RUT tras corregir y salir del campo: %r (se limpia al reenviar)" % (W, pg.evaluate("document.getElementById('error-rut').textContent.trim()")[:40]))
    pg.click("#agregar-maestro button[type=submit]"); pg.wait_for_url("**/mi-postulacion.html**", timeout=15000); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(800)
    chk(W, 4, "lleva a mi-postulacion", "mi-postulacion" in pg.url, pg.url)
    lab = pg.evaluate(r"[...document.querySelectorAll('#lista-oficios label')].map(l=>l.textContent.trim().replace(/\s+/g,' '))")
    chk(W, 8, "declaración de oficios incluye «Otros servicios»", any("Otros servicios" in x for x in lab), "%d oficios: %s" % (len(lab), lab))
    print("INTRO:", pg.evaluate("document.querySelector('main').innerText")[:260].replace("\n", " | "))
    pg.check("#lista-oficios label:has-text('Pintura') input"); pg.check("#lista-oficios label:has-text('Gas') input"); pg.wait_for_timeout(200)
    pg.click("#form-oficios button[type=submit]"); pg.wait_for_timeout(1500)
    s = paso(pg); print("PASO1:", s)
    chk(W, 5, "paso 1 dice qué documento pide", s["visible"] and re.search("c[eé]dula", s["titulo"] + s["ayuda"], re.I) is not None, s["titulo"])
    chk(W, 5, "cédula: vencimiento obligatorio en pantalla", "obligatorio" in s["ven"] and s["venReq"], s["ven"])
    campos_foto = pg.evaluate("[...document.querySelectorAll('#fotos input[type=file]')].map(i=>i.id)")
    jpg = open("/tmp/a.jpg", "rb").read()
    r = pg.evaluate("""async([hex,nombres])=>{const u=new Uint8Array(hex.match(/../g).map(h=>parseInt(h,16)));
      await fetch('/api/sesion/csrf',{credentials:'same-origin'});const t=document.cookie.split('; ').find(x=>x.startsWith('csrftoken=')).split('=')[1];
      const f=new FormData();f.append('tipo','cedula_identidad');f.append('fecha_emision','2024-01-15');nombres.forEach(n=>f.append(n,new Blob([u],{type:'image/jpeg'}),n+'.jpg'));
      const x=await fetch('/api/maestros/expediente/documentos',{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':t},body:f});return [x.status,await x.text()]}""",
        [jpg.hex(), [i.replace("entrada-", "") for i in campos_foto]])
    chk(W, 5, "API cédula sin fecha_vencimiento -> 400 en fecha_vencimiento", r[0] == 400 and "fecha_vencimiento" in r[1], "%s %s" % (r[0], r[1][:200]))
    for etiqueta in campos_foto: pg.set_input_files("#" + etiqueta, "/tmp/a.jpg")
    pg.wait_for_timeout(1500); pg.fill("#fecha_emision", "2024-01-15"); pg.fill("#fecha_vencimiento", "")
    pg.click("#enviar-documento"); pg.wait_for_timeout(800)
    er = errores(pg, "#form-documento"); chk(W, 5, "cédula sin vencimiento: error junto al campo, visible", any(x["id"] == "error-fecha_vencimiento" and x["enVista"] for x in er), str(er))
    chk(W, 7, "dato faltante no borra fotos ni emisión", pg.input_value("#fecha_emision") == "2024-01-15" and imgs(pg) >= 2, "imgs=%d" % imgs(pg))
    pg.fill("#fecha_vencimiento", "2031-05-20")
    pg.click("#documento-volver"); pg.wait_for_timeout(700)
    chk(W, 5, "paso anterior muestra los oficios", pg.is_visible("#form-oficios"), "")
    pg.click("#form-oficios button[type=submit]"); pg.wait_for_timeout(1500)
    chk(W, 5, "al volver al paso se conservan fechas", pg.input_value("#fecha_emision") == "2024-01-15" and pg.input_value("#fecha_vencimiento") == "2031-05-20", "%s %s" % (pg.input_value("#fecha_emision"), pg.input_value("#fecha_vencimiento")))
    chk(W, 5, "al volver al paso se conservan las 2 fotos", imgs(pg) >= 2, "imgs=%d" % imgs(pg))
    alm = pg.evaluate("({ss:Object.entries(sessionStorage).map(([k,v])=>[k,v.length,v.slice(0,30)]),ls:Object.entries(localStorage).map(([k,v])=>[k,v.length,v.slice(0,30)])})")
    chk(W, 5, "fotos no están en sessionStorage/localStorage (solo marcas cortas)", not alm["ls"] and all(x[1] < 50 and not x[2].startswith("data:") for x in alm["ss"]), str(alm))
    pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(800)
    av = aviso(pg, ".aviso")
    chk(W, 5, "al recargar: aviso de volver a elegir las fotos", any("elige de nuevo las fotos" in a["t"] for a in av), str(av)[:300])
    print("   tras recargar: form-documento", pg.is_visible("#form-documento"), "oficios", pg.is_visible("#form-oficios"), "resumen", pg.is_visible("#resumen"))
    if not pg.is_visible("#form-documento"):
        if pg.is_visible("#form-oficios"): pg.click("#form-oficios button[type=submit]"); pg.wait_for_timeout(1500)
        elif pg.is_visible("#continuar"): pg.click("#continuar"); pg.wait_for_timeout(1000)
    for etiqueta in campos_foto: pg.set_input_files("#" + etiqueta, "/tmp/a.jpg")
    pg.wait_for_timeout(1500); pg.fill("#fecha_emision", "2024-01-15"); pg.fill("#fecha_vencimiento", "2031-05-20")
    pend = []
    pg.route("**/api/maestros/expediente/documentos", lambda rt: pend.append(rt))
    pg.click("#enviar-documento"); pg.wait_for_timeout(700)
    est = pg.evaluate("()=>{const b=document.getElementById('enviar-documento');return {dis:b.disabled||b.getAttribute('aria-disabled')==='true',busy:b.getAttribute('aria-busy'),txt:b.innerText,prog:document.getElementById('progreso-envio').textContent,live:document.getElementById('progreso-envio').getAttribute('role')}}")
    chk(W, 5, "envío en espera: botón desactivado con texto de espera", est["dis"] and est["txt"].strip() != "Enviar documento", str(est))
    for rt in pend: rt.continue_()
    pg.unroute("**/api/maestros/expediente/documentos"); pg.wait_for_timeout(4000)
    print("   tras enviar cédula, avisos:", aviso(pg, ".aviso")[:2], "| form-documento visible:", pg.is_visible("#form-documento"))
    s2 = paso(pg); print("PASO2:", s2)
    chk(W, 5, "paso 2 dice qué documento pide (antecedentes)", re.search("antecedentes", s2["titulo"] + s2["ayuda"], re.I) is not None, s2["titulo"])
    chk(W, 5, "antecedentes: vencimiento «(si tiene)» y opcional", "(si tiene)" in s2["ven"] and not s2["venReq"], s2["ven"])
    chk(W, 5, "antecedentes: la ayuda dice dónde leer cada fecha", len(s2["emiAy"]) > 20 and len(s2["venAy"]) > 20, s2["emiAy"] + " / " + s2["venAy"])
    for e_ in pg.evaluate("[...document.querySelectorAll('#fotos input[type=file]')].map(i=>i.id)"): pg.set_input_files("#" + e_, "/tmp/a.jpg")
    pg.wait_for_timeout(1200); pg.fill("#fecha_emision", "2026-09-01")
    pg.click("#documento-volver"); pg.wait_for_timeout(800)
    t = pg.evaluate("document.getElementById('titulo-documento').textContent")
    chk(W, 5, "paso anterior desde antecedentes vuelve a la cédula", "dula" in t, t)
    pg.click("#documento-seguir"); pg.wait_for_timeout(1000)
    s3 = paso(pg)
    chk(W, 5, "adelante de nuevo: antecedentes conserva foto y fecha", "ntecedentes" in s3["titulo"] and pg.input_value("#fecha_emision") == "2026-09-01" and imgs(pg) >= 1, "%s %s imgs=%d" % (s3["titulo"], pg.input_value("#fecha_emision"), imgs(pg)))
    pg.click("#enviar-documento"); pg.wait_for_timeout(4000)
    s4 = paso(pg); print("PASO3:", s4)
    chk(W, 5, "paso 3 dice qué documento pide (licencia)", re.search("licencia", s4["titulo"] + s4["ayuda"], re.I) is not None, s4["titulo"])
    chk(W, 5, "licencia: vencimiento «(si tiene)» y opcional", "(si tiene)" in s4["ven"] and not s4["venReq"], s4["ven"])
    alm = pg.evaluate("({ss:Object.entries(sessionStorage).map(([k,v])=>[k,v.length]),ls:Object.keys(localStorage)})")
    chk(W, 5, "almacenamiento final sin fotos", not alm["ls"] and all(x[1] < 50 for x in alm["ss"]), str(alm))
    print("ERRORES consola:", pg.errs, pg.http[:6])
    b.close()
