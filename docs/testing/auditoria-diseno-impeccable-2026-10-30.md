# Auditoría de diseño y UX con `impeccable` (critique + audit), 2026-10-30

Solo análisis; no se modificó código ni se crearon PRODUCT.md/DESIGN.md. Versión revisada: v0.6.8 (altiro-dev).

## 0. Método y límites (leer primero)

- Method: DEGRADED single-context. Las dos evaluaciones (A: revisión de diseño, B: detector) corrieron en un solo contexto, sin subagentes aislados, por instrucción del encargo de no lanzar agentes.
- El lanzador `impeccable context` funcionó; avisó que no hay PRODUCT.md (se siguió con el código y MASTER.md como contexto, sin crearlo). El detector `impeccable detect` corrió sobre `frontend/*.html` (30 páginas). No se usaron `live`, `generate` ni `visualize`.
- La extensión de Chrome no estaba conectada, así que no hubo revisión visual en vivo ni a 390 px. Todo lo visual se infiere del HTML, CSS (`base.css`, 2699 líneas) y JS. Lo que dependa de pintura real figura como "por verificar".
- Modo de la superficie: Operate (completar tareas), con inicio de cliente y ficha de maestro más cercanos a Persuade/Read. Se juzga claridad, escaneo, táctil y legibilidad por sobre expresión.
- Se conserva: identidad roja/Fiverr, carrusel de oficios, inicio por rol, sin «Volver», Bootstrap 5.3.8 + CSP sin inline.

## 1. Pantallas revisadas

Las 30 páginas por marcado y detector; en profundidad por código: `index`, `categorias` (carrusel), `buscar`, `perfil-maestro`, `pedir-trabajo`, `ingresar`, `registro-cliente`, `postulacion-maestro`, `cuenta`, `mis-trabajos`, `menu.js`, `categorias.js`, `api.js`, `base.css`. El resto (curatoría, comercial, moderación, indicadores, agenda, cobertura, documentos, conversación, evaluar) solo por detector y estructura.

## 2. Resultado del detector (Assessment B)

| Hallazgo | Cantidad | Veredicto |
|---|---|---|
| `overused-font` (Plus Jakarta Sans) | 27 | Falso positivo: la fuente está fijada por MASTER.md y alojada en el sitio. No actuar. |
| `skipped-heading` | 1 | Real: `comercial.html`, h1 seguido de h3 «Agregar un oficio» (falta h2). |
| `broken-image` (img sin src) | 4 | Falso positivo en su mayoría: `curatoria-expediente`, `mi-perfil`, `mis-documentos`, `perfil-maestro` ponen el `src` por JS. Riesgo real: si la foto falla, hay un recuadro roto (ver M-09). |
| `side-tab` (borde izquierdo 6 px + radio 8 px) | 1 | `mi-postulacion.html`. Coherente con MASTER (mensajes con borde izquierdo de 4 px), solo se señala la diferencia 6 vs 4 px. P3. |

Sin hallazgos de contraste, tamaño de objetivos ni texto bajo 14 px en marcado estático.

## 3. Critique: puntaje de heurísticas (Nielsen), estimado por código

| # | Heurística | Puntaje | Problema principal |
|---|---|---|---|
| 1 | Visibilidad del estado | 3 | Cargando/enviando con `aria-live` consistente (11 usos de «Cargando…»). Falla el resumen de errores que queda viejo (DEF-CHR-04) y la bandeja que no distingue lo nuevo (DEF-CHR-02). |
| 2 | Lenguaje del usuario | 3 | Buen español de oficio («Pide un horario», «Ver maestros»). Quedan términos de sistema: «Expediente», «Curatoría» visibles al maestro, «bloque» donde el cliente diría «horario». |
| 3 | Control y libertad | 2 | Sin «Volver» por diseño (E-3) y marca que cambia de destino según flujo: el cliente depende de recordar la ruta. Cancelar existe en pedidos; faltan salidas en formularios por pasos largos. |
| 4 | Consistencia | 3 | Sistema único y bien tokenizado. Desvíos: bordes de mensaje 6 vs 4 px, menú con `#000` suelto, h1→h3. |
| 5 | Prevención de errores | 3 | `maxlength`, `data-validar`, `inputmode`/`autocomplete` en muchas pantallas. Enter en paso 1 salta al 2 con errores (DEF-CHR-03). |
| 6 | Reconocer en vez de recordar | 3 | Botón «Menú» con texto y cuenta por roles. Hay que recordar en qué flujo se está; la marca no lo dice. |
| 7 | Flexibilidad y eficiencia | 2 | Sin atajos ni "repetir pedido"; para el cliente que repite oficio, cada pedido parte de cero. |
| 8 | Estética y minimalismo | 3 | Aire y jerarquía Fiverr bien aplicados. En `cuenta.html` y `mis-trabajos` se acumulan tarjetas y avisos viejos. |
| 9 | Recuperación de errores | 3 | Mensajes accionables y formulario conservado. Quedan 409 sin salida (DEF-CHR-06) y el texto engañoso de indicadores (DEF-CHR-05). |
| 10 | Ayuda y documentación | 2 | Una sola ayuda real (`ayuda-orden.html`). No hay ayuda contextual en "precio por hora vs por trabajo", documentos ni cobertura, que son lo más difícil para el maestro. |
| **Total** | | **27/40** | **Aceptable-alto (68%)**, base sólida; falta pulido en flujo del maestro y ayuda contextual. |

