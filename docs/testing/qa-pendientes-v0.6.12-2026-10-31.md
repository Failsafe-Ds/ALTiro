# QA acotado de pendientes de pantalla, v0.6.12 (2026-10-31)

Entorno: altiro-dev (`https://localhost:8443`), Chromium de Playwright 1.63 en Docker (red `altiro-dev_frontal`), anchos 390 y 1280 px, cuentas demo (sin contraseñas en este documento). No se modificó código de producto.

## Resultados

| # | Punto | Resultado |
|---|---|---|
| 1a | Marcador `cargando-foto` en `mi-perfil` (maestro demo): con la imagen retrasada 2,5 s la clase está presente y el fondo es el degradado; al cargar se quita (`naturalWidth` 160). Con `route.abort` la imagen queda oculta, sin clase y sin icono roto | PASS (390 y 1280) |
| 1b | Visor de `curatoria-expediente` (cuenta de curatoría, expediente con fotos): clase presente durante la espera, se quita al cargar; con `abort` la imagen queda oculta, sin clase y el visor dice «No pudimos mostrar la foto. Revisa tu señal o tu wifi y toca «Reintentar»» | PASS (390 y 1280) |
| 1c | Visor de `mis-documentos` del maestro demo | BLOCKED: el maestro demo no tiene documentos cargados («Todavía no has enviado documentos»); no hay botón «Ver foto». Es el mismo `js/visor.js` verificado en 1b, pero no se vio en esa pantalla |
| 2 | `comercial.html` (cuenta comercial): encabezados H1, luego H2 por oficio, H3 «Servicios», H4 por servicio, y H2 de formularios ocultos; ningún salto de nivel en los visibles. axe (wcag2a/aa/21aa/22aa + best-practice) | PASS: 0 violaciones en 390 y 1280 |
| 3 | Avisos en «Mis trabajos»: aviso real generado por el flujo normal (cliente crea pedido, maestro acepta, cliente envía mensaje, que emite `mensaje_nuevo`). Primera carga: `#detalles-avisos` abierto con «(1 sin ver)»; recargada, ya visto, plegado y sin contador | PASS (390 y 1280) |
| 4 | RNF-02 (fila §4.2.2: «3 segundos o menos con una conexión móvil de 4 Mbps, y la primera pantalla no debe pesar más de 1,5 MB») | PASS para la portada (ver abajo) |

Observación al punto 3: crear un pedido solo no genera aviso al maestro; el aviso nace al enviar un mensaje (o en otras transiciones). Al ingresar por la pantalla, la página de aterrizaje ya marca los avisos como vistos antes de abrir «Mis trabajos»; por eso la prueba usó el ingreso por API.

## RNF-02, portada (`index.html`)

- Método: CDP `Network.emulateNetworkConditions` con 4 Mbps (500 000 B/s) de bajada y subida; el RNF no fija latencia, se usó **150 ms** (supuesto). Caché desactivada y contexto nuevo en cada corrida, 390 px, 3 corridas, `localhost` por la red interna de Docker (el proxy comprime con gzip).
- Corridas (LCP / load en ms): 584/577, 548/541, 552/544. FCP igual al LCP.
- Mediana: LCP 552 ms, load 544 ms, FCP 552 ms. Umbral: 3000 ms. Peso transferido de la primera pantalla: 97 KB (umbral 1,5 MB).
- Límite: el texto del RNF habla de «página de resultados»; aquí se midió la portada, como se pidió. La página de resultados de búsqueda no se midió en este QA.

## Defectos

Ninguno nuevo.

Evidencia: capturas `p1-*`, `p2-*`, `p3-*` en el directorio de trabajo de la sesión (no versionadas). Guiones de prueba en el mismo directorio (`qa/p.py`, `qa/p5.py`).
