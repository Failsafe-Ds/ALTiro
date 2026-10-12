# Auditoría de calidad del código, segunda ronda (ponytail-audit)

- **Fecha:** 2026-10-11
- **Preparado por:** Claude, con la skill `ponytail-audit` (adaptación AlTiro).
- **Versión revisada:** commit `03bbb8b` (v0.6.3).
- **Alcance:**
  1. el frontend completo (`frontend/`: 30 páginas HTML, 41 archivos JS y `css/base.css`): seguridad, corrección, código de más y accesibilidad solo como falla concreta;
  2. lo que cambió en el backend desde la primera auditoría (`git diff 60ab883..03bbb8b -- backend/`): `comun/texto.py` y sus usos, el precio en la búsqueda (ADR-022 E-2), la descripción del maestro (DA-30, migración `perfil/0005`), la cédula con vencimiento (ADR-017 E-4) y «Otros servicios» (DA-31, `catalogo/0008`, `busqueda/maestros_por_comuna.py`, `cargar_datos_demo`);
  3. lo que la primera auditoría no revisó: `perfil/publicacion.py`, `perfil/fotos.py`, `gestion/indicadores.py`, `expediente/retencion.py`, `scripts/respaldo.sh`, `scripts/restaurar.sh` e `infra/proxy/`.
- **Carga supuesta:** la de la prueba de concepto (CLAUDE.md §3): 10 usuarios simultáneos; 100 maestros, 300 servicios, 1.000 tickets y 5.000 mensajes; teléfono con conexión móvil limitada (RNF-02: 4 Mbps) y señal irregular.
- **Método:** búsquedas dirigidas en todo `frontend/` (`innerHTML`, redirecciones, `localStorage`/`sessionStorage`, `window.*`, CSP, estilos en línea, nombre accesible de cada control, clases CSS sin uso, funciones repetidas) y lectura completa de `api.js`, `dom.js`, `formulario.js`, `territorio.js`, `ingresar.js` y de las partes con borradores, sondeo y enlaces. Tres fallas se confirmaron en el navegador (Chromium de Playwright en un contenedor desechable, contra la pila `altiro-dev`, solo lectura: no se creó ninguna cuenta ni se escribió ningún dato). No se cambió código. No se corrió la suite.
- **Primera auditoría:** `docs/testing/auditoria-backend-ponytail.md`; sus 8 hallazgos están corregidos y no se repiten aquí.

---

**Qué hace este repositorio:** AlTiro conecta hogares con maestros verificados. El frontend son páginas HTML estáticas con JavaScript sin framework, servidas por Nginx con una CSP estricta, y cada página llama a la API en Django. El servidor decide todas las reglas; la pantalla guarda borradores en el teléfono para que no se pierda lo escrito si se corta la señal (RNF-20).

Lo que está bien: no hay ningún `innerHTML` ni `eval`; todo el texto del servidor se agrega como texto (`dom.elemento`, `textContent`). No hay scripts, estilos ni manejadores en línea, y la CSP del proxy (`script-src 'self'`) se cumple. Los enlaces que vienen del servidor pasan por `dom.enlaceInterno` (mismo origen y rutas conocidas). `ingresar.js` solo redirige a una lista cerrada de páginas y valida el UUID del ticket. Los IDs de la URL van siempre con `encodeURIComponent`. La búsqueda descarta las respuestas viejas (`numero !== consulta`). Ninguna regla de negocio vive solo en JS: horarios, 4 horas, precio y estados los decide el servidor. Todos los controles tienen nombre accesible. En el backend, los cambios nuevos usan bien `limpiar_texto`, y los cuatro módulos que faltaban revisar, los scripts de respaldo y el proxy están sanos.

## Debe corregirse