### Veredicto de especificidad
El producto tiene carácter propio: abanico de oficios, insignia «Verificado», panel «Pide un horario» y horas en 24 h sin AM/PM no son intercambiables con otro producto. La paleta roja con Plus Jakarta Sans es reconocible; el riesgo es que las pantallas de maestro y administración (tarjetas y avisos apilados) se vean genéricas frente a la del cliente.

### Qué funciona bien
1. Tokens y contrastes calculados (MASTER) y `--bs-*` alineados: el sistema es coherente y los contrastes documentados superan AA.
2. Formularios: etiqueta visible, `aria-describedby` hacia el error, `autocomplete`, "Mostrar contraseña", mensajes con ícono y texto, `role="alert"`/`status`.
3. Móvil: meta viewport, objetivos de 44 px, `min-width:0` anti desborde, carrusel con puntos de 32-44 px como alternativa al gesto, `prefers-reduced-motion` respetado por el carrusel.

### Personas (rojos específicos)
- **Maestro con baja alfabetización digital (proyecto)**: no puede aceptar/rechazar desde la pantalla (DEF-CHR-01); primera pantalla de «Mis trabajos» ocupada por avisos antiguos; textos largos de ayuda sin apoyo de ícono ni audio; "monto por hora vs por trabajo" sin explicación inline.
- **Casey (móvil, conexión irregular)**: la marca no indica el flujo; el inicio carga 232 KB de CSS Bootstrap completo + 27 KB de fuente antes de pintar; sin indicio de "borrador guardado" visible tras interrupción.
- **Sam (teclado/lector)**: sin enlace «Saltar al contenido»; carrusel sin pausa (WCAG 2.2.2); `alt=""` en la foto del maestro cuyo nombre sí está al lado (aceptable) pero la foto principal en el perfil público no describe nada; reduced-motion global con `!important` borra transiciones útiles de estado.

## 4. Audit: puntaje por dimensión

| # | Dimensión | Puntaje | Hallazgo clave |
|---|---|---|---|
| 1 | Accesibilidad | 3 | Sin skip link; carrusel sin pausa/stop (2.2.2); reduced-motion global agresivo; h1→h3 en comercial. |
| 2 | Rendimiento | 2 | Bootstrap CSS completo (232 KB sin minificar a medida) en 30 páginas más ~20 scripts `defer` separados por página; sin `preload` de la fuente. |
| 3 | Tema | 3 | Tokens bien usados; `#000` sueltos en el menú (líneas ~1714-1734 de `base.css`). Sin modo oscuro (no es requisito). |
| 4 | Responsive | 3 | Buen mobile-first; puntos del carrusel bajan a 32 px; vista a 390 px sin verificar visualmente. |
| 5 | Integridad de implementación | 3 | Sistema coherente; detector sin hallazgos serios. |
| **Total** | | **14/20** | **Bueno** (límite bajo): corregir rendimiento y 3 puntos de a11y. |

## 5. Hallazgos y mejoras

Escala: esfuerzo S/M/L; prioridad alta/media/baja. Todas compatibles con Bootstrap + CSP (sin estilos ni scripts en línea) + MASTER.md.

### Alta

**M-01. Carrusel de oficios sin pausa (WCAG 2.2.2) y sin control en táctil**
- Archivo: `frontend/categorias.html`, `js/categorias.js` (líneas ~81-140), `css/base.css` (~2057).
- Problema: avanza solo cada 4 s; solo se detiene con mouse encima o foco dentro. En teléfono no hay hover, así que el movimiento no se puede parar y pasa los 5 s. Con `prefers-reduced-motion` parte pausado, pero no hay botón.
- Por qué importa: el maestro/cliente con poca experiencia pierde la tarjeta que iba a tocar; para lectores y baja visión es una falla AA.
- Propuesta: agregar un botón «Pausar movimiento» / «Reanudar» (texto visible, `aria-pressed`) junto a los puntos, hecho con `.boton-secundario`; que el primer toque o deslizar sobre el abanico pause definitivamente (`pausadoPorPersona = true`) hasta pulsar «Reanudar»; detener tras un ciclo completo. Mantener el carrusel como está.
- Esfuerzo S. Criterio: WCAG 2.2.2, RNF de accesibilidad (RNF-16 y afines).

