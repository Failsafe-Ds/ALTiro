# QA del pulido posterior al S5 (v0.6.1, commit 93d31ce)

Fecha: 2026-10-11. Fuera de sprint. Alcance: ADR-002 E-3 y E-3.1, `design-system/altiro/MASTER.md`, `docs/testing/validaciones-minimas-pantalla.md` y las 9 validaciones mínimas de CLAUDE.md §8-§9. La suite de pytest (2088) y `scripts/validacion-pantalla/verificar.sh` ya habían pasado; no se repitieron.

## Ambiente

| Dato | Valor |
|---|---|
| Pila | `altiro-dev`, `https://localhost:8443` (proxy en la red `altiro-dev_frontal`) |
| Navegador | Chromium de `mcr.microsoft.com/playwright/python:v1.63.0-noble`; 360×740 táctil móvil y 1280×740; Playwright 1.63 |
| Red limitada | CDP: 4 Mbps bajada, 1 Mbps subida, 150 ms (D-19) para RNF-02; en los formularios, cada petición de envío se retrasa 2,5 s con `page.route` para observar el estado de espera |
| Equipo | Windows 11 Pro, Docker Desktop, equipo de desarrollo local |
| Scripts | `scripts/qa-pulido/` (`run.sh`, `lib.py`, `lib2.py`, `a`..`h`); leen `datos.json` (no versionado, con la contraseña al azar) |

## Cuentas de QA (sin contraseñas)

Creadas solo en `altiro-dev`, con `docker compose exec -T app python manage.py shell < prep_pulido.py` (servicios reales `identidad.servicios`: `crear_cuenta_cliente`, `crear_cuenta_maestro`, `crear_cuenta_administrativa`, `agregar_perfil_cliente`; fixture adaptado de `scripts/qa-s5/preparar_datos.py`). Una sola contraseña aleatoria de 16 caracteres (`contrasena_aleatoria`), impresa una vez y guardada solo en el directorio temporal del agente. Las cuentas demo no se tocaron.

| Cuenta | Rol | Cómo |
|---|---|---|
| `qa.pulido.cliente@example.com` | cliente | `crear_cuenta_cliente` (comuna 8101); en la corrida final se le cambió la contraseña con `cambiar_contrasena` (cuenta de QA, la contraseña de la primera corrida se perdió) |
| `qa.pulido.b.<sufijo>@example.com` | cliente | `crear_cuenta_cliente` |
| Maestro QA Pulido Uno (RUT ficticio 31309223-2) | maestro aprobado y publicado | `crear_cuenta_maestro` + oficio pintura, expediente `aprobado`, servicio (25.000 por trabajo), cobertura base 8101, disponibilidad 08:00-12:00 todos los días y foto marcada (el fixture usa un `foto` sin archivo; ver observación 4) |
| Maestro QA Pulido Dos | maestro aprobado y publicado | igual que el anterior |
| Maestro Revisión QA Pulido y Dos (RUT 31309225-9 y 31309226-7) | maestro con expediente `en_revision` | `crear_cuenta_maestro` (para la prueba de curatoría) |
| `qa.pulido.cur.*`, `qa.pulido.com.*`, `qa.pulido.mod.*`, `qa.pulido.ges.*` | curatoría, comercial, moderación, control de gestión | `crear_cuenta_administrativa` |
| `qa.pulido.dual.*` (RUT 31309227-5) | maestro y cliente | `crear_cuenta_maestro` + `agregar_perfil_cliente` |
| `qa.pulido.multi1@example.com`, `qa.pulido.multi2@example.com` | comercial + control de gestión; moderación + curatoría | `crear_cuenta_administrativa` con dos roles |
| Tickets del fixture | 1 pendiente, 1 aceptado, 3 finalizados, 1 cerrado | filas creadas por el modelo `Ticket` |

Residuos que quedan en `altiro-dev` (no se borró ningún volumen): las cuentas huérfanas de las dos primeras corridas del fixture (la primera falló por un `dia_semana` fuera de 1-7 y la segunda perdió la salida; sus contraseñas no se recuperaron), las cuentas `qa.pulido.reg*` y `qa.pulido.api*` de las pruebas de registro, y los datos de las pruebas (2 pedidos pendientes, mensajes, evaluaciones, 2 expedientes observados, foto de ruido en el maestro Uno, monto 26.000 y 27.000).

