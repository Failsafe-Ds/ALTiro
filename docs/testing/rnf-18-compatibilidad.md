# Evidencia RNF-18 — Compatibilidad de navegadores y reflujo en celulares angostos

- **Requisito:** RNF-18 (NTI-11). Umbral literal: "Las dos últimas versiones de Chrome y Firefox, y Chrome en Android, sin que haya que desplazar la pantalla de lado en celulares angostos".
- **Método acordado:** D-15 de `docs/decisions/sprint-3-propuesta-arquitectura.md`: "celular angosto" = 320 px CSS; Playwright con Chromium y Firefox en dos versiones; un pase manual en Chrome y Firefox de escritorio y en Chrome de Android.
- **Alcance:** pantallas existentes de S1 y S2 (verificación retroactiva del Sprint 3). Las pantallas nuevas del S3 deberán pasar por el mismo script cuando existan.
- **Fecha:** 2026-09-29. Base: `main`, commit `5bea2ad`, sin cambios en `frontend/`.
- **Preparado por:** agente `frontend`.

## 1. Método

### 1.1 Qué se comprueba en cada estado

Para cada página y estado, a **320 px** (reflujo de WCAG 2.2, criterio 1.4.10) y a **390 px** CSS de ancho:

1. **Sin desplazamiento lateral:** `document.documentElement.scrollWidth <= window.innerWidth` y, además, `scrollWidth <=` el ancho configurado. Así no se engaña con un viewport que el navegador móvil ensancha solo.
2. **Ningún elemento se sale de la pantalla:** se recorre cada elemento visible de `body` y se exige que `getBoundingClientRect()` quede entre 0 y `document.documentElement.clientWidth`.
3. **Objetivos táctiles de al menos 44 × 44 px (RNF-14):** botones, enlaces, campos, listas, áreas de texto y etiquetas de casillas (`label.casilla`, `label.casilla-grande`). Los enlaces dentro de una frase (`display: inline`) se informan aparte, por la excepción "en línea" de WCAG 2.5.8. Es el mismo criterio del cierre del S1 (`cierre-sprint-1.md`, fila RNF-14).
4. **Sin errores de JavaScript:** ningún `pageerror` (excepción no capturada). En la consola solo se aceptan los avisos del navegador por respuestas 4xx esperadas (sesión, validación, acceso denegado), el 502 de la página 50x simulada y el corte de red provocado a propósito.

Además hay **chequeos de compatibilidad** de las funciones del navegador que usan las pantallas y que difieren entre motores:

| Chequeo | Qué usa el frontend |
|---|---|
| `:has()` marca la casilla elegida con borde de 3 px | `.casilla-grande:has(input:checked)` en `base.css` |
| Texto alternativo en `content` (`"► " / ""`) | `.nota-licencia::before`, `.cuenta-pendiente::before` |
| `input type="date"` guarda el valor ISO | Fechas de emisión y vencimiento |
| Vista previa de la foto comprimida | `createImageBitmap`, `canvas.toBlob` en `foto.js` |
| Fechas en español con `Intl` ("Vence el 1 de mayo de 2031") | `expediente.js` |
| `<dialog>` abierto como modal (`showModal`, `:modal`) | Visor de fotos (`visor.js`) |
| La foto del visor cabe en el ancho | `.visor img { max-width: 100% }` |
| **Control negativo** | Se inserta un bloque 80 px más ancho que la pantalla y un botón de 30 px: la medición debe detectarlos (y los detecta). Luego se quitan. Así se prueba que un "0 fallas" no es un falso negativo del script |

### 1.2 Entorno