1. **«Cerrar sesión» desde el menú no borra los borradores del teléfono** (`frontend/js/menu.js:137`)
   - **Qué es:** el botón «Cerrar sesión en este dispositivo» del menú, que está en todas las páginas, debería llamar a `formulario.olvidarTodo()`. Esa función borra los borradores `altiro.*`: la dirección del pedido, los datos de registro, la conversación y la evaluación.
   - **Problema:** el código pregunta `if (window.formulario)`, pero `formulario.js` declara `const formulario`, y una `const` global no queda en `window`. Verificado en el navegador: `typeof window.formulario` da `"undefined"` y `typeof formulario` da `"object"`. Por eso, al cerrar sesión desde el menú no se borra nada. En un teléfono compartido, el borrador de la conversación (en `localStorage`) y la dirección escrita en `pedir-trabajo` (en `sessionStorage`, mientras siga abierta la pestaña) quedan para la persona siguiente. Solo «Mi cuenta» (`cuenta.js:396`) borra bien. Incumple ADR-002 E-1 y la minimización de datos (CLAUDE.md §8).
   - **Arreglo:** `formulario.olvidarTodo();` sin el `window.`. Todas las páginas cargan `formulario.js` (revisado). Es una línea.
   - **Si no se corrige:** lo que el cliente escribió (dirección, mensajes al maestro) queda en un teléfono que otra persona usa después, aunque se cerró la sesión.
   - **Estado: corregido.** `menu.js` llama a `formulario.olvidarTodo()` sin `window.`; ningún otro archivo usa `window.formulario`, `window.api`, `window.dom` ni `window.formato`. Prueba: `scripts/qa-pulido/formulario_pegado_y_salir.py` (v0.6.4).

2. **Pegar un correo con un espacio al final no pega nada** (`frontend/js/formulario.js:43-55`)
   - **Qué es:** un manejador global de «pegar» quita los espacios de los extremos del texto pegado (DEF-QA-019) e inserta el resultado con `setRangeText`.
   - **Problema:** `setRangeText` no funciona en `<input type="email">` y lanza un error. Como antes se llamó a `preventDefault()`, el pegado queda cancelado. Verificado en el navegador: pegar `"ana.prueba@example.cl "` en `#correo` de `registro-cliente.html` deja el campo **vacío** y la página registra «The input element's type ('email') does not support selection». Copiar el correo desde WhatsApp o desde un correo suele traer ese espacio. Afecta al registro de cliente (correo obligatorio), a la postulación y a «Mi cuenta» (`cuenta.html:103,176`). Además, cuando el pegado sí funciona, `setRangeText` no respeta `maxlength`: un texto largo pegado con espacios entra completo, y el servidor responde con el error de largo.
   - **Arreglo:** al comienzo del manejador, `if (typeof campo.selectionStart !== "number") return;` deja que el navegador pegue normal (el correo ya se recorta al enviar, en `formulario.valor`). Recortar también a `campo.maxLength` lo pegado. Unas 3 líneas.
   - **Si no se corrige:** quien pega su correo no puede registrarse, no ve ningún error y no entiende por qué (RNF-15).
   - **Estado: corregido.** Si el campo no admite selección (`email`, `number`) pega el navegador y el valor se recorta al salir y al enviar; si `setRangeText` falla, tampoco se cancela el pegado; lo pegado se corta al `maxlength`. Prueba: `formulario_pegado_y_salir.py`.

3. **Si se cambia rápido de región, la lista muestra las comunas de la región anterior** (`frontend/js/territorio.js:44-68`)
   - **Qué es:** al elegir una región, `cargarComunas` pide sus comunas y llena la lista cuando llega la respuesta.
   - **Problema:** no revisa si la región sigue siendo la misma cuando llega la respuesta. Verificado en el navegador, con la respuesta de Arica y Parinacota demorada 2,5 s: se elige Arica y Parinacota y luego Tarapacá; al final la región dice «Tarapacá» y la lista de comunas muestra «Arica, Camarones, General Lagos». Con red móvil lenta (RNF-02) basta con corregir la región antes de que cargue. Afecta al registro de cliente, a «Mi cuenta», a la búsqueda y a «Mi cobertura», donde se puede guardar como comuna base una comuna de otra región (RF-06).
   - **Arreglo:** antes del `await`, guardar `selectComuna.dataset.region = region`; después, `if (selectComuna.dataset.region !== region) return;`. Son 2 líneas, el mismo patrón que ya usa `buscar.js:507-513`.
   - **Si no se corrige:** quedan comunas equivocadas en el perfil del cliente o en la cobertura del maestro, y la búsqueda las usa.
   - **Estado: corregido.** `territorio.js` descarta la respuesta si la región ya cambió (`dataset.region`) y usa `dom.opcion`. El servidor no recibe la región: guarda la comuna enviada, y su región se deriva de ella, así que no hay incoherencia que rechazar. Prueba: `formulario_pegado_y_salir.py` y revisión de `mi-cobertura`.

## Conviene corregir