**M-02. «Mis trabajos»: pedido nuevo enterrado y acciones sin respuesta (DEF-CHR-01 y 02 en conjunto)**
- Archivo: `mis-trabajos.html`, `js/mis-trabajos.js` (~255), `css/base.css`.
- Problema: además de los defectos conocidos, la jerarquía es plana: avisos, pestañas y pedidos pesan igual.
- Por qué importa: es la pantalla de trabajo del maestro; si no ve y no puede resolver el pedido pendiente, la plataforma no cumple su flujo principal.
- Propuesta: tras corregir DEF-CHR-01, mostrar primero el pedido pendiente (tarjeta con comuna, fecha-hora, "Vence en …", botones Aceptar y Rechazar de 48 px siempre visibles, en la parte baja en móvil), pestañas «Nuevos / Aceptados / Historial» arriba, y avisos viejos colapsados en «Avisos anteriores (6)» (`<details>` de Bootstrap, sin JS).
- Esfuerzo M. Prioridad alta. Criterio: RNF-14 (usabilidad móvil), flujo ADR-023.

**M-03. Ayuda contextual para el maestro (precio por hora/trabajo, documentos con y sin vencimiento, cobertura)**
- Archivo: `mis-servicios.html`, `mis-documentos.html`, `mi-cobertura.html`.
- Problema: solo existe una página de ayuda (`ayuda-orden.html`). Heurística 10 en 2/4.
- Por qué importa: la baja alfabetización digital es el eje del proyecto; un campo con jerga ("modalidad", "vencimiento") provoca errores y abandono.
- Propuesta: una línea `.ayuda` bajo cada campo con ejemplo ("Por hora: $8.000 cada hora. Por trabajo: un precio fijo, como $40.000"), y un `<details>` «¿Qué es esto?» de Bootstrap. Textos de 1-2 frases en lenguaje de oficio.
- Esfuerzo M. Prioridad alta. Criterio: CLAUDE.md §9, RNF-15.

**M-04. «Saltar al contenido» y reduced-motion más fino**
- Archivo: todas las páginas (`<header class="encabezado">`), `css/base.css` (~241).
- Problema: sin skip link; el bloque `*{transition:none!important; animation:none!important}` elimina también transiciones útiles (aparición de mensajes, cambio de pestaña) y pisa cualquier estilo posterior.
- Propuesta: `<a class="saltar" href="#main">Saltar al contenido</a>` visible al enfocar (clase en `base.css`, `main id="main"`); en reduced-motion, dejar solo cambio de opacidad/color instantáneo (sin `!important` global, solo `scroll-behavior:auto` y animaciones de movimiento).
- Esfuerzo S. Prioridad alta/media. Criterio: WCAG 2.4.1, 2.3.3.

### Media

**M-05. Orientación de flujo: la marca cambia de destino sin avisarlo**
- Archivo: `js/menu.js` (INICIO_FLUJO).
- Problema: la marca lleva a `categorias.html` o `mis-trabajos.html` según el último flujo; el usuario no lo sabe ni ve dónde está.
- Propuesta: debajo del encabezado, una franja corta con el título de sección que ya existe en el h1; en el menú, marcar con `aria-current="page"` y negrita la opción activa, y agrupar «Para pedir trabajos» / «Mi trabajo como maestro». Sin añadir «Volver».
- Esfuerzo S. Criterio: heurística 6, RNF-14.

**M-06. Formularios por pasos: Enter y resumen de errores (DEF-CHR-03/04) con indicador de progreso**
- Archivo: `registro-cliente.html`, `postulacion-maestro.html`, `js/formulario.js`.
- Propuesta: texto «Paso 1 de 3» con barra de progreso Bootstrap (`.progress` con `role="progressbar"`), Enter solo avanza si el paso es válido sin mostrar errores del siguiente; limpiar el resumen al corregir el último campo afectado.
- Esfuerzo M. Criterio: CLAUDE.md §9 puntos 4 y 5.

**M-07. Pesos de carga en red móvil**
- Archivo: `frontend/vendor/bootstrap-5.3.8/bootstrap.min.css` (232 KB), `*.html` (6-8 `<script defer>` por página).
- Problema: se carga todo Bootstrap aunque se use grilla/utilidades y poco más; sin `preload` de la fuente.
- Propuesta: medir con la red limitada del RNF; si pasa el umbral, agregar `<link rel="preload" as="font" type="font/woff2" crossorigin href="fuentes/…woff2">` (compatible con CSP) y evaluar un CSS de Bootstrap reducido (solo módulos usados) o confirmar el gzip del proxy. Agrupar `api/formulario/menu/pie/version` en un solo archivo por página si hay presupuesto.
- Esfuerzo M. Criterio: RNF de carga en red móvil.