- Stack local por Docker Compose (`proxy`, `app`, `planificador`, `db`), en `https://localhost`.
- Navegadores: imágenes oficiales `mcr.microsoft.com/playwright/python`, en la red `altiro_frontal`. Dentro del contenedor, el script reenvía `127.0.0.1:443` a `proxy:443`. Así los dos motores usan `https://localhost`, el nombre del certificado y de `ALLOWED_HOSTS`, sin reglas propias de un motor.
- Chromium: contexto móvil (`is_mobile=True`, `has_touch=True`), con la meta `viewport` activa, igual que Chrome en Android.
- Firefox: `has_touch=True`, ventana del ancho indicado. Playwright no admite `is_mobile` en Firefox, así que se prueba Firefox de escritorio con una ventana angosta. Es lo que pide RNF-18: Firefox se exige en escritorio y el móvil exigido es Chrome en Android.
- Alto de la ventana: 800 px. Idioma: `es-CL`.
- Datos ficticios: RUT y teléfonos aleatorios, correos `@example.com`, fotos sintéticas rotuladas "MUESTRA". La cuenta de curatoría la crea `cur_prep.sh`, con una contraseña aleatoria en un archivo `0600` que se borró al terminar.
- Script: `rnf18.py <chromium|firefox> <versión de Playwright>`, lanzado con `run18.sh`. Está en el scratchpad de la sesión, igual que `axe_s2.py` en RNF-16; no está en el repositorio. Cada corrida deja `rnf18_<motor>_<versión>.json` con todas las mediciones.

### 1.3 Versiones exactas

Se usaron dos pares de imágenes consecutivas:

- **1.54 y 1.55:** son las versiones de los motores que son consecutivas entre sí (Chromium 139 y 140, Firefox 140 y 141).
- **1.62 y 1.63:** son las más recientes publicadas al 2026-09-29, lo más cercano a las "dos últimas versiones" vigentes.

| Imagen | Digest | Chromium | Firefox |
|---|---|---|---|
| `v1.54.0-noble` | `sha256:9e85bdc9c6980dc230c17f3548acb8d2d73b2cb2d5f6e34e706e18464559ef63` | 139.0.7258.5 | 140.0.2 |
| `v1.55.0-noble` | `sha256:640d578aae63cfb632461d1b0aecb01414e4e020864ac3dd45a868dc0eff3078` | 140.0.7339.16 | 141.0 |
| `v1.62.0-noble` | `sha256:aa81288e738725378becba5b3e06cb0f3a7f012a610e87e8d767a090ea3f740d` | 151.0.7922.34 | 153.0 |
| `v1.63.0-noble` | `sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0` | 153.0.8010.12 | 155.0 |

Las versiones las informa el propio navegador (`browser.version`). En el par 1.62–1.63 los motores no son versiones mayores consecutivas: Playwright se saltó Chromium 152 y Firefox 154.

> **Importante.** El Chromium de Playwright **no es Google Chrome de marca**. Es una compilación de Chromium, a veces previa a la publicación, sin los componentes propietarios de Chrome. El Firefox de Playwright es una compilación parchada para automatización, no el Firefox que distribuye Mozilla. Tampoco reemplazan a Chrome en un Android real: allí influyen el teclado en pantalla, la barra de direcciones, el tamaño de letra del sistema y el selector de fechas nativo. Por eso el pase manual del §5 sigue siendo obligatorio para dar RNF-18 por cumplido.

## 2. Páginas y estados recorridos

Son 53 estados por ancho: 106 mediciones por corrida y 848 en total (4 imágenes × 2 motores).