4. **Los borradores de conversación y evaluación vencidos no se borran, y su código está copiado** (`frontend/js/formulario.js:330-334`; `frontend/js/conversacion.js:56-90`; `frontend/js/evaluar.js:34-66`)
   - **Qué es:** la conversación y la evaluación guardan su borrador en `localStorage`, con una vigencia de 2 h (ADR-002 E-1). `formulario.js` borra lo vencido al cargar cualquier página.
   - **Problema:** esa limpieza solo recorre `sessionStorage`. Un borrador de conversación vencido queda en `localStorage` para siempre, salvo que se vuelva a abrir esa misma conversación o se cierre sesión desde «Mi cuenta». Por ejemplo, el cliente escribe «el timbre no funciona, depto 402», no lo envía, la sesión vence sola a los 30 min y el texto sigue en el teléfono. Además, `conversacion.js` y `evaluar.js` repiten casi igual `guardarDatos`/`recuperar` de `formulario.js`, solo que con otro almacenamiento.
   - **Arreglo:** dar a `formulario.guardarDatos`, `recuperar` y `olvidar` un parámetro de almacenamiento (`sessionStorage` por defecto) y hacer que la limpieza al cargar recorra también las claves `altiro.conversacion.*` y `altiro.evaluar.*` de `localStorage`. Las dos páginas usan esas funciones. Quedan unas 40 líneas menos.
   - **Si no se corrige:** la regla de 2 h de ADR-002 E-1 solo se cumple a medias, en el caso con más datos personales.
   - **Estado: corregido.** `formulario.js` guarda, recupera y vence también en `localStorage` (`guardarTexto`, `recuperarTexto`; parámetro de almacenamiento) y al cargar limpia lo vencido de `altiro.conversacion.*` y `altiro.evaluar.*`; se quitó la copia de `conversacion.js` y `evaluar.js`.

5. **Una petición que se queda colgada deja el botón en «Enviando…» por minutos** (`frontend/js/api.js:64-79` y `:117-150`)
   - **Qué es:** `api.js` hace todas las llamadas con `fetch` y las subidas de fotos con `XMLHttpRequest`.
   - **Problema:** ninguna tiene tiempo límite. Si la señal se cae a mitad de una petición (cambio de antena, ascensor), el navegador puede esperar varios minutos antes de fallar. Mientras tanto, el botón queda desactivado sin «Reintentar». La subida incluso escucha el evento `"timeout"`, pero `xhr.timeout` nunca se fija, así que ese evento no ocurre. Es justo el caso del maestro con conectividad irregular (CLAUDE.md §9; RNF-20).
   - **Arreglo:** en `ejecutar`, `opciones.signal = AbortSignal.timeout(30000)` (Chrome y Firefox actuales lo tienen, RNF-18), que cae en el `catch` existente y da `SIN_CONEXION`. En `subir`, `xhr.timeout = 120000`. Son 2 líneas. El reintento no duplica envíos donde ya hay protección (`clave_envio` en mensajes, transiciones idempotentes del ticket); es el mismo riesgo de hoy con un corte que sí se detecta.
   - **Si no se corrige:** en la demostración con red limitada, una acción puede quedar «pensando» sin salida.
   - **Estado: corregido.** `api.js`: 20 s para JSON (`AbortController`) y 120 s para subir fotos (`xhr.timeout`); al vencer responde estado 0 con «La conexión está muy lenta y no recibimos respuesta a tiempo…», que conserva lo escrito. Prueba: `formulario_pegado_y_salir.py` (corte a los 20,4 s).

6. **`mis-pedidos.js` y `mis-trabajos.js` comparten unas 320 líneas idénticas** (`frontend/js/mis-pedidos.js:19-70, 173-471` y `frontend/js/mis-trabajos.js:21-80, 200-524`)
   - **Qué es:** son las bandejas del cliente y del maestro: avisos, paginación, historial, tarjeta y sesión terminada.
   - **Problema:** son copias con 13 bloques iguales (el mayor, 55 líneas: `lineaAviso` y `cargarAvisos`). Todo cambio se hace dos veces. Así pasó con el filtro de enlaces del hallazgo B-4 (`dom.enlaceInterno`), que tuvo que aplicarse en ambos archivos. Si una copia se olvida, el cliente y el maestro ven avisos distintos.
   - **Arreglo:** un archivo `js/bandeja.js` con lo común (avisos, paginación, `lineaFecha`, `sesionTerminada` con su texto y su `siguiente` como parámetros). Cada página deja solo lo propio: precio, acciones y textos. Quedan unas 250 líneas menos.
   - **Si no se corrige:** la próxima regla de avisos (ADR-024) queda aplicada en una sola bandeja.
   - **Estado: corregido.** Lo común está en `frontend/js/bandeja.js` (`bandeja.crear`); cada página deja su tarjeta, detalle, acciones y textos, sin cambios.