## Resultados por punto

| # | Punto | Resultado | Evidencia |
|---|---|---|---|
| 1 | Inicio por rol (E-3 punto 7) | PASS | Ingreso por la pantalla, sin `siguiente`, a 360 y 1280: cliente a `categorias.html`, maestro a `mis-trabajos.html`, curatoría a `curatoria.html`, comercial a `comercial.html`, moderación a `moderacion.html`, control de gestión a `indicadores.html`; el `href` de la marca coincide en cada caso. Dos roles: maestro + cliente va a `mis-trabajos`; comercial + gestión va a `comercial`; moderación + curatoría va a `curatoria` (orden E-3). `siguiente=servicios` (maestro) y `siguiente=moderacion` (cuenta multi) ganan sobre el inicio; con `siguiente` sin el rol (cliente) cae en `categorias.html`. Sin sesión, 7 páginas públicas × 2 anchos: el encabezado solo tiene `index.html` «AlTiro». |
| 2a | Sin «Volver» de navegación | PASS | Barrido de 26 pantallas (todas las páginas) en DOM, incluidos elementos ocultos: no hay `a[data-volver]` ni «Volver» de navegación. Quedan «No, volver» (confirmaciones), «Página anterior» (paginación) e «Ir al resumen», todos admitidos por E-3.1. Observación 1: el enlace «Vuelve a la ficha» de `pedir-trabajo` (resuelta en v0.6.2). |
| 2b | «← Paso anterior» solo en pasos y funcional tras recargar | PASS | Presente solo en registro-cliente, postulación, mi-postulación, pedir-trabajo y mis-servicios. Recargando en el último paso, el botón sigue visible, lleva al paso anterior y conserva los valores (registro: región y comuna; postulación: RUT, nombre, teléfono; pedir-trabajo: comuna; mis-servicios: oficio marcado; mi-postulación a 360). |
| 3 | Páginas de opciones | PASS | `cuenta` y las 6 del maestro, 360 y 1280: a 1280 el menú está a la izquierda (x=184, ancho 240) y el contenido a su derecha; a 360 el menú va arriba (plegable `details`, cerrado) y el contenido debajo; sin desborde horizontal. Un solo ítem con `aria-current="page"` (el de la página). Teclado: Tab recorre el resumen y los 6 enlaces, Enter navega y el ítem activo cambia; foco con contorno de 2 px. |
| 4.1 | Sin credenciales en el código | PASS | `grep` en `backend/`, `frontend/` e `infra/`: solo identificadores de campos y variables de `psql`; sin contraseñas, usuarios fijos ni atajos. |
| 4.2 | Cerrar pestaña o navegador en ingresar y volver | PASS | Contexto nuevo sin cookies: se ingresa (360 y 1280). Contexto nuevo con el estado de sesión vigente: `ingresar.html` muestra el formulario y no bloquea. |
| 4.3 | Largo + 1 | PASS | `maxlength` presente y tecleando de más queda en el máximo: nombre 150, teléfono 15, correo 254, RUT 12, contraseña 128, dirección 200, descripción 1000, monto 12, mensaje 1000, comentario 500, motivo 1000. La API responde 400 en el campo (sin 500): nombre/identificador/contraseña, dirección 201, descripción 1001, mensaje 1001, comentario 501, motivo 1001. Salvedad en DEF-QA-019 (espacios iniciales). |
| 4.4 | Espacios | FAIL | PASS en lo demás: `"  valor  "` se ve recortado al salir del campo y se envía/guarda recortado (nombre, correo, RUT con espacios, dirección, descripción, monto `$ 26.000`, mensaje, comentario, motivo; el mensaje con borrador restaurado lo recorta el servidor); solo espacios da «Completa este dato» (u otro texto del campo) junto al campo. FAIL: con «Mostrar contraseña» activo la contraseña sí se recorta (DEF-QA-016). Sin eso, la contraseña con espacios se guarda y se compara exacta (registro por API y por ingresar). |
| 4.5 | Indicador de carga y botón desactivado | PASS | En los 8 formularios el botón queda desactivado con texto «Enviando…» o «Guardando…» durante la espera (ingresar, registro, postulación, pedir-trabajo, mis-servicios, mensaje, evaluar, curatoría); `aria-busy="true"` en el formulario donde aplica. |
| 4.6 | Mensajes de error | PASS | Junto al campo, con `aria-invalid` y resumen «Hay N datos por corregir…» cuando son varios; el primer error está a la vista en todos los casos. Observación 5 / DEF-QA-020 (el error de un campo que queda al borde de la pantalla). |
| 4.7 | Un dato faltante no borra el resto | PASS | Registro, postulación, ingresar (la contraseña se limpia tras un ingreso fallido, a propósito), pedir-trabajo, mis-servicios (el monto fallido se conserva), evaluar (comentario y nota) y curatoría (motivo). |
| 4.8 | Limpiar tras el éxito y borrar el borrador | PASS | Mensaje: campo vacío y clave `altiro.conversacion.*` borrada. Curatoría: motivo y opción limpios. Pedir-trabajo y registro: borrador borrado y se pasa a la pantalla siguiente. (Evaluar: el formulario desaparece y queda la evaluación.) |
| 4.9 | Mensaje de resultado con `aria-live` | FAIL | PASS en registro, postulación, ingresar, pedir-trabajo, mis-servicios, curatoría (`role="status"` o `alert`). FAIL en `conversacion` (DEF-QA-017: el envío termina en error de JavaScript y no hay mensaje) y en `evaluar` (DEF-QA-018: no se modifica ninguna región viva). |
| 5 | Búsqueda y categorías | PASS | `categorias.html` (9 oficios): el enlace lleva a `buscar.html?oficio=gas` y el filtro queda con el oficio. Resultados (20), 360 y 1280: foto arriba del texto, `border 0`, sin sombra ni fondo (sin tarjeta), 1 solo enlace por resultado; nombre, «Verificado», oficio y «4,8 (3)» más el texto «Calificación: 4,8 de 5 (3 evaluaciones)» (no depende de las estrellas). Sin precio (decisión E-3.1 pendiente; DA-29 lo agregó después, ver «Verificación v0.6.2»). |
| 6a | RNF-02 | PASS | `buscar.html?oficio=pintura&region=8&comuna=8101`, Chromium con CDP 4 Mbps/150 ms, contexto nuevo (sin caché), 6 corridas: 81 KiB y 1,31 s hasta red inactiva (carga 0,67 s). Con una foto real de peor caso (JPEG de ruido de 1600×1200 subido por la pantalla; el servidor devolvió 60 KiB a 480 px y 3 KiB a 160 px) en el primer resultado: 140 KiB y 1,43 s. Umbrales: ≤ 1,5 MB y ≤ 3 s. Las fotos son `loading=lazy` con `srcset` 160w/480w; con las 20 a 60 KiB serían unos 1,3 MB (estimación, no medida). Las fotos demo son marcadores de 220 px. La fuente pesa 27 KiB. |
| 6b | RNF-16 (axe) | PASS | axe-core 4.10.3, reglas WCAG 2.2 A/AA, `index`, `buscar` (con resultados), `cuenta`, `curatoria`, `categorias`, `moderacion` y `mis-trabajos`, a 360 y 1280: 0 violaciones y 0 fallas de contraste (11 a 130 nodos de contraste aprobados por página, 0 incompletos). Es un muestreo con axe, no una medición manual de todos los pares de colores. |
| 7 | Consola sin CSP ni JS | FAIL | 27 pantallas × 2 anchos: 0 violaciones CSP. Un error de JavaScript: `formulario.resultado is not a function` (DEF-QA-017). Los demás mensajes son `Failed to load resource` por 401 de `GET /api/cuenta` en páginas públicas (observación 2) y 404 de fotos del fixture (observación 4). |

