# ADR-002 — Estilo de interfaz

- Estado: **Aceptada** — 2026-09-27, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-27
- Relacionado con: RF-02, RNF-02, RNF-07, RNF-08, RNF-20

## Contexto
El informe define frontend en HTML, CSS y JavaScript (§4.1). Hay que decidir si el servidor entrega plantillas o una API. RNF-08 se comprueba "revisando lo que el servidor manda y no lo que la pantalla muestra".

## Decisión propuesta
API JSON bajo `/api/` y un frontend estático (HTML/CSS/JS sin framework) servido por el proxy.

## Supuesto a validar
Con frontend estático, el HTML de una página privada puede descargarse sin sesión, pero no contiene datos: todos los datos privados se obtienen de `/api/`, que exige autenticación. Se interpreta que esto cumple RF-02 ("Un usuario no autenticado no accede a ninguna vista privada"). Si el equipo no acepta esta interpretación, la alternativa es servir las páginas privadas desde Django tras verificar la sesión.

## Alternativas consideradas
- **Plantillas renderizadas en el servidor**: menos JavaScript, pero verificar RNF-08 es más directo sobre JSON.

## Consecuencias
- Pruebas de privacidad y de autorización sobre respuestas JSON.
- El frontend maneja CSRF y los errores en `js/api.js`.
- Sin framework, el peso de página favorece RNF-02.
- Al conservar el progreso de formularios (RNF-20), nunca se guarda la contraseña y se minimizan los datos personales en `localStorage`, porque hay teléfonos compartidos.

## Enmiendas

### E-1 — Vencimiento del progreso guardado en el navegador (M-4)
- **Fecha:** 2026-09-28.
- **Motivo:** el progreso de los formularios (RNF-20) quedaba en sessionStorage sin vencimiento. En un teléfono compartido podía quedar el RUT, el correo o el teléfono escrito por otra persona. Es el hallazgo M-4 de la revisión `ux` (`docs/testing/saneamiento-sprint-1.md`, anexo).
- **Cambio:**
  - Todo lo guardado lleva la hora del último cambio y **vence a las 2 horas**. El plazo se reinicia con cada cambio.
  - Al cargar una página con formularios se borran las claves `altiro.*` vencidas.
  - Al cerrar sesión con éxito se borran todas las claves `altiro.*`.
  - Nunca se guarda la contraseña.
- **Por qué 2 horas:** la sesión vence a los 30 minutos (RNF-09) y la postulación debería tomar 10 minutos o menos (RNF-13). Dos horas dan margen para recuperar la señal y volver a ingresar (RNF-20) sin conservar los datos indefinidamente.
- **Aprobación:** equipo de desarrollo, 2026-09-28 (Sprint 2, incremento 0).

## Enmienda 2026-10-01: pie de página y «← Volver»

- Pie `<footer class="pie" role="contentinfo">` estático en todas las páginas (también `errores/`) con copyright y aviso de prueba de concepto. La versión sale de un solo archivo, `frontend/js/version.js` (`ALTIRO_VERSION`, se cambia en cada iteración), y `js/pie.js` la escribe en el pie.
- Enlace `← Volver` (`a[data-volver]`, `href` de respaldo real) en el encabezado de todas las páginas salvo `index.html`, `errores/*` y las tres que ya tienen enlace a su padre (`conversacion`, `evaluar`, `curatoria-expediente`). `js/volver.js` usa `history.back()` si el origen anterior es del mismo sitio o si hay un paso interno; si no, sigue el respaldo.
- Pasos internos con `history.pushState({altiroPaso})`: `buscar.js` (formulario, horario, resultados) y `formulario.porPasos` (postulación, pedir trabajo). Atrás del teléfono retrocede un paso sin perder lo escrito (RNF-20).