7. **La visibilidad de un maestro se arma por dos caminos distintos** (`backend/perfil/publicacion.py:120-148` `_contexto_de` y `:160-205` `contextos_en_lote`)
   - **Qué es:** la regla única de publicación (ADR-019 E-1) recibe un `Contexto`. La búsqueda lo arma en lote; la ficha pública, «Mis servicios» y `maestro_publicado` lo arman servicio por servicio con otras consultas.
   - **Problema:** hoy los dos dan lo mismo, pero son dos copias que hay que cambiar juntas. Si una regla nueva (por ejemplo, otra licencia) se agrega solo en una, la búsqueda muestra a un maestro cuya ficha dice que no ofrece ese servicio (RF-05, RNF-25). Además, el camino de a uno hace unas 3 consultas por servicio.
   - **Arreglo:** que `_contexto_de` llame a `contextos_en_lote([maestro_id], servicio_ids={servicio.pk})[maestro_id]` (con el `elegible` ya calculado si viene) y borrar su cuerpo. La regla pura no cambia. Quedan unas 25 líneas menos.
   - **Si no se corrige:** la «regla única» deja de serlo en el primer cambio.
   - **Estado: corregido.** `_contexto_de` llama a `contextos_en_lote` (con el `elegible` ya calculado, si viene). Prueba `test_el_camino_de_a_uno_usa_el_mismo_contexto_que_el_lote` en `backend/tests/test_publicacion_lote.py`, junto a la comparación F-12 existente.

8. **Ninguna prueba ejerce el comportamiento de `formulario.js` en el navegador** (`frontend/js/formulario.js`; `scripts/qa-pulido/`)
   - **Qué es:** `formulario.js` concentra el recorte, la contraseña que nunca se recorta, los borradores y su borrado. Solo se revisa con los guiones de QA de Playwright.
   - **Problema:** esos guiones escriben con `fill`, que no dispara el evento de pegar, y no cierran sesión desde el menú. Por eso los hallazgos 1 y 2 pasaron el QA del pulido. Nada falla si mañana se rompe el borrado al cerrar sesión.
   - **Arreglo:** un guion de Playwright con tres casos: pegar `"ana@example.cl "` en un correo (el valor queda recortado), pegar `"  clave  "` en una contraseña (queda igual) y cerrar sesión desde el menú con un borrador guardado (no queda ninguna clave `altiro.*` en ninguno de los dos almacenamientos). Unas 30 líneas.
   - **Si no se corrige:** estas fallas vuelven sin aviso en el próximo cambio de pantalla.
   - **Estado: corregido.** `scripts/qa-pulido/formulario_pegado_y_salir.py`: pegado real en `email` y `text`, `maxlength`, contraseña (también con «Mostrar contraseña»), error que se limpia al corregir, región rápida, tiempo límite y cierre de sesión desde el menú; 27 PASS.

## Mejoras menores

9. **Ayudas copiadas página por página** (`sesionTerminada` en 12 archivos, por ejemplo `frontend/js/agenda.js:142` y `frontend/js/mis-servicios.js:162`; `formatearRut` en `frontend/js/cuenta.js:68`, `frontend/js/expediente.js:81` y `frontend/js/formulario.js:522`; `opcion` en `frontend/js/territorio.js:11`, igual a `dom.opcion`)
   - **Qué es:** cada página arma su propio aviso «Tu sesión terminó» con un enlace a `ingresar.html?aviso=sesion&siguiente=…`, y hay tres copias del formato de RUT.
   - **Problema:** solo cambian el texto y el `siguiente`. Las copias de `formatearRut` ya difieren: la de `cuenta.js` no protege un RUT vacío y la de `expediente.js` sí.
   - **Arreglo:** `dom.sesionTerminada(caja, siguiente, texto)`, exportar `formulario.formatearRut` y usar `dom.opcion` en `territorio.js`. Unas 80 líneas menos.
   - **Si no se corrige:** cada ajuste de este aviso (por ejemplo, el foco o el rol) hay que repetirlo 12 veces.
   - **Estado: corregido.** `dom.sesionTerminada` y `dom.enlaceIngresar` (los usan `expediente.avisarSesionTerminada`, la bandeja, conversación, evaluar, comercial, curatoría, indicadores y moderación); `formulario.formatearRut` única (protege el vacío); `territorio.js` usa `dom.opcion`.

