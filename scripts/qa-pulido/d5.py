from lib2 import *
def conv(b, w):
    F = "conversacion (mensaje)"
    c, pg = ctx(b, w); api_login(pg, D["A"]); ir(pg, "conversacion.html?ticket=" + D["acep"]); pg.wait_for_timeout(800)
    chk(w, 3, F, tipear(pg, "#texto", 1100) == 1000, "maxlength 1000")
    r = api(pg, "/api/tickets/%s/mensajes" % D["acep"], {"texto": "x" * 1001, "clave_envio": "00000000-0000-4000-8000-000000000001"})
    chk(w, 3, F, r[0] == 400 and "texto" in (r[1].get("errores") or {}), "API 1001 -> %s %s" % (r[0], json.dumps(r[1], ensure_ascii=False)[:150]))
    r = api(pg, "/api/tickets/%s/mensajes" % D["acep"], {"texto": "     ", "clave_envio": "00000000-0000-4000-8000-000000000002"})
    chk(w, 4, F, r[0] == 400, "API solo espacios -> %s %s" % (r[0], json.dumps(r[1], ensure_ascii=False)[:120]))
    pg.fill("#texto", "     "); pg.click("#enviar"); pg.wait_for_timeout(600)
    er = errores(pg); chk(w, 4, F, len(er) >= 1 and all(e["enVista"] for e in er), "solo espacios -> %s" % [(e["id"], e["t"], e["enVista"]) for e in er])
    msg = "  Hola, ¿a qué hora llegas? (%d)  " % w
    pg.fill("#texto", msg); pg.keyboard.press("Tab"); pg.wait_for_timeout(300)
    chk(w, 2, F, pg.input_value("#texto") == msg.strip(), "recortado en pantalla")
    # borrador conservado al recargar
    pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(900)
    chk(w, 7, F, pg.input_value("#texto").strip() == msg.strip(), "borrador conservado tras recargar: %r; claves %s" % (pg.input_value("#texto"), claves_borrador(pg)))
    cu = []
    pg.on("request", lambda rq: cu.append(rq.post_data) if rq.method == "POST" and "mensajes" in rq.url else None)
    pg.evaluate("""()=>{const f=document.getElementById('formulario-mensaje'),b=document.getElementById('enviar');f.addEventListener('submit',()=>setTimeout(()=>sessionStorage.setItem('__est',JSON.stringify({dis:b.disabled,txt:b.innerText,busy:f.getAttribute('aria-busy')})),400))}""")
    pg.route("**/api/tickets/**/mensajes", lambda rt: (time.sleep(2.5), rt.continue_()) if rt.request.method == "POST" else rt.continue_())
    pg.click("#enviar"); pg.wait_for_timeout(4500)
    est = pg.evaluate("sessionStorage.getItem('__est')")
    chk(w, 5, F, est is not None and json.loads(est)["dis"], "durante la espera: %s" % est)
    body = json.loads(cu[0]) if cu else {}
    chk(w, 2, F, body.get("texto") == msg.strip(), "cuerpo enviado texto=%r" % body.get("texto"))
    chk(w, 8, F, pg.input_value("#texto") == "" and not [k for k in claves_borrador(pg) if "conversacion" in k], "campo limpio %r y borrador eliminado %s" % (pg.input_value("#texto"), claves_borrador(pg)))
    av = aviso(pg, "#aviso-envio, .aviso, [role=status], [role=alert]"); print("   avisos:", av[:3])
    chk(w, 9, F, any(a["role"] for a in av), "mensaje de resultado anunciado: %s" % [(a["t"][:60], a["role"]) for a in av[:3]])
    print("   ERRS", [e for e in pg.errs if "401" not in e][:3])
    c.close()

def evaluar(b, w, tk):
    F = "evaluar"
    c, pg = ctx(b, w); api_login(pg, D["A"]); ir(pg, "evaluar.html?ticket=" + tk); pg.wait_for_timeout(800)
    chk(w, 3, F, tipear(pg, "#comentario", 600) == 500, "maxlength comentario 500")
    r = api(pg, "/api/tickets/%s/evaluacion" % tk, {"puntualidad": 5, "trabajo": 5, "cordialidad": 5, "comentario": "x" * 501})
    chk(w, 3, F, r[0] == 400 and "comentario" in (r[1].get("errores") or {}), "API 501 -> %s %s" % (r[0], json.dumps(r[1], ensure_ascii=False)[:150]))
    pg.fill("#comentario", "  Muy buen trabajo, gracias.  ")
    pg.locator("input[name=puntualidad]").nth(4).check()
    pg.locator("button[type=submit]").first.click(); pg.wait_for_timeout(600)
    er = errores(pg); chk(w, 6, F, len(er) >= 1, "faltan 2 puntajes -> %s | resumen %s" % ([(e["id"], e["t"], e["enVista"]) for e in er], [a["t"] for a in aviso(pg)][:2]))
    chk(w, 7, F, pg.input_value("#comentario").strip() == "Muy buen trabajo, gracias." and pg.locator("input[name=puntualidad]").nth(4).is_checked(), "no borra lo escrito (comentario %r, puntualidad marcada %s)" % (pg.input_value("#comentario"), pg.locator("input[name=puntualidad]").nth(4).is_checked()))
    pg.locator("input[name=trabajo]").nth(4).check(); pg.locator("input[name=cordialidad]").nth(3).check()
    cu = []
    pg.on("request", lambda rq: cu.append(rq.post_data) if rq.method == "POST" and "evaluacion" in rq.url else None)
    pg.evaluate("""()=>{const b=document.querySelector('button[type=submit]'),f=b.form;f.addEventListener('submit',()=>setTimeout(()=>sessionStorage.setItem('__est',JSON.stringify({dis:b.disabled,txt:b.innerText,busy:f.getAttribute('aria-busy')})),400))}""")
    pg.route("**/api/tickets/**/evaluacion", lambda rt: (time.sleep(2.5), rt.continue_()) if rt.request.method == "POST" else rt.continue_())
    pg.locator("button[type=submit]").first.click(); pg.wait_for_timeout(4500)
    est = pg.evaluate("sessionStorage.getItem('__est')")
    chk(w, 5, F, est is not None and json.loads(est)["dis"], "durante la espera: %s" % est)
    body = json.loads(cu[0]) if cu else {}
    chk(w, 2, F, body.get("comentario") == "Muy buen trabajo, gracias.", "cuerpo comentario=%r" % body.get("comentario"))
    av = aviso(pg, ".aviso, [role=status], [role=alert]"); print("   avisos:", av[:3], "| main:", pg.inner_text("main")[:160].replace("\n", " | "))
    chk(w, 9, F, any(a["role"] for a in av), "resultado anunciado: %s" % [(a["t"][:60], a["role"]) for a in av[:2]])
    print("   comentario campo:", pg.locator("#comentario:visible").count() and repr(pg.input_value("#comentario")), "borradores", claves_borrador(pg))
    print("   ERRS", [e for e in pg.errs if "401" not in e][:3])
    c.close()