### E-2 — Estructura header/main/footer y menú principal por sesión y rol
- **Fecha:** 2026-10-04.
- **Motivo:** las opciones de «Mi cuenta» salían como tarjetas con párrafos y botones; no había navegación común. Pedido del usuario: header, cuerpo y pie, y un menú.
- **Cambio (solo presentación):**
  - Todas las páginas (salvo `errores/`) tienen `<header class="encabezado">`, `<main>` y el pie existente. `index.html` suma el encabezado con la marca. «← Volver» queda como estaba.
  - `frontend/js/menu.js` (un solo archivo, sin dependencias) agrega al encabezado un botón «Menú» (`aria-expanded`, `aria-controls`, Escape cierra, objetivos de 44 px) con la lista de enlaces según `GET /api/cuenta`: sin sesión (Buscar, Ingresar, Crear mi cuenta, Postular); cliente (Mis pedidos); maestro (Mis trabajos, Mi perfil, Mi agenda, Mis servicios); curatoría, comercial, moderación y control de gestión (su bandeja); todos con sesión: Mi cuenta y Salir. Es un botón desplegable en todos los anchos.
  - `cuenta.html`: las tarjetas de accesos pasan a listas de enlaces agrupadas por sección (mismos ids `accesos-*` y misma lógica de `cuenta.js`); «Seguridad de mi cuenta» queda plegada en `<details>`; los formularios de agregar perfil pierden el recuadro.
- **Seguridad:** el menú no autoriza; cada ruta de la API sigue exigiendo identidad, rol y propiedad. «Salir» usa `DELETE /api/sesion` y `formulario.olvidarTodo()`, igual que «Cerrar sesión».
- **Costo:** una consulta `GET /api/cuenta` por página para armar el menú (RNF-02: JS nuevo ~4 KB).

### E-3 — Rediseño visual: referencia Fiverr, tonos rojos, navegación por la marca e inicio por rol
- **Fecha:** 2026-10-11. **Estado:** decisión del usuario; **pendiente de implementar**. Los puntos marcados como PROVISIONAL los propuso Claude y se revisan con el equipo.
- **Motivo:** al equipo no le convence el frontend actual. Dio una referencia concreta en lugar de pedir "hacerlo mejor".
- **Cambio:**
  1. **Referencia visual: Fiverr.** Se toma de Fiverr la forma de los enlaces y la forma de mostrar a los trabajadores en la búsqueda: **foto arriba y la información debajo** (nombre, oficio, estrellas, precio), **sin recuadro de tarjeta**.
  2. **Paleta:** predominan los tonos **rojos**. Se siguen cumpliendo el contraste (RNF-16) y la regla de no comunicar un estado solo con el color.
  3. **Páginas de opciones** («Mi cuenta» y similares): menú de secciones a la izquierda y el contenido de la sección elegida a la derecha, como la configuración de Steam. En el celular (mobile-first, RNF-14), el menú pasa arriba del contenido, porque a la izquierda no cabe.
  4. **Pie:** copyright en todas las páginas (ya existe, enmienda 2026-10-01).
  5. **Encabezado en dos versiones:**
     - **sin sesión:** solo el nombre **AlTiro**, que lleva a `index.html`. Sirve para salir de un formulario abierto por error. Ingresar, Crear cuenta y Postular quedan en el cuerpo de `index.html`, no en el encabezado. Esto reemplaza el menú sin sesión de E-2;
     - **con sesión:** el nombre **AlTiro** lleva a la página de inicio del rol (punto 7), no a un formulario. El menú por rol de E-2 se mantiene.
  6. **Se eliminan todos los botones «Volver»:** el `← Volver` del encabezado (`a[data-volver]`, `js/volver.js`), «Volver a la cola», el «Volver» de `conversacion` y `evaluar`, y el «Volver» entre los pasos de `buscar`. El nombre AlTiro cumple esa función. **Se mantiene** el botón Atrás del navegador y del teléfono (los pasos con `history.pushState` de la enmienda 2026-10-01), que no es un botón de la página, y no pierde lo escrito (RNF-20).
  7. **Inicio por rol** (destino por defecto tras ingresar y destino del nombre AlTiro con sesión):
     - **cliente:** la página de **categorías (oficios)** para ver maestros, al estilo Fiverr. Es la entrada a la búsqueda (RF de búsqueda y catálogo), no una funcionalidad nueva;
     - **maestro:** `mis-trabajos.html` (sus pedidos);
     - **curatoría:** `curatoria.html` (expedientes por revisar);
     - PROVISIONAL: **comercial** → `comercial.html`; **moderación** → `moderacion.html`; **control de gestión** → `indicadores.html`;
     - PROVISIONAL: **cuenta con varios roles** → el primero de este orden: curatoría, moderación, comercial, control de gestión, maestro, cliente. Los demás quedan en el menú;
     - el parámetro `siguiente` de `ingresar.js` sigue teniendo prioridad sobre el inicio por rol.
