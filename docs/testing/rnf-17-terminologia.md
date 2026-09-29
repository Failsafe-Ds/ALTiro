# Evidencia RNF-17 — Terminología de las vistas del maestro

- **Requisito:** RNF-17. Umbral literal: "Revisión de terminología sobre todas las vistas del maestro; sin siglas técnicas ni jerga de desarrollo".
- **Fecha:** 2026-09-28, cierre de UX del Sprint 2 (frontend). Base: commit `e06d2d2` más los cambios de este cierre, sin commit.
- **Alcance:** textos propios del frontend (`frontend/*.html`, `frontend/js/*.js`, `frontend/errores/*.html`) en las vistas que usa el maestro: inicio, ingresar, postulación, registro, Mi cuenta, Mi postulación, Mis documentos y páginas de error.
- **Fuera de alcance:** los textos que arma el servidor (`mensaje` y `errores` de la API, y el texto de los avisos de RF-35). Otra tarea los está cambiando en paralelo y se revisan aparte.
- **Origen de las listas:** hallazgos T-4, T-5, T-6/M-7, T-10, T-11, T-14 y el "término falso" de RNF-13 de la revisión `ux` del cierre del Sprint 2.

## 1. Términos prohibidos o reemplazados

| Término o frase | Por qué | Reemplazo | Dónde |
|---|---|---|---|
| "se inició una sesión en este navegador" | "navegador" es jerga; el maestro piensa en su teléfono | "Parece que alguien ingresó a una cuenta en este teléfono mientras llenabas el formulario." + botón «Volver a cargar» | `postulacion-maestro.js`, `registro-cliente.js` (T-4) |
| "Recarga la página" | Pide una acción del navegador que el maestro puede no conocer | Botón «Volver a cargar» o «Reintentar» en el mismo aviso | `formulario.js`, `cuenta.js`, `visor.js`, `territorio.js` (T-11, E-6) |
| "… en esta pestaña" | "pestaña" es jerga | "Lo que escribiste seguirá aquí cuando vuelvas a ingresar." | `cuenta.js` (T-5) |
| "Ya tienes una sesión iniciada" | "sesión iniciada" es jerga | "Ya entraste con una cuenta en este teléfono" | `postulacion-maestro.html`, `registro-cliente.html` (T-6/M-7) |
| "Si esta no es tu cuenta… primero cierra sesión en «Mi cuenta»" | No dice cómo comprobar de quién es la cuenta | "Si la sesión abierta no es la tuya, entra a «Mi cuenta», revisa el nombre y pulsa «Cerrar sesión». Después podrás crear tu cuenta." | mismas páginas (T-6/M-7) |
| "Puede que la dirección esté mal escrita" / "Revisa la dirección" | "dirección" se confunde con la dirección de la casa | "Puede que el enlace esté mal escrito…" / "Vuelve al inicio para seguir desde ahí." | `errores/404.html` (T-10) |
| "Tu acceso" (título de paso) | Abstracto; el paso pide contraseña y correo | "Tu contraseña y tu correo (opcional)". La contraseña (obligatoria) va primero | `postulacion-maestro.html` (T-14) |
| "Enviar postulación" | Término falso: la postulación sigue con las fotos (RNF-13) | "Crear mi cuenta y seguir" | `postulacion-maestro.html` |
| "Tu postulación quedó registrada. Ahora ingresa…" | Término falso (RNF-13) | "Primer paso listo. Ahora ingresa con tu RUT y tu contraseña para enviar las fotos de tus documentos." | `ingresar.js` |
| "Listo: tu postulación como maestro quedó registrada." | Término falso, desde «Mi cuenta» | "Primer paso listo. Ahora envía las fotos de tus documentos desde «Mi postulación»." | `cuenta.js` (supuesto de este cierre, ver §4) |
| "Lo que escribiste sigue aquí" en errores al **leer** | No hay nada escrito al cargar una página | "No pudimos conectarnos. Revisa tu señal o tu wifi y toca «Reintentar»." | `api.js` (E-2) |
| "(ya venció)", "quedan 0 días", días negativos | Confuso | "Venció el …" + "⚠ Vencido"; "Quedan N días." / "Queda 1 día." | `expediente.js` |
| Emoji 🪪 | Algunos lectores de pantalla leen su descripción ("tarjeta de identificación") | "►" decorativo con texto alternativo vacío | `base.css` |
| Códigos de la API (`en_revision`, `licencia_sec`, `observado`…) | Jerga de desarrollo | Tablas de textos en `expediente.js` (ya existía) | — |

