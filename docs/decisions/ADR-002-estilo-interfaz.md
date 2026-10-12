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
- **Restricciones que siguen vigentes:** HTML, CSS y JS propios, sin Tailwind ni Bootstrap (Bootstrap se permite desde E-4); CSP estricta sin estilos ni scripts inline (los estilos van en `frontend/css/`); objetivos táctiles de 44 px; validaciones mínimas de CLAUDE.md §9. La skill de diseño UI/UX Pro Max, si se usa, se pide con la pila `html-css`, nunca `html-tailwind`.
- **Seguridad:** el inicio por rol es solo navegación; el servidor sigue decidiendo qué ve cada cuenta.

#### E-3.1 — Parte 2 (2026-10-11, PROVISIONAL)
- **Estado:** implementado en el árbol de trabajo (v0.6.1). Decisiones del coordinador, PROVISIONAL hasta la revisión con el equipo.
- **«← Paso anterior»:** control del formulario por pasos (`registro-cliente`, `postulacion-maestro`, `mi-postulacion`, `pedir-trabajo`, `mis-servicios`), botón secundario con el mismo texto en todos. No es un «Volver» de navegación entre páginas (punto 6): sin él, un formulario restaurado en el paso 2 tras recargar no puede llegar al paso 1 (no hay historial, RNF-20). «Volver al resumen» de `mi-postulacion` pasa a «Ir al resumen»; la confirmación de precio de `mis-pedidos` usa «No, volver», como las demás confirmaciones. `tests/test_frontend_pie_volver.py` permite exactamente «← Paso anterior» y solo en esas cinco páginas.
- **Páginas de opciones (punto 3):** un solo componente, `frontend/js/opciones.js`. La página marca `<main data-opciones>`; el componente arma el menú (grupo «Mi cuenta»: Mis datos, Seguridad, Mis perfiles; grupo «Mi trabajo como maestro» si la cuenta tiene perfil de maestro: Mi perfil, Mis servicios, Mi cobertura, Mi agenda, Mis documentos, Mi postulación). Usa la cuenta que ya pidió `menu.js` (`window.altiroCuenta`), sin una segunda consulta. En 768 px o más, menú a la izquierda (15 rem, ítem activo con `aria-current="page"`, `--marca-suave` y barra roja de 3 px); en el celular, arriba y plegado en `<details>` con la sección actual. En `cuenta.html` las secciones (`#datos`, `#seguridad`, `#perfiles`) son ítems del menú y se muestra una a la vez; «Seguridad de mi cuenta» deja de ser un `<details>` y suma «Cerrar sesión».
- **Bandejas administrativas** (`curatoria`, `moderacion`, `comercial`, `indicadores`): sin menú lateral, porque cada una es un solo flujo (lista y detalle, o formulario y resultado), no secciones independientes.
- **Sin precio en los resultados de búsqueda:** RF-13 no lo exige y agregarlo amplía el alcance; queda como pregunta al usuario (el MASTER lo menciona como «Desde $X», pendiente).
- **Validaciones mínimas (CLAUDE.md §9) en `formulario.js`:** recorte de espacios al salir del campo y al leer (nunca en contraseñas), `errorRut`/`errorIdentificador` aceptan espacios en los bordes (paridad con el servidor), resumen con la cantidad de datos por corregir y foco en el primer campo con error, `ocupado(form, sí, texto)`, `terminado(form, texto, clave)` y `resultado(caja, texto, tipo)`. `maxlength` igual al servidor; teléfono, RUT y montos usan el largo de su forma escrita más larga que el servidor acepta (detalle en `docs/testing/validaciones-minimas-pantalla.md`).

### E-3.2 — Dos flujos para cuentas con dos roles, y ajustes de pantalla (2026-10-11)
- **Pedido del usuario** tras revisar la v0.6.2.
- **Marca «AlTiro» según el flujo en que está la persona** (reemplaza el orden fijo de E-3 punto 7 para cuentas con cliente y maestro):
  - **flujo cliente:** `categorias`, `buscar`, `perfil-maestro`, `pedir-trabajo`, `mis-pedidos`, `evaluar` y `conversacion` cuando la persona es el cliente del pedido. La marca lleva a `categorias.html`;
  - **flujo maestro:** `mis-trabajos`, `mi-perfil`, `mis-servicios`, `mi-cobertura`, `mi-agenda`, `mis-documentos`, `mi-postulacion`, y `conversacion`/`evaluar` cuando es el maestro del pedido. La marca lleva a `mis-trabajos.html`;
  - **páginas neutras** (`cuenta`, `index`, administrativas): se usa el último flujo visitado, guardado en `sessionStorage` (`altiro.flujo`, sin datos personales), o el orden de E-3 si no hay uno;
  - el **menú** permite cambiar de flujo: «Buscar maestros» y «Mi trabajo como maestro».
