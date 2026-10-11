from lib2 import *
SUF = "".join(random.choice(string.digits) for _ in range(6))
with sync_playwright() as b_:
    b = lanzar(b_)
    c, pg = ctx(b, 360); ir(pg, "registro-cliente.html")
    pwd = "  " + "-".join("".join(random.choice(string.ascii_letters + string.digits) for _ in range(5)) for _ in range(4)) + "  "
    correo = "qa.pulido.api%s@example.com" % SUF
    # 1) por la API directa (sin formulario.js)
    r = api(pg, "/api/clientes", {"nombre": "Qa Pulido Api", "telefono": "+56912340000", "correo": correo, "comuna": "15101", "contrasena": pwd})
    print("registro API directa:", r[0], json.dumps(r[1])[:200])
    c.close()
    for p_, et in ((pwd, "exacta con espacios"), (pwd.strip(), "recortada"), (" " + pwd.strip(), "un espacio inicial")):
        c, pg = ctx(b, 360); print("login", et, api_login(pg, correo, p_)); c.close()
    # 2) ¿qué manda el formulario? capturar el cuerpo
    c, pg = ctx(b, 360); ir(pg, "registro-cliente.html")
    cuerpos = []
    pg.on("request", lambda rq: cuerpos.append(rq.post_data) if rq.method == "POST" and "/api/clientes" in rq.url else None)
    pg.fill("#nombre", "Qa Pulido Form"); pg.fill("#telefono", "9 1234 0001"); pg.fill("#correo", "qa.pulido.f%s@example.com" % SUF)
    pg.locator("button:visible:has-text('Continuar')").first.click(); pg.wait_for_timeout(400)
    pg.select_option("#region", index=1); pg.wait_for_timeout(600); pg.select_option("#comuna", index=1)
    pg.locator("button:visible:has-text('Continuar')").first.click(); pg.wait_for_timeout(400)
    pg.fill("#contrasena", pwd); pg.locator("input[type=checkbox]:visible").first.check()
    pg.locator("button[type=submit]:visible").click(); pg.wait_for_timeout(2500)
    cu = json.loads(cuerpos[0]) if cuerpos else {}
    print("cuerpo enviado por el formulario: contrasena repr =", repr(cu.get("contrasena")), "largo", len(cu.get("contrasena", "")), "(esperado", len(pwd), ")")
    c.close()
    # 3) ingresar: el formulario ¿recorta la contraseña?
    c, pg = ctx(b, 360); ir(pg, "ingresar.html"); cuerpos = []
    pg.on("request", lambda rq: cuerpos.append(rq.post_data) if rq.method == "POST" and "/api/sesion" in rq.url else None)
    pg.fill("#identificador", correo); pg.fill("#contrasena", pwd); pg.locator("button[type=submit]").click(); pg.wait_for_timeout(2000)
    cu = json.loads(cuerpos[0]) if cuerpos else {}
    print("ingresar envía contrasena repr =", repr(cu.get("contrasena")), "largo", len(cu.get("contrasena", "")))
    c.close()