| Página | Estados |
|---|---|
| Inicio (`index.html`) | Sin sesión; con sesión |
| Páginas de error | 404 real del proxy (dirección que no existe). 50x: el contenido real de `errores/50x.html` con estado 502, entregado por el script porque el proxy solo la muestra ante un error (`internal`) |
| Ingresar | Vacía; errores de campo; credenciales incorrectas; aviso de cuenta creada; derivada desde "Mi cuenta" sin sesión |
| Registro de cliente (3 pasos) | Paso 1; paso 1 con errores; paso 2 (región y comuna cargadas); paso 3; paso 3 con error de contraseña; con sesión iniciada (derivación a "Mi cuenta") |
| Postulación de maestro (2 pasos) | Paso 1; paso 1 con errores; paso 2 |
| Mi cuenta | Solo cliente; solo maestro; cliente y maestro (perfil de maestro agregado desde la cuenta); agregar maestro con RUT inválido; curatoría. Correo del cliente de más de 60 caracteres, para probar el corte de textos largos |
| Mi postulación (por pasos) | Oficios; oficios con error; oficios marcados; cédula vacía; cédula con errores; cédula con dos fotos y fecha; **sin conexión** (corte de red real); antecedentes; licencia con error del servidor junto al campo; resumen en revisión; resumen observado con motivo y aviso de vencimiento (respuesta simulada con la forma del contrato); acceso denegado a un cliente |
| Mis documentos | Lista; visor con la cara frontal; visor con la parte de atrás; observado y por vencer (simulado); sesión terminada |
| Curatoría: cola | Acceso denegado a cliente y a maestro; cola en revisión con avisos; filtro "rechazados"; página con el expediente de la corrida; sesión terminada |
| Curatoría: detalle | Detalle completo con historial; visor; observar documento sin motivo (error junto al campo); documento observado (resultado junto al documento); 409 al aprobar sin requisitos; confirmación de rechazo; expediente inexistente |

## 3. Resultados

| Imagen | Motor y versión | 320 px | 390 px | Chequeos de compatibilidad | Errores de JS no capturados | Errores de consola inesperados |
|---|---|---|---|---|---|---|
| 1.54.0 | Chromium 139.0.7258.5 | 53/53 **PASS** | 53/53 **PASS** | 16/16 | 0 | 0 |
| 1.54.0 | Firefox 140.0.2 | 53/53 **PASS** | 53/53 **PASS** | 16/16 | 0 | 0 |
| 1.55.0 | Chromium 140.0.7339.16 | 53/53 **PASS** | 53/53 **PASS** | 16/16 | 0 | 0 |
| 1.55.0 | Firefox 141.0 | 53/53 **PASS** | 53/53 **PASS** | 16/16 | 0 | 0 |
| 1.62.0 | Chromium 151.0.7922.34 | 53/53 **PASS** | 53/53 **PASS** | 16/16 | 0 | 0 |
| 1.62.0 | Firefox 153.0 | 53/53 **PASS** | 53/53 **PASS** | 16/16 | 0 | 0 |
| 1.63.0 | Chromium 153.0.8010.12 | 53/53 **PASS** | 53/53 **PASS** | 16/16 | 0 | 0 |
| 1.63.0 | Firefox 155.0 | 53/53 **PASS** | 53/53 **PASS** | 16/16 | 0 | 0 |

En todas las mediciones `scrollWidth` fue igual al ancho (320 o 390) y `clientWidth` igual a `innerWidth`. Ningún elemento se salió de la pantalla. El control negativo detectó el desborde y el botón chico en todas las corridas.

**Por debajo de 44 px, solo los enlaces dentro de una frase** (excepción "en línea", sin cambios desde el S1):

- "Ingresa aquí": 91 × 21 px en Chromium y 91 × 23 px en Firefox (registro de cliente);
- "Ingresa con tu RUT": 141 × 21 px y 141 × 23 px (postulación de maestro).

RNF-14 exige 44 px en "botones"; estos son enlaces de texto, igual que en el cierre del S1. Si el equipo decide aplicar el umbral también a esos enlaces, es un ajuste de CSS que queda como decisión pendiente del representante, no como falla de RNF-18.

**Consola:** en Chromium aparecen los avisos del navegador "Failed to load resource" para respuestas 401, 400 y 403 esperadas (sesión consultada sin iniciar, validaciones, acceso denegado), más el 502 de la página 50x simulada. Firefox no registra esos avisos de red en la consola. No hubo ninguna excepción de JavaScript en ningún motor.

## 4. Correcciones hechas

**Ninguna.** No apareció ningún desplazamiento lateral ni ninguna incompatibilidad en Firefox. Por eso `frontend/` no se modificó. Lo que ya estaba en `base.css` explica el resultado:

- `box-sizing: border-box` global, y campos y botones con `width: 100%`;
- `min-width: 0` en `fieldset` (Firefox y Chromium le dan por defecto `min-width: min-content`, que puede ensanchar un formulario);
- `overflow-wrap: anywhere` en `dd`, motivos, citas e historial;
- columnas de curatoría con `minmax(0, …)` y solo desde 60 rem;
- visor con `width: calc(100% - 2rem)` e imagen con `max-width: 100%`.

Riesgo que queda: `content: "…" / ""` necesita Firefox 128 o posterior, y las versiones probadas ya lo cumplen. En un Firefox más antiguo se aplica la primera declaración y el lector de pantalla podría leer "►" (ya anotado en `rnf-16-contrastes.md` §4).

## 5. Pendiente manual (obligatorio para cerrar RNF-18)

La verificación automática cubre los motores, no los navegadores de marca ni un teléfono real. Falta:

| Navegador | Versiones | Dispositivo | Estado |
|---|---|---|---|
| Google Chrome (escritorio) | Las dos últimas estables a la fecha de la prueba (ver `chrome://version`) | Notebook del equipo | **Pendiente** |
| Mozilla Firefox (escritorio) | Las dos últimas estables (versión actual y la anterior, o la ESR vigente si el equipo lo decide) | Notebook del equipo | **Pendiente** |
| Chrome para Android | Estable vigente | Teléfono Android real, idealmente de gama baja y pantalla angosta (360 px CSS o menos) | **Pendiente** |

Para tener dos versiones de un navegador de escritorio en el mismo equipo se puede usar la versión estable y la anterior en su versión portátil, o dos equipos. Anotar la versión exacta de cada una.

### 5.1 Lista de verificación manual

Para cada navegador y versión, con datos ficticios, anotar **OK / Falla + captura** en cada punto.

**Preparación**
- [ ] Anotar el navegador, la versión exacta, el sistema operativo y el dispositivo.
- [ ] En escritorio, abrir las herramientas de desarrollo y el modo de diseño adaptable a **320 px** de ancho, y repetir a 390 px. En Firefox: `Ctrl+Mayús+M`.
- [ ] En Android: dejar el tamaño de letra del sistema por defecto y repetir con letra "grande". Aceptar la advertencia del certificado de demostración (ADR-008).

**En cada página: no debe hacer falta desplazar la pantalla de lado**
- [ ] Inicio sin sesión y con sesión.
- [ ] Ingresar: vacía, con errores y con credenciales incorrectas.
- [ ] Registro de cliente: los 3 pasos, con errores en el paso 1, elegir región y comuna en el selector nativo, "Mostrar contraseña".
- [ ] Postulación de maestro: los 2 pasos, con errores.
- [ ] Mi cuenta: solo cliente, solo maestro, ambos perfiles y curatoría.
- [ ] Mi postulación: oficios (marcar y desmarcar; la casilla elegida debe verse con borde grueso), cédula con **"Tomar foto"** (en Android debe abrir la cámara trasera) y **"Elegir de la galería"**, fechas con el **selector de fecha nativo**, resumen.
- [ ] Mis documentos: lista y visor (abrir, ver la otra cara, cerrar con el botón y con "Atrás" o `Esc`).
- [ ] Curatoría (en escritorio y a 390 px): cola, filtros, paginación, detalle, visor, observar, confirmación de rechazo.
- [ ] Página 404 (cualquier dirección que no exista).

**Teclado móvil (Android)**
- [ ] El teclado que aparece corresponde al campo: numérico en teléfono y `@` en correo.
- [ ] Al abrir el teclado, el campo activo y su mensaje de error siguen visibles, sin desplazamiento lateral.
- [ ] Los botones principales se pueden tocar con el pulgar sin tocar otro por error.

**Conectividad**
- [ ] Con el modo avión a mitad del envío de un documento, aparece "No se pudo enviar…", el botón dice "Reintentar" y la foto y las fechas se conservan.

**Consola (escritorio)**
- [ ] Sin errores de JavaScript en rojo, salvo los avisos de red 4xx de sesión o validación.