- **«Cerrar sesión en este dispositivo»**: no se intenta adivinar si es teléfono o computador, porque el navegador no lo informa de forma confiable.
- **«Mi cuenta»:** los botones de acción de una misma sección van en una fila (se envuelven en el celular), no apilados.
- **Ingresar:** formulario centrado, con ancho de lectura y alineación consistente.
- **RUT:** al salir del campo se muestra con formato (`11.111.111-1`), para que se vea qué se escribió.

### E-3.3 — Carrusel de oficios, contenido centrado en las tarjetas y encabezado con degradado (2026-10-11)
- **Pedido del usuario** tras la v0.6.3.
- **Categorías en carrusel:** la página de categorías muestra los oficios en un carrusel horizontal, para que el catálogo pueda crecer (RF-36, DA-31) sin una grilla desbalanceada. Es accesible: botones «Anterior» y «Siguiente» con texto accesible, desplazamiento con el dedo y con el teclado, `scroll-snap` nativo de CSS, sin avance automático y sin animación con `prefers-reduced-motion`. Sin bibliotecas. La lista de oficios de la postulación sigue como casillas, porque ahí se marcan varios y un carrusel lo haría más difícil.
- **Contenido centrado en las tarjetas:** el ícono, el nombre y los textos de cada tarjeta (oficios y bloques del mismo tipo) van centrados, no pegados a la izquierda. Los formularios y los textos largos siguen alineados a la izquierda, porque así se leen mejor.
- **Encabezado:** fondo con un degradado suave de rojo claro al color del fondo, para separarlo del cuerpo. Los valores están en `design-system/altiro/MASTER.md` y deben mantener el contraste de la marca y del botón «Menú» (RNF-16).

### E-4 — Bootstrap 5.3 en el frontend y React permitido (2026-10-12)
- **Decisión del usuario** (2026-10-12): «vamos a añadir Bootstrap porque el front la verdad lo necesita, también se permite de ahora en adelante React». Levanta la restricción de E-3 («sin Tailwind ni Bootstrap») y la de `frontend.md`.
- **Bootstrap 5.3.8 (licencia MIT), alojado en el sitio:** `frontend/vendor/bootstrap-5.3.8/` (`bootstrap.min.css`, `bootstrap.bundle.min.js` y `LICENSE`), sin CDN, porque la CSP solo permite `'self'`. Bajado del registro oficial de npm; el paquete coincidió con su integridad publicada (`sha512-HP1SZDqaLDPwsNiqRqi5NcP0SSXciX2s9E+RyqJIIqGo+vJeN5AJVM98CXmW/Wux0nQ5L7jeWUdplCEf0Ee+tg==`). SHA-256 de los archivos copiados:
  - `bootstrap.min.css` `d85327d99c7a3ee1f9b5d0500d1370acea3ad2db39c163c2f51f232baedbdede`
  - `bootstrap.bundle.min.js` `e4fd49181388c48ec5040bd3fe66f57c29c8e67fcd8502b3354b96ec7ab47cc7`
  - Los archivos no se editan: para cambiar de versión se agrega otra carpeta y se registra aquí.
- **Cómo se usa:**
  - el CSS de Bootstrap se carga en **todas** las páginas antes de `css/base.css`, así que MASTER sigue mandando: `base.css` le pasa los colores, la fuente y el radio de AlTiro (variables `--bs-*`) y deshace lo del reinicio que MASTER no quiere (`legend` flotante, `h3`/`h4`);
  - el JS (`bootstrap.bundle.min.js`, con Popper) se carga **solo en las páginas que usan un componente con JS** (hoy, `categorias.html` para el carrusel), para no sumar peso (RNF-02);
  - se usa Bootstrap donde ahorra código o mejora el resultado (carrusel, grilla, utilidades como `text-center`). Las clases propias (`boton`, `aviso`, `tarjeta`…) siguen y no se reescriben de una vez: se migra pantalla por pantalla, cuando se toque cada una;
  - la CSP no cambia: Bootstrap no necesita `unsafe-inline` ni `unsafe-eval` (sus íconos SVG en `data:` ya están permitidos por `img-src 'self' data:`).