## Defectos

**DEF-QA-017** (alta). HU de mensajería (S5), CLAUDE.md §9 puntos 8-9. `frontend/js/conversacion.js:26` declara `const formulario = document.getElementById("formulario-mensaje")`, que oculta el módulo global `formulario`; la línea 268 llama `formulario.resultado(...)` y falla con `TypeError`.
- Pasos: cliente `qa.pulido.cliente`, `conversacion.html?ticket=<aceptado>`, escribir «Prueba» y enviar.
- Esperado: «Mensaje enviado.» anunciado, el mensaje aparece en la lista, el foco vuelve al campo.
- Observado: el mensaje sí se guarda (el servidor lo recorta), el campo se limpia, pero sale `pageerror`, no hay aviso, la lista no cambia (2 mensajes antes y después) y se salta `consultarNuevos` y el foco; solo aparece al recargar. El usuario puede creer que no se envió y reescribirlo (nueva clave de envío, duplicado).
- Responsable: frontend (renombrar la variable local). La prueba estática del repositorio no lo detecta; conviene una prueba de navegador para el envío.
- **Estado: Corregido (v0.6.2).** `frontend/js/conversacion.js`: la variable local pasó a `formMensaje`; ninguna otra página redeclara `formulario`, `dom`, `api` ni `formato` (grep). Verificado con `e5.py`: 0 errores JS, aviso «Mensaje enviado.», el mensaje aparece sin recargar y el foco vuelve al campo.