**Registro del resultado**
- [ ] Agregar a este documento una tabla por navegador y versión con el resultado y las capturas a 320 px de al menos: registro paso 2, mi-postulación con cédula y fechas, visor y detalle de curatoría.

## 6. Limitaciones

- No se probó Safari ni Samsung Internet: RNF-18 no los exige.
- Firefox se probó sin emulación móvil (Playwright no la admite en Firefox). El umbral solo exige Firefox en escritorio.
- La medición cuenta como "fuera de la pantalla" cualquier elemento visible que exceda el ancho. Hoy no hay contenedores con desplazamiento interno. Si se agregan (por ejemplo, una tabla con desplazamiento propio), el script los informará y habrá que revisarlos a mano.
- Solo se simularon la página 50x (con su contenido real) y dos estados del expediente del maestro ("observado" con aviso de vencimiento), con la forma del contrato vigente de `GET /api/maestros/expediente`. Todo lo demás se recorrió contra la API real.

## 7. Pantallas nuevas del Sprint 3: catálogo comercial y «Mis servicios» (2026-09-29)

- **Base:** `main`, commit `98cadce`, más los cambios del frontend de esta tarea (sin commit): `comercial.html`, `mis-servicios.html`, `js/comercial.js`, `js/mis-servicios.js`, `js/formato.js`, el método `api.modificar` (PATCH) en `js/api.js`, accesos en `cuenta.html` y `cuenta.js`, destinos `servicios` y `comercial` en `ingresar.js`, y estilos al final de `base.css`.
- **Script:** `s3_ui.py <motor> <versión>` (scratchpad de la sesión, igual que `rnf18.py`, con la misma función de medición copiada en `s3_medir.js`). La cuenta comercial ficticia la crea `com_prep.sh` con `crear_usuario_administrativo` y una contraseña aleatoria pasada por entrada estándar (archivo `0600`). El maestro ficticio se crea en cada corrida con RUT aleatorio.
- **Anchos:** comercial a **1280 px** (escritorio, sin emulación móvil) y **320 px** (móvil); maestro a **390 y 320 px** (móvil). Mismos criterios del §1.1: sin desplazamiento lateral, ningún elemento fuera de la pantalla, objetivos de 44 × 44 px o más y sin errores de JavaScript.

### 7.1 Estados recorridos (24 por motor y por par de anchos; 48 mediciones por motor)

| Página | Estados |
|---|---|
| `comercial.html` | Lista del catálogo; crear oficio con errores (nombre y «¿Necesita licencia de la SEC?» obligatorios); oficio creado; crear servicio sin formas de cobro; editar servicio sin motivo; conflicto 409 real (otra persona cambió el servicio por la API con la versión vigente); editar un oficio regulado (el dato se muestra sin control para cambiarlo); dar de baja sin motivo; sesión terminada; acceso denegado a un maestro |
| `mis-servicios.html` | Sin oficios declarados; sin servicios, con lo que falta para que lo vean los clientes; agregar paso 1 sin elegir; paso 2 con precios de referencia; CA-12.1 sin monto (error del servidor junto al campo); CA-12.1 sin forma de cobro; lista con motivos (licencia de Gas y pendientes); cambiar precio sin monto; confirmación para quitar; progreso recuperado tras volver a cargar; sesión terminada; acceso denegado a la cuenta comercial |
| `cuenta.html` | Cuenta comercial (acceso «Catálogo (comercial)»); maestro (acceso «Mis servicios») |

### 7.2 Resultados (Playwright 1.63.0)

| Motor y versión | Estados | Verificaciones funcionales | Errores de JS | Consola inesperada |
|---|---|---|---|---|
| Chromium 153.0.8010.12 | 48/48 **PASS** | 0 fallidas | 0 | 0 (30 avisos de red 4xx esperados) |
| Firefox 155.0 | 48/48 **PASS** | 0 fallidas | 0 | 0 |