- **Restricciones que siguen vigentes:** HTML, CSS y JS propios, sin Tailwind ni Bootstrap; CSP estricta sin estilos ni scripts inline (los estilos van en `frontend/css/`); objetivos táctiles de 44 px; validaciones mínimas de CLAUDE.md §9. La skill de diseño UI/UX Pro Max, si se usa, se pide con la pila `html-css`, nunca `html-tailwind`.
- **Seguridad:** el inicio por rol es solo navegación; el servidor sigue decidiendo qué ve cada cuenta.

#### E-3.1 — Parte 2 (2026-10-11, PROVISIONAL)
- **Estado:** implementado en el árbol de trabajo (v0.6.1). Decisiones del coordinador, PROVISIONAL hasta la revisión con el equipo.
- **«← Paso anterior»:** control del formulario por pasos (`registro-cliente`, `postulacion-maestro`, `mi-postulacion`, `pedir-trabajo`, `mis-servicios`), botón secundario con el mismo texto en todos. No es un «Volver» de navegación entre páginas (punto 6): sin él, un formulario restaurado en el paso 2 tras recargar no puede llegar al paso 1 (no hay historial, RNF-20). «Volver al resumen» de `mi-postulacion` pasa a «Ir al resumen»; la confirmación de precio de `mis-pedidos` usa «No, volver», como las demás confirmaciones. `tests/test_frontend_pie_volver.py` permite exactamente «← Paso anterior» y solo en esas cinco páginas.
- **Páginas de opciones (punto 3):** un solo componente, `frontend/js/opciones.js`. La página marca `<main data-opciones>`; el componente arma el menú (grupo «Mi cuenta»: Mis datos, Seguridad, Mis perfiles; grupo «Mi trabajo como maestro» si la cuenta tiene perfil de maestro: Mi perfil, Mis servicios, Mi cobertura, Mi agenda, Mis documentos, Mi postulación). Usa la cuenta que ya pidió `menu.js` (`window.altiroCuenta`), sin una segunda consulta. En 768 px o más, menú a la izquierda (15 rem, ítem activo con `aria-current="page"`, `--marca-suave` y barra roja de 3 px); en el celular, arriba y plegado en `<details>` con la sección actual. En `cuenta.html` las secciones (`#datos`, `#seguridad`, `#perfiles`) son ítems del menú y se muestra una a la vez; «Seguridad de mi cuenta» deja de ser un `<details>` y suma «Cerrar sesión».
- **Bandejas administrativas** (`curatoria`, `moderacion`, `comercial`, `indicadores`): sin menú lateral, porque cada una es un solo flujo (lista y detalle, o formulario y resultado), no secciones independientes.
- **Sin precio en los resultados de búsqueda:** RF-13 no lo exige y agregarlo amplía el alcance; queda como pregunta al usuario (el MASTER lo menciona como «Desde $X», pendiente).
- **Validaciones mínimas (CLAUDE.md §9) en `formulario.js`:** recorte de espacios al salir del campo y al leer (nunca en contraseñas), `errorRut`/`errorIdentificador` aceptan espacios en los bordes (paridad con el servidor), resumen con la cantidad de datos por corregir y foco en el primer campo con error, `ocupado(form, sí, texto)`, `terminado(form, texto, clave)` y `resultado(caja, texto, tipo)`. `maxlength` igual al servidor; teléfono, RUT y montos usan el largo de su forma escrita más larga que el servidor acepta (detalle en `docs/testing/validaciones-minimas-pantalla.md`).