**DEF-QA-016** (media). CLAUDE.md §9 punto 2 («la contraseña no se recorta»), ADR-013 punto 3. `formulario.js`, `recortable()` decide por `campo.type`: al activar «Mostrar contraseña» el campo pasa a `type=text` y se recorta (al salir del campo y al leer).
- Pasos: `ingresar.html`, escribir `"  abc  "` en contraseña, activar «Mostrar contraseña», enviar. Igual en registro-cliente/postulación.
- Esperado: el cuerpo lleva `"  abc  "`. Observado: lleva `"abc"`. En registro, quien activa la casilla y escribe espacios en los bordes crea la cuenta con la contraseña recortada y después no puede ingresar escribiendo lo que tecleó con espacios; medido: registro con la casilla activa, ingreso con los espacios exactos 401, recortada 200. El registro por API directa con espacios sí guarda exacta.
- Responsable: frontend.
- **Estado: Corregido (v0.6.2).** `frontend/js/formulario.js`: `esContrasena()` reconoce el campo por `autocomplete` `current-password`/`new-password` o `data-contrasena`, no por el `type`; lo usan `recortable`, el borrador y su restauración. Verificado con `d1.py` (registro y postulación: ingreso con espacios exactos 200) y `d2.py` (ingresar con «Mostrar contraseña»: cuerpo `"  abc  "`). Cubre también cuenta y nueva-contraseña, que comparten el mismo `autocomplete`.

**DEF-QA-018** (baja). CLAUDE.md §9 punto 9. `evaluar.js`, éxito (201): recarga la tarjeta «Tu evaluación» y mueve el foco al título, pero ningún `role="status"`/`aria-live` recibe un mensaje (observador de mutaciones sin cambios en regiones vivas). El foco al título mitiga parcialmente para lectores de pantalla. El inventario `validaciones-minimas-pantalla.md` lo da como «Sí». Responsable: frontend.
- **Estado: Corregido (v0.6.2).** `frontend/evaluar.html` (región `#resultado-envio`, `role="status"`) y `evaluar.js` (`formulario.resultado`, también tras la denuncia). Verificado con `e5.py`: región viva con «Tu evaluación quedó registrada.».

**DEF-QA-019** (baja). CLAUDE.md §9 puntos 1-2. `maxlength` igual a la forma escrita más larga deja sin margen a los espacios de los bordes: teclear `"  +56 9 1234 5678"` (teléfono, 15) queda `"  +56 9 1234 56"`; al recortar, el número queda `+56 9 1234 56` y el servidor lo rechaza con «Ingresa tu teléfono con 9 dígitos…», sin explicar el corte. Igual con RUT (12) y monto (12) si hay espacios iniciales o se pega con ellos. Esperado: recortar al pegar o dar margen al `maxlength`. Responsable: frontend (el servidor ya valida y recorta).
- **Estado: Corregido (v0.6.2).** `formulario.js`: al escribir (`input`) y al pegar (`paste`) se quitan los espacios iniciales antes de que `maxlength` corte; se eligió esto en vez de ampliar `maxlength` para no inventar otro largo que el del servidor. Verificado con `d1.py`: `"  +56 9 1234 5678"` queda `+56 9 1234 5678` completo.