Verificaciones funcionales incluidas en la corrida: CA-20.1 (el servicio creado aparece en `GET /api/catalogo` visto por un visitante), CA-20.2 (el visitante ve el precio nuevo tras el cambio y tras el 409 con nuevo guardado), 409 que conserva lo escrito y «Volver a cargar» que muestra el cambio de la otra persona, regulado sin control al editar, baja con motivo obligatorio (el oficio sale del catálogo público), CA-12.1 (monto y forma de cobro, en la interfaz y por la API), CA-12.2 (motivo "licencia de Gas" visible), quitar con confirmación en la página, montos con formato `es-CL` ("$85.000"), accesos por rol en «Mi cuenta» y enlaces `siguiente=comercial` y `siguiente=servicios` tras sesión terminada.

**Regresión (Chromium 1.63.0):** `s2_maestro.py`, `flujo_s2.py`, `cur_ui.py`, `aviso_ui.py` (tras `aviso_prep.py` y una corrida de `planificador --una-vez`) y `rnf18.py` (106/106 estados, 16/16 chequeos): sin fallas.

**Datos que dejan las corridas:** cada corrida comercial crea un oficio "Oficio Prueba S3 …" con un servicio y al final lo da de baja (queda inactivo y fuera del catálogo público, sin borrado físico por ADR-018). Cada corrida del maestro crea un maestro ficticio en revisión.

El pase manual del §5 también debe incluir estas dos pantallas (comercial en notebook y a 320 px; «Mis servicios» en Chrome de Android).

## 8. Pantallas nuevas del Sprint 3: cobertura, agenda, mi perfil y perfil público (2026-09-29)

- **Base:** `main`, commit `e5ce0c4`, más los cambios del frontend de esta tarea (sin commit):
  - páginas nuevas: `mi-cobertura.html` + `js/cobertura.js`, `mi-agenda.html` + `js/agenda.js`, `mi-perfil.html` + `js/mi-perfil.js`, `perfil-maestro.html` + `js/perfil-publico.js`;
  - `api.reemplazar` (PUT) en `js/api.js`;
  - opciones `camara` y `textoLista` en `js/foto.js` (compatibles con el uso anterior);
  - accesos en `cuenta.html`, botones de pendientes en `js/mis-servicios.js` y destinos `perfil`, `cobertura` y `agenda` en `js/ingresar.js`;
  - estilos al final de `base.css`.
- **Script:** `s3_perfil.py <motor> <versión>` (scratchpad de la sesión, con la misma medición `s3_medir.js`). La cuenta de curatoría ficticia la crea `perfil_prep.sh`, con una contraseña aleatoria pasada por entrada estándar y guardada en un archivo `0600` que se borró al terminar. En cada ancho se crea un maestro ficticio nuevo, con RUT aleatorio y fotos sintéticas "MUESTRA".
- **Recorrido "publicable" completo en cada ancho:**
  1. El maestro postula, declara Gas y Pintura y sube la cédula, los antecedentes y la licencia de Gas.
  2. Agrega servicios de Pintura y Gas. Gas tiene el motivo de licencia mientras no se valida.
  3. El perfil público responde 404.
  4. Curatoría valida los documentos y aprueba (por API).
  5. El maestro declara su cobertura y su agenda y sube la foto: queda publicado.
  6. El perfil público se ve sin sesión.
  7. Al quitar los servicios, deja de estar publicado (404).
- **Anchos:** páginas del maestro a **390 y 320 px** (móvil); el perfil público también a **1280 px** (escritorio).

### 8.1 Estados medidos (53 por motor)