**M-08. Cliente que repite: eficiencia (heurística 7)**
- Archivo: `mis-pedidos.html`, `js/mis-pedidos.js`.
- Propuesta: en pedidos finalizados, botón «Pedir de nuevo a este maestro» que lleva a `pedir-trabajo.html` con el maestro y el servicio ya elegidos (por parámetros de ref, no datos personales). Hay que confirmar con backend que existe el contrato.
- Esfuerzo M. Prioridad media-baja.

**M-09. Estado de imagen fallida (foto del maestro)**
- Archivo: `perfil-maestro.html` (`#foto-maestro`), `mi-perfil.html`, `mis-documentos.html`, `curatoria-expediente.html`.
- Problema: `<img>` sin `src` hasta que carga el JS; en conexión lenta o foto fallida queda un recuadro roto, y `alt=""` la hace invisible a lector de pantalla.
- Propuesta: `<img hidden>` hasta `onload`, marcador con iniciales del maestro si falla, `alt` útil donde la foto es contenido («Foto de María») y reservar espacio (ya hay width/height, bien).
- Esfuerzo S.

**M-10. Errores y textos puntuales (DEF-CHR-05/06 + estos)**
- `indicadores.js`: mensaje de fechas invertidas; el 409 «Ya evaluaste este trabajo» sin siguiente paso.
- Propuesta de texto: «“Hasta” debe ser igual o posterior a “Desde”. Cambia la fecha de término.» y «Ya evaluaste este trabajo. Puedes ver tu evaluación en esta pantalla.»
- Esfuerzo S.

### Baja

**M-11. h1 → h3 en `comercial.html`.** Cambiar «Agregar un oficio» a h2 (o añadir h2 de sección). S.
**M-12. Hex sueltos `#000` en el menú** (`base.css` ~1714-1734): usar `var(--foco)` o `var(--texto)`. S.
**M-13. Borde de aviso de 6 px en `mi-postulacion`** vs 4 px de MASTER; unificar. S.
**M-14. Texto mínimo:** hay reglas con `font-size: 0.85rem` (línea ~1632); MASTER fija mínimo 0.875 rem. S.
**M-15. Puntos del carrusel en móvil a 32 px:** pasa WCAG 2.5.8 (24 px) pero queda bajo los 44 px de RNF-14; ampliar el área táctil con padding sin agrandar el punto visible (2 filas de 5 puntos o área de 44 px con superposición controlada). M.

## 6. Patrones sistémicos
- El sistema visual es sólido en cliente y formularios; la deuda está en jerarquía de las pantallas del maestro (avisos y tarjetas apilados) y en ayuda contextual.
- Accesibilidad por defecto buena (labels, aria-describedby, roles), pero faltan elementos globales (skip link, pausa de movimiento).
- Rendimiento no medido en este análisis: hay que verificarlo contra el umbral de red móvil.

## 7. Por verificar visualmente (no cubierto)
Vista a 390 px de todas las pantallas; solapamiento del abanico en móvil; foco visible negro sobre el encabezado rojo; legibilidad real del panel «Pide un horario» en una columna; zoom 200% y texto aumentado; táctil real en el carrusel (gesto de deslizar sin `touch-action` revisado).

## 8. Top 10 de mayor impacto
1. M-02 Pantalla «Mis trabajos» (corregir DEF-CHR-01 y jerarquizar el pedido pendiente con Aceptar/Rechazar grandes). Alta, M.
2. M-01 Pausa y control táctil del carrusel (WCAG 2.2.2). Alta, S.
3. M-03 Ayuda contextual en precio, documentos y cobertura del maestro. Alta, M.
4. M-04 Skip link y reduced-motion sin `!important` global. Alta, S.
5. M-06 Formularios por pasos: progreso visible, Enter seguro, resumen que se actualiza. Media, M.
6. M-07 Peso de carga: preload de fuente, medir/reducir CSS de Bootstrap. Media, M.
7. M-05 Orientación de flujo en el encabezado y menú agrupado. Media, S.
8. M-09 Foto del maestro: estado de carga/fallo y `alt` útil. Media, S.
9. M-10 Textos de error accionables (indicadores, evaluación duplicada). Media, S.
10. M-15 Objetivos táctiles de los puntos del carrusel a 44 px. Baja-media, M.

(Siguientes comandos sugeridos de `impeccable`: `harden` para 1 y 5, `clarify` para 3 y 9, `adapt` para 10, `optimize` para 6, `polish` al final.)
