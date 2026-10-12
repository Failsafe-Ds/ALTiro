"""Capturas de pantalla de páginas públicas de altiro-dev, para revisar el diseño
(ADR-002 E-4). Corre en la imagen de Playwright, en la red del proxy de desarrollo.
No usa cuentas ni contraseñas: solo páginas sin sesión.

Uso (Git Bash, desde la raíz del repositorio):
  MSYS_NO_PATHCONV=1 docker run --rm --network altiro-dev_frontal \
    -v "$(pwd -W)/scripts/qa-pulido:/w" -v "<carpeta de salida>:/out" \
    mcr.microsoft.com/playwright/python:v1.63.0-noble \
    sh -c "pip install -q playwright==1.63.0; python /w/capturas.py 'index.html,categorias.html' 360,1280"

Notas:
- El proxy solo acepta el nombre «localhost» (ALLOWED_HOSTS): por eso el
  navegador resuelve localhost a la IP del contenedor «proxy».
- Las capturas de la extensión de Chrome se congelaban en este equipo; este
  script es la forma confiable de ver la pantalla.
"""
import socket
import sys

from playwright.sync_api import sync_playwright

rutas = sys.argv[1].split(",")
anchos = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [360, 1280]

with sync_playwright() as p:
    ip = socket.gethostbyname("proxy")
    navegador = p.chromium.launch(args=["--ignore-certificate-errors", f"--host-resolver-rules=MAP localhost {ip}"])
    for ancho in anchos:
        contexto = navegador.new_context(viewport={"width": ancho, "height": 800}, ignore_https_errors=True, locale="es-CL")
        pagina = contexto.new_page()
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)[:150]))
        for ruta in rutas:
            pagina.goto("https://localhost/" + ruta)
            pagina.wait_for_load_state("networkidle")
            pagina.wait_for_timeout(400)
            nombre = ruta.split("?")[0].replace(".html", "") or "index"
            pagina.screenshot(path=f"/out/{nombre}-{ancho}.png", full_page=True)
        print(ancho, "errores de JS:", errores)
        contexto.close()