| Página | Estados |
|---|---|
| `mi-perfil.html` | Con pendientes (postulación, comuna principal y foto, cada uno con su botón); guardar sin foto (error junto a los botones); foto lista con vista previa local; **sin conexión** (corte real: «Reintentar» y la foto se conserva); publicado (✓, enlace «Ver cómo me ven los clientes» y foto pública cargada); sin servicios visibles (pendiente con «Ir a mis servicios»); sesión terminada |
| `mi-cobertura.html` | Sin comunas (paso 2 bloqueado); **CA-13.1** sin comuna principal (error del servidor junto al campo, sin guardar nada); comuna repetida; con otras comunas de dos regiones; cambiar la comuna principal; sesión terminada |
| `mi-agenda.html` | Sin horarios (con la ayuda); faltan el día y las horas (errores del servidor en cada campo); **CA-14.2** término no posterior (y cruce de medianoche); solapamiento; lista por día con 24:00; confirmación para quitar; **CA-14.4** progreso recuperado tras volver a cargar; acceso denegado (curatoría); sesión terminada |
| `perfil-maestro.html` | No publicado (404 neutro, con el mismo texto que una ref inexistente o inválida); publicado, sin sesión, a 390, 320 y 1280 px |
| `mis-servicios.html`, `cuenta.html` | Pendientes con botones a «Mi cobertura» y «Mi perfil»; «Mi cuenta» del maestro con «Mi perfil», «Mi cobertura» y «Mi agenda» |

### 8.2 Resultados (Playwright 1.63.0)

| Motor y versión | Estados | Verificaciones funcionales | Errores de JS | Consola inesperada |
|---|---|---|---|---|
| Chromium 153.0.8010.12 | 53/53 **PASS** | 0 fallidas | 0 | 0 (36 avisos esperados: respuestas 4xx y el corte de red provocado) |
| Firefox 155.0 | 53/53 **PASS** | 0 fallidas | 0 | 0 |

Verificaciones funcionales incluidas en la corrida:

- **Cobertura:**
  - CA-13.1: sin comuna principal no se guarda nada y el error va junto al campo.
  - Lo guardado coincide con `GET /api/maestros/cobertura`, con una sola comuna principal.
  - Al cambiar la comuna principal, la anterior queda entre las otras comunas.
- **Agenda:**
  - CA-14.1: no hay `input type="time"`; "Desde" va de 00 a 23 y "Hasta" de 00 a 24; minutos 00 y 30; "24" solo admite ":00"; no aparece AM/PM.
  - CA-14.2: se rechaza el término no posterior, y el cruce de medianoche lleva su sugerencia; el solapamiento se informa en «Desde».
  - Se aceptan bloques contiguos.
  - CA-14.4: lo elegido se recupera y los bloques guardados siguen ahí.
  - El botón vuelve a su texto después de guardar.
- **Foto:** con el corte de red se ofrece reintentar, y el reintento funciona.
- **Perfil público:**
  - Muestra Pintura ($85.000 por trabajo) y Gas ($16.000 por hora); Gas solo aparece después de validada la licencia.
  - Comunas por nombre, sin marcar la principal; horarios en 24 h.
  - La API pública trae solo `ref`, `nombre`, `foto`, `servicios`, `comunas` y `agenda`, y las comunas sin `es_base`.
  - La página no muestra RUT, teléfono ni correo.
  - `srcset` 160w/480w: el navegador eligió 160 a 390 y 320 px, y 480 a 1280 px.
- **Sesión:** tras la sesión terminada, los enlaces llevan `siguiente=perfil|cobertura|agenda`, e `ingresar.html?siguiente=agenda` lleva a «Mi agenda».

**Regresión** (Chromium 1.63.0, salvo `s3_ui.py`, que corrió en los dos motores): sin fallas en:

- `s3_ui.py`: 48/48 en Chromium y en Firefox;
- `rnf18.py`: 106/106 estados y 16/16 chequeos;
- `s2_maestro.py`, `flujo_s2.py` y `cur_ui.py`;
- `aviso_ui.py`, tras `aviso_prep.py` y `planificador --una-vez`.

**Datos que dejan las corridas:** en cada motor, dos maestros ficticios aprobados con cobertura, agenda y foto, sin servicios al final (por lo tanto, no publicados), y una cuenta de curatoría ficticia.

El pase manual del §5 debe incluir estas cuatro pantallas. En Chrome de Android, en particular:

- «Tomar foto» en «Mi perfil»: debe abrir la cámara **frontal** (`capture="user"`);
- los selectores de hora y minutos: lista nativa, sin AM/PM;
- el perfil público con letra "grande".