- **Carrusel de oficios:** reemplaza el carrusel de `scroll-snap` de E-3.3, que en PC mostraba los 9 oficios en una fila y ocultaba los botones, así que no se veía como carrusel. Ahora es el carrusel de Bootstrap con 3 oficios por diapositiva en toda pantalla (los 9 quedan en 3 diapositivas parejas), con «Anterior», «Siguiente» y puntos de posición de 44 px, deslizable con el dedo, sin avance automático y dando la vuelta al final. En el celular los botones muestran solo la flecha (el texto queda para los lectores de pantalla).
- **Contenido centrado (complementa E-3.3):** además de la caja, va centrado lo que hay dentro en la portada del inicio, «Tu cuenta» (sus 3 accesos en una sola fila desde 640 px), las tarjetas de oficios, las tarjetas de maestros de la búsqueda y el resumen de la búsqueda. El texto de los botones de varias líneas también va centrado.
- **React permitido, con condiciones:** se puede usar en pantallas nuevas o rehechas donde el estado de la interfaz lo justifique. Como la CSP prohíbe `unsafe-eval` y scripts de otros dominios, React **no** se carga desde CDN ni con Babel en el navegador: requiere un paso de compilación (por ejemplo Vite en un contenedor `node` de Docker Compose, porque el equipo no tiene Node instalado) que deje los archivos finales en `frontend/`, con dependencias fijadas en un `package-lock.json`. Cuando se adopte para la primera pantalla, se registra como enmienda (E-5) con el impacto en el peso de página (RNF-02) y en las pruebas de pantalla.
- **Restricciones que siguen vigentes:** CSP estricta sin estilos ni scripts en línea; sin Tailwind ni shadcn; objetivos táctiles de 44 px; contraste de MASTER (RNF-16); validaciones mínimas de CLAUDE.md §9.

### E-4.1 — Carrusel en abanico y encabezado rojo (2026-10-12)
- **Pedido del usuario** (2026-10-12): «vamos a hacerlo dinámico, el carrusel solo aplica a las categorías…, que sea un carrusel grande en diagonal, el header más rojo y los botones en el header con relleno blanco y contorno negro». Entre tres opciones mostradas, eligió «tarjetas inclinadas».
- **Carrusel de oficios en abanico** (solo en `categorias.html`; ninguna otra página usa carrusel). Reemplaza el carrusel de Bootstrap de E-4:
  - una tarjeta grande al centro (ícono, nombre y «Ver maestros» con forma de botón principal) y, a cada lado, dos más chicas, giradas en 3D e inclinadas en diagonal hacia abajo (en el celular, una por lado, asomada);
  - **dinámico:** avanza solo cada 4 s, con transición de 550 ms; se detiene con el mouse encima o con el foco dentro, queda en pausa al tocarlo con el dedo y tiene botón «Pausar/Reanudar» (WCAG 2.2.2). Con `prefers-reduced-motion` empieza en pausa y sin animación. Con la pestaña oculta no avanza;
  - se cambia con «Anterior»/«Siguiente», con un punto por oficio (en PC), deslizando el dedo, con las flechas del teclado o tocando una tarjeta lateral (que pasa al centro). Da la vuelta al final;
  - solo la tarjeta del centro es enlace enfocable y visible para lectores de pantalla; el cambio a mano se anuncia («Oficio 3 de 9: Gasfitería…»), el automático no, para no interrumpir cada 4 s;
  - código propio (`js/categorias.js`, CSS con transformaciones 3D), sin el JS de Bootstrap: hoy ninguna página carga `bootstrap.bundle.min.js` (queda alojado para cuando se use un componente con JS).
- **Encabezado rojo:** degradado de `--marca-oscura` (`#A50E26`) a `--marca` (`#C8102E`), sin línea inferior; la marca «AlTiro» en blanco (7,8:1 y 5,88:1). Botones del encabezado (hoy, «Menú»): relleno blanco, texto y contorno negros de 2 px; abierto, fondo gris suave con contorno más grueso y `aria-expanded`. El anillo de foco dentro del encabezado es blanco, porque el negro sobre el rojo oscuro queda en 2,7:1 (menos de 3:1). Reemplaza el degradado claro de E-3.3.