10. **CSS sin uso y reglas que el rediseño ya pisa** (`frontend/css/base.css:414-420`, `:1571-1573`; reglas repetidas en `:351` y `:1940` `.tarjeta`, `:135` y `:1624` `.encabezado`, `:301` y `:1962` `.aviso`, `:1409` y `:1484` `.calificacion-ficha`, `:1755` y `:1952` `.seccion`, y `.opciones-plegable > summary`)
    - **Qué es:** `.enlace-encabezado` y `.calificacion` no se usan en ningún HTML ni JS (revisado, incluidas las clases que se arman con prefijos). Además, el rediseño (ADR-002 E-3) agregó al final bloques nuevos para 6 selectores que ya existían.
    - **Problema:** el primer `.tarjeta` queda pisado en sus 4 propiedades. Quien lo edite no verá ningún cambio.
    - **Arreglo:** borrar las 2 clases sin uso y unir cada par de reglas en la versión nueva. Unas 40 líneas menos.
    - **Si no se corrige:** más peso en cada página (RNF-02) y cambios de estilo que no se ven.
    - **Estado: corregido.** Se borraron `.enlace-encabezado` y `.calificacion` (sin uso, revisado con `grep` en HTML y JS) y se unieron los pares de `.tarjeta`, `.encabezado`, `.aviso`, `.calificacion-ficha`, `.seccion` y `.opciones-plegable > summary`, revisando que ninguna regla intermedia dependiera del orden.

11. **La retención repite la misma advertencia cada 5 minutos** (`backend/expediente/retencion.py`, en `aplicar_retencion`, la rama `if dias is None`)
    - **Qué es:** sin plazo configurado (pendiente V-04/P-30), la tarea avisa en el registro que hay documentos que quedarían sujetos a retención.
    - **Problema:** el planificador corre cada 300 s, así que con un solo expediente rechazado o suspendido son 288 advertencias por día y tipo de documento. Tapan los avisos reales.
    - **Arreglo:** emitir la advertencia solo una vez por día; por ejemplo, solo en la primera vuelta después de medianoche, o con una variable del proceso del planificador. Unas 3 líneas. La advertencia se mantiene (ADR-026 E-9.3).
    - **Si no se corrige:** el registro de operación se llena de ruido mientras V-04 siga abierto.
    - **Estado: corregido.** La advertencia se registra una vez por día y tipo (variable del proceso del planificador). Prueba `test_la_advertencia_sin_plazo_se_registra_una_vez_por_dia` en `backend/tests/test_retencion.py`.

Se dejaron fuera 3 observaciones menores:
- 8 páginas vuelven a pedir `GET /api/cuenta` aunque `menu.js` ya lo pidió (`window.altiroCuenta`); no se reutiliza porque esa promesa no dice si fue un 401.
- `respaldo.sh` cuenta las filas después del `pg_dump`, así que una escritura entre ambos pasos hace diferir los conteos; a las 03:00 es poco probable.
- El contador de «Sobre mí» cuenta un emoji como 2 caracteres y el servidor como 1; la pantalla es más estricta, nunca más permisiva.

**Revisado sin hallazgos:** `comun/texto.py` y sus usos nuevos; precio en la búsqueda (siempre hay precio para un candidato visible, sin consultas extra y fuera del puntaje); `cambiar_descripcion` y `PUT /api/maestros/perfil`; cédula con vencimiento obligatorio solo en cargas nuevas; migración `catalogo/0008` (idempotente y reversible) y `completar_descripciones`; `perfil/fotos.py` (recodificación, escritura atómica y borrado al confirmar); `gestion/indicadores.py` (agregación en la base y supresión mes a mes); `expediente/retencion.py` (bloqueos y bitácora); `scripts/respaldo.sh` y `scripts/restaurar.sh`; `infra/proxy/` (CSP, cabeceras, límites, 413/429/503 en JSON, registro sin parámetros de consulta).

**Veredicto:** el frontend es seguro frente a inyección y redirección, pero falla en la privacidad del teléfono compartido y en la entrada de datos. Lo primero es corregir 1 (una línea), 2 (3 líneas) y 3 (2 líneas); después, 4, 5 y la prueba del 8.

**Lean:** se pueden quitar unas 435 líneas (hallazgos 4, 6, 7, 9 y 10) y ninguna dependencia.

**No revisado:** la lectura línea por línea de `mis-servicios.js`, `mi-postulacion.js`, `curatoria-expediente.js`, `comercial.js`, `agenda.js`, `cobertura.js` e `indicadores.js` (solo se revisaron con las búsquedas de arriba); las páginas de `frontend/errores/`, salvo el uso de CSP; el peso real de cada página con red limitada (ya medido en `docs/testing/rnf-02-medicion.md`); y las pruebas de `backend/tests/` agregadas en el pulido, salvo sus nombres. No se corrió la suite.