Para curatoría (no es vista del maestro, pero comparte criterio):

| Antes | Después | Hallazgo |
|---|---|---|
| "Falta, según el servidor:" | "Falta para aprobar:" | E-3 |
| Ayuda del motivo: "el maestro puede verlo en su postulación" | "El maestro verá este motivo si observas, rechazas o suspendes: escríbelo simple, diciendo qué debe hacer el maestro." | E-8 |
| "Recarga para ver la información actual." | "Toca «Recargar el expediente» para ver la información actual." (con el botón) | T-11 |

## 2. Términos permitidos

| Término | Motivo |
|---|---|
| "Ingresar", "Mi cuenta", "Cerrar sesión", "Tu sesión terminó" | Son los rótulos de los botones que el maestro ve y toca; se nombran igual en los avisos. "Sesión" se usa solo junto a esas acciones |
| "teléfono", "señal", "wifi" | Vocabulario cotidiano |
| "RUT", "cédula de identidad", "certificado de antecedentes" | Nombres de los documentos que el maestro tiene en la mano |
| "SEC" | Siempre acompañada de su nombre completo ("Superintendencia de Electricidad y Combustibles (SEC)") en la ayuda de oficios y del paso de licencia |
| "Fecha de emisión", "Fecha de vencimiento (si tiene)" | Salen impresas en el documento. La ayuda lo explica ("Sale impresa en él") |
| "En revisión", "Te pedimos corregir algo", "Aprobado", "No aprobado", "Suspendido" | Estados del expediente en lenguaje del oficio (ADR-017, D-2) |
| "Volver a cargar", "Reintentar" | Rótulos de botones visibles |
| "Paso X de N" | Orientación en el formulario por pasos |

## 3. Resultado tras los cambios

Búsqueda en los textos visibles de las vistas del maestro (se excluyen comentarios, nombres de variables y rutas de la API):

| Término buscado | Apariciones visibles |
|---|---|
| navegador | 0 |
| pestaña | 0 |
| recarga / recargar | 0 (solo nombres de funciones internas) |
| dirección (en el sentido de URL) | 0 |
| servidor | 0 |
| sesión iniciada | 0 |
| "Tu acceso" | 0 |
| "Enviar postulación" / "quedó registrada" | 0 |
| token, CSRF, cookie, URL, código, API | 0 (solo en código) |
| emoji 🪪 | 0 |

Verificación en navegador (Playwright en contenedor, 390 y 320 px): `aviso_ui.py`, `defectos_s2.py`, `s2_maestro.py`, `inc0.py`, `flujo_s2.py`, `csrf_m1.py` y `cur_ui.py`, sin fallas. Textos comprobados: T-4 (con botón), T-5, T-11 (botón «Volver a cargar» al fallar el cierre de sesión y en el visor), E-2, E-4 y E-6.

**Resultado del cierre:** en los textos propios del frontend no quedan términos prohibidos de la lista. RNF-17 sigue abierto hasta revisar los textos del servidor (tarea paralela) y hasta tener la evidencia de la pregunta "¿Hubo palabras que no entendió?" del protocolo de RNF-13 (`docs/testing/rnf-13-protocolo.md`, §5), que no se ha ejecutado.

## 4. Supuestos y pendientes

- **Supuesto:** el aviso de éxito al agregar el perfil de maestro desde «Mi cuenta» también se cambió a "Primer paso listo…", con el mismo criterio de término falso. No venía en los hallazgos: se somete a la revisión `ux`.
- Queda "(SEC)" en el nombre de la licencia ("Licencia de Gas (SEC)"). La sigla está explicada en la ayuda del mismo paso. Si la prueba de RNF-13 muestra que no se entiende, se reemplaza.
- Los mensajes del servidor que aún digan "Recarga la página…" (por ejemplo, en `backend/comun/api.py`) son de la tarea de backend.