**DEF-QA-020** (baja). CLAUDE.md §9 punto 4 («visibles sin desplazarse»). `formulario.mostrarErrores` hace `focus()` y el navegador deja el campo pegado al borde inferior; el texto de error, que está debajo, queda fuera de pantalla. Medido en `mis-servicios`, «Cambiar precio» con solo espacios, 360×740: campo termina en y=739,8 y el error empieza en y=745 (alto de pantalla 740). A 360×640 sí se ve. En registro-cliente y pedir-trabajo el segundo error también queda bajo el pliegue a 740 px (el primero y el resumen sí se ven). Esperado: `scrollIntoView({block:"center"})` o foco sin desplazamiento más un `scrollIntoView` del error. Responsable: frontend.
- **Estado: Corregido (v0.6.2).** `formulario.mostrarErrores`: `focus({preventScroll:true})` y `scrollIntoView({block:"center"})` (`behavior:auto` con `prefers-reduced-motion`). Verificado con `scripts/qa-pulido/v62.py`: mis-servicios, «Cambiar precio» con espacios, 360×740: campo y=345-396 y error y=401-427 (alto 740).

## Observaciones (sin defecto)

1. (Resuelta en v0.6.2: el texto pasó a «Ir a la ficha del maestro»; el `href` no cambia.) `pedir-trabajo` conserva el enlace de texto «¿No es lo que buscabas? Vuelve a la ficha» (`#enlace-volver-ficha`). No es un botón «Volver» de los que lista E-3 punto 6, pero cumple su función; el coordinador decide si se quita.
2. En todas las páginas públicas `menu.js` consulta `GET /api/cuenta` y el visitante recibe un 401 que Chromium muestra como error en la consola. No es un error de CSP ni de JavaScript; es ruido que molesta al revisar consolas.
3. Las dos primeras corridas del fixture dejaron cuentas huérfanas (ver arriba).
4. Los maestros del fixture (QA Pulido Uno/Dos) tienen un `foto` sin archivo, y sus resultados de búsqueda dan 404 y una imagen rota (artefacto del fixture, no de producto; en producto `foto` solo se marca tras subir un archivo). El maestro Uno quedó con una foto de ruido real.
5. El nivel de detalle de los mensajes de campo vacío es «Completa este dato.»; dice qué hacer junto al campo, aunque no el motivo. Se acepta como PASS en 4.6.
6. Limitaciones: móvil emulado (Chromium en un contenedor), no un teléfono real; la red limitada de los formularios es un retraso de 2,5 s por petición, no un perfil de ancho de banda; solo Chromium (RNF-18 no entra en este incremento).

## Siguiente paso

Devolver DEF-QA-017 y DEF-QA-016 al agente frontend (críticos para la defensa: el envío de un mensaje y «Mostrar contraseña»), junto con DEF-QA-018, -019 y -020. Tras la corrección, repetir solo `scripts/qa-pulido/d1.py`, `d2.py`, `d5.py` y `e5.py`. Después se puede cerrar la v0.6.1.

## Verificación v0.6.2 (frontend)

Cuentas de QA: nueva corrida de `prep_pulido.py` en `altiro-dev` (contraseña al azar nueva en `datos.json`, borrado después; cuentas demo sin tocar). `d5.py` ahora toma el expediente en revisión desde la lista de curatoría. Resultados: `d1.py`, `d2.py` y `d5.py` sin FAIL; `e5.py` sin error JS; `verificar.sh` casos=3085 fallos=0; `test_frontend_pie_volver.py` 62 passed.
Precio en resultados (DA-29, `.precio-tarjeta`), `buscar.html?oficio=pintura&region=8&comuna=8101`: 20 resultados con «$25.000 por trabajo», «Desde $8.500 por hora», a 360 y 1280 px, sin desborde horizontal, 17 px.