def curat(b, w, ref):
    F = "curatoria (motivo)"
    c, pg = ctx(b, w); api_login(pg, D["CUR"]); ir(pg, "curatoria-expediente.html?ref=" + ref); pg.wait_for_timeout(900)
    chk(w, 3, F, tipear(pg, "#motivo-estado", 1100) == 1000, "maxlength motivo 1000")
    r = api(pg, "/api/curatoria/expedientes/%s/estado" % ref, {"estado_nuevo": "observado", "motivo": "x" * 1001})
    chk(w, 3, F, r[0] == 400 and "motivo" in (r[1].get("errores") or {}), "API 1001 -> %s %s" % (r[0], json.dumps(r[1], ensure_ascii=False)[:150]))
    pg.locator("input[name=estado_nuevo][value=observado]").check(); pg.fill("#motivo-estado", "     ")
    pg.click("#guardar-estado"); pg.wait_for_timeout(600)
    er = errores(pg); chk(w, 4, F, len(er) >= 1 and all(e["enVista"] for e in er), "solo espacios -> %s" % [(e["id"], e["t"], e["enVista"]) for e in er])
    pg.fill("#motivo-estado", "x" * 5 + "  falta la foto de la cédula  "); pg.fill("#motivo-estado", "  falta la foto de la cédula  ")
    pg.locator("input[name=estado_nuevo]").evaluate_all("els=>els.forEach(e=>e.checked=false)")
    pg.click("#guardar-estado"); pg.wait_for_timeout(500)
    er = errores(pg); chk(w, 7, F, pg.input_value("#motivo-estado") == "  falta la foto de la cédula  " or pg.input_value("#motivo-estado").strip() == "falta la foto de la cédula", "falta el estado: motivo conservado %r; errores %s" % (pg.input_value("#motivo-estado"), [(e["id"], e["t"]) for e in er]))
    pg.locator("input[name=estado_nuevo][value=observado]").check()
    cu = []
    pg.on("request", lambda rq: cu.append(rq.post_data) if rq.method == "POST" and "/estado" in rq.url else None)
    pg.evaluate("""()=>{const b=document.getElementById('guardar-estado'),f=b.form;f.addEventListener('submit',()=>setTimeout(()=>sessionStorage.setItem('__est',JSON.stringify({dis:b.disabled,txt:b.innerText,busy:f.getAttribute('aria-busy')})),400))}""")
    pg.route("**/api/curatoria/**/estado", lambda rt: (time.sleep(2.5), rt.continue_()) if rt.request.method == "POST" else rt.continue_())
    pg.click("#guardar-estado"); pg.wait_for_timeout(4500)
    est = pg.evaluate("sessionStorage.getItem('__est')")
    chk(w, 5, F, est is not None and json.loads(est)["dis"], "durante la espera: %s" % est)
    body = json.loads(cu[0]) if cu else {}
    chk(w, 2, F, body.get("motivo") == "falta la foto de la cédula", "cuerpo motivo=%r" % body.get("motivo"))
    av = aviso(pg, ".aviso, [role=status], [role=alert]"); print("   avisos:", av[:3])
    chk(w, 9, F, any(a["role"] for a in av and [x for x in av if "estado" in x["t"].lower() or "listo" in x["t"].lower() or "observ" in x["t"].lower()]), "resultado: %s" % [(a["t"][:70], a["role"]) for a in av[:3]])
    print("   campos tras éxito: motivo=%r, radio marcado=%s" % (pg.input_value("#motivo-estado") if pg.locator("#motivo-estado:visible").count() else "(oculto)", pg.evaluate("[...document.querySelectorAll('input[name=estado_nuevo]')].filter(r=>r.checked).length")))
    print("   ERRS", [e for e in pg.errs if "401" not in e][:3])
    c.close()

with sync_playwright() as b_:
    b = lanzar(b_)
    c0, p0 = ctx(b, 1280); api_login(p0, D["CUR"]); ir(p0, "curatoria.html"); p0.wait_for_timeout(900)
    ref0 = p0.evaluate("[...document.querySelectorAll('a[href*=curatoria-expediente]')].map(a=>a.getAttribute('href').split('ref=')[1])[0]"); c0.close()
    curat(b, 1280, ref0)
