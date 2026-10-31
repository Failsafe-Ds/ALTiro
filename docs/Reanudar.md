# Reanudar — instrucciones de operación

Redactado por Claude a pedido del equipo (2026-09-30). El equipo puede reemplazarlo cuando quiera.

## Modo de operación (se mantiene del Reanudar anterior)
- Operar de forma continua y pasar de un incremento o sprint al siguiente a medida que se terminan.
- Si una decisión no tiene respuesta del equipo en 15 minutos, aplicar la opción recomendada, registrarla como "Aceptada — PROVISIONAL" y continuar.
- Subir a GitHub (`origin/main`, sin `--force`) en cada paso estable, y etiquetar cada sprint cerrado.
- Respetar CLAUDE.md §14: sin `push --force`, sin `reset --hard`, sin borrar volúmenes ni bases sin autorización y sin credenciales reales.

## Reglas de economía de tokens (coordinador)
El costo de un agente crece con **lo que lee × los pasos que da**. Todo lo de abajo busca bajar uno de los dos factores.

1. **Encargos acotados:**
   - un incremento por encargo, con la lista explícita de identificadores (HU, RF, CA) y de ADR o secciones a leer;
   - no pedir "revisa todo";
   - citar `docs/estado-actual.md` en vez de repetir contexto en el encargo.
2. **Menos agentes por incremento:**
   - backend y frontend del mismo incremento van en un solo encargo cuando el cambio de frontend es chico;
   - `ux` solo para pantallas o flujos nuevos, no para ajustes;
   - `architect` una vez por sprint (propuesta corta y un ADR), no por incremento, salvo una decisión nueva real.
3. **Modelo según la tarea:**
   - `architect` y `backend` usan el modelo principal;
   - `qa`, `frontend` y `ux` usan Sonnet (fijado en `.claude/agents/`);
   - las tareas mecánicas (extraer, contar, formatear) usan Sonnet o un script.
4. **QA:**
   - por incremento, solo lo nuevo;
   - el barrido completo, una vez, al cierre del sprint;
   - la regresión la da la suite de pytest.
5. **Pruebas:**
   - los agentes corren pruebas dirigidas y la suite completa una sola vez al final;
   - el coordinador vuelve a correr la suite completa solo antes del commit, mostrando solo la última línea.
6. **Informes:**
   - los agentes entregan 30 líneas o menos;
   - al usuario, un resumen corto por incremento.
7. **Retomar en vez de relanzar:**
   - si un agente se corta por el límite de uso, se retoma con SendMessage, que conserva lo que ya leyó;
   - no se relanza desde cero.
8. **Mantener `docs/estado-actual.md`:**
   - el coordinador agrega una línea por incremento cerrado;
   - es la única lectura obligatoria de los agentes, además de CLAUDE.md.
9. **graphify, solo para código (ADR-025 E-1):**
   - después de cada commit se corre `graphify update .`, que no usa LLM;
   - **nunca se extrae documentación al grafo.**
10. **Medir:**
    - anotar los tokens de cada agente, que vienen en la notificación de término, en `docs/estado-actual.md` → "Consumo";
    - si en el primer incremento del S5 el gasto no baja respecto del incremento 4 del S4 (unos 340 mil), revisar la regla de graphify que obliga a consultar el grafo antes de cada búsqueda.

11. **Sesión nueva por sprint:**
    - al cerrar un sprint (etiqueta subida), el coordinador deja `docs/estado-actual.md` al día y pide al equipo abrir una sesión nueva;
    - la sesión nueva empieza leyendo solo este archivo y `docs/estado-actual.md`;
    - el historial de una conversación larga se vuelve a enviar en cada turno del coordinador.
12. **Agrupar incrementos** que tocan los mismos archivos y ADR en un solo encargo (por ejemplo, los incrementos 5 y 6 del S4).

## ▶ Sesión nueva — empezar aquí (dejado el 2026-10-31)
La sesión anterior (2026-10-30/31) quedó larga y se cortó a pedido del usuario. **Nada de lo siguiente tiene commit todavía.** Leer solo este archivo y `docs/estado-actual.md`, y seguir este orden:

1. **Revisar el trabajo sin commit** (`git status`):
   - skills nuevas `.claude/skills/security-audit/` (Cloudflare) y `.claude/skills/impeccable/`; `ui-ux-pro-max` ya se desinstaló; `.claude/agents/frontend.md` ya apunta a `impeccable`;
   - `.gitignore`: se agregó `docs/testing/security-audit/`;
   - informes `docs/testing/qa-recorrido-chrome-2026-10-30.md` (DEF-CHR-01..06) y `docs/testing/auditoria-diseno-impeccable-2026-10-30.md` (M-01..M-15);
   - **v0.6.9 (ADR-002 E-4.4)**: pulido visual moderno, sobre todo en `frontend/css/base.css`, «Ir al contenido» en las 27 páginas (`<main id="principal">`), botón «Pausar movimiento» del carrusel, puntos de 44 px y DEF-CHR-01 corregido en `frontend/js/mis-trabajos.js:255`;
   - `Glosario-terminos-Informe2.pdf` e `Informe2ALTiroDanielSebastianLuciano-v5.docx` en la raíz son del equipo: **no tocarlos ni agregarlos sin preguntar**.
2. **QA de v0.6.9 antes del commit** (agente `qa`, encargo acotado):
   - correr la suite completa una vez con el montaje `-v "$(pwd -W)/frontend:/frontend:ro"`. Hasta ahora solo pasó `tests/test_frontend_pie_volver.py` (62 pruebas);
   - DEF-CHR-01 de punta a punta: crear un pedido nuevo para el maestro demo, aceptarlo y rechazar otro desde «Mis trabajos». Solo se probó que la confirmación aparece; el POST real no se probó;
   - revisión visual a 390 y 1280 px de las pantallas que no se miraron y heredan los estilos: ficha del maestro, curatoría, comercial, agenda, cobertura, documentos, moderación e indicadores. Usar `scripts/qa-pulido/capturas.py` (la extensión de Chrome no conectaba);
   - contraste con axe o una medición equivalente, y el peso de la portada (RNF-02).
3. **Commit** de todo lo anterior (v0.6.9), si el usuario lo pide o según el modo de operación.
4. **Corregir los 2 hallazgos confirmados (baja) de la auditoría de seguridad** (agente `backend`, un solo encargo con pruebas de regresión). Los detalles están en `docs/testing/security-audit/run-1/REPORT.md` y `findings.json`. La carpeta está fuera de git; si el equipo quiere versionar el resumen, copiarlo a `docs/testing/`.
   - **Primer correo sin reautenticación:** al agregar el primer correo por la rama de sesión de `POST /api/clientes` (`identidad/vistas.py:338` → `servicios.py:300-304`) no se pide la contraseña (RNF-09). Ese correo pasa a servir para recuperar la cuenta. Hay que exigir `_reautenticar` y enmendar ADR-013 p7 y ADR-027 p2.
   - **`POST /api/cuenta/correo` revela si un correo tiene cuenta**, y no tiene límite (`vistas.py:264-273`). Hay que agregarle un límite de frecuencia por cuenta y por origen, y sumar la ruta a la zona Nginx `altiro_estricta`.
   - **Pistas `needs_validation`, para el equipo, no para código:**
     - se confía en X-Real-IP / X-Forwarded-Proto de cualquier contenedor de la red `interna`;
     - la conversación se devuelve sin paginar;
     - `restaurar.sh` acepta un `base.dump` en texto plano sin comprobar su integridad.
5. **Pendientes de diseño** (agente `frontend` con `impeccable`; el carrusel se mantiene):
   - **M-02:** jerarquía de «Mis trabajos». Ojo: `bandeja.js` marca los avisos como vistos.
   - **M-03:** ayuda contextual para el maestro.
   - **M-06:** formularios por pasos (DEF-CHR-03/04).
   - **M-07:** peso y preload de la fuente.
   - **M-08:** pedir de nuevo al mismo maestro. Revisar primero que tenga respaldo en una HU o RF.
   - **M-10:** textos de error que vienen del servidor (DEF-CHR-05/06).
   - **M-11:** títulos h1→h3 en `comercial.html`.
   - **Marcador de la foto mientras carga:** también en `mi-perfil`, `mis-documentos` y `curatoria-expediente`.
   - M-05 (`aria-current`) ya estaba hecho.
6. **Documentación:**
   - registrar el cambio de skills (de `ui-ux-pro-max` a `impeccable` y la nueva `security-audit`) en un ADR o enmienda (CLAUDE.md §15);
   - agregar a `docs/estado-actual.md` una línea por paso cerrado.

**Cuentas demo:** las contraseñas de la sesión anterior estaban en su scratchpad. Si no están disponibles, regenerarlas con `cargar_datos_demo --con-cuentas --restablecer-contrasenas` en altiro-dev, que las muestra una sola vez. **Nunca copiarlas al repo ni a informes.** `altiro-dev` corre en https://localhost:8443.

## Siguiente trabajo — pulido post-S5 (2026-10-11, fuera de sprint) — **CERRADO en v0.6.2**
Pedido del usuario: "dejar todo lindo y funcional, sobre todo con las validaciones mínimas". No pertenece a ningún sprint; el equipo lo ubicará después en el backlog (CLAUDE.md §11). Se trabaja en modo continuo (reglas de arriba), con versiones 0.6.x. Orden:
1. **Commit** de la documentación del 2026-10-11 (validaciones mínimas, ADR-002 E-3, skills). ✔ al cerrar el paso.
2. **Auditoría del backend** con la skill `ponytail-audit` (informe en `docs/testing/auditoria-backend-ponytail.md`), y corrección de lo que haya que corregir (agente `backend`).
3. **Validaciones mínimas** (CLAUDE.md §8-§9) en todas las pantallas y en la API: inventario, corrección y QA con la lista de `qa.md`.
4. **Rediseño visual** (ADR-002 E-3), por partes: base visual (tokens rojos, encabezado en dos versiones, pie, sin «Volver», inicio por rol) → categorías y búsqueda (estilo Fiverr) → páginas de opciones con menú lateral → resto. Skill `ui-ux-pro-max` con pila `html-css` (retirada el 2026-10-30; hoy se usa `impeccable`, ver `.claude/agents/frontend.md`).
5. QA final del pulido y `docs/estado-actual.md` al día.

Resultado: pasos 1 a 5 hechos (commits del 2026-10-11, v0.6.0 a v0.6.2), más DA-29 (precio en resultados). Pendiente del equipo: ubicar este trabajo en el backlog, confirmar las decisiones PROVISIONAL de ADR-002 E-3/E-3.1 y DA-29 con el representante, y mencionarlo en el próximo informe.

Avance y decisiones provisionales: en `docs/estado-actual.md` (línea por paso cerrado) y en "Consumo".

### Ronda 2 del pulido (2026-10-11) — **CERRADA en v0.6.4**
Observaciones del usuario sobre la v0.6.2: dos flujos (ADR-002 E-3.2), ingresar, cuenta, postulación y documentos (ADR-017 E-4), carrusel, centrado y encabezado (E-3.3), «Sobre mí» (DA-30), «Otros servicios» (DA-31). Orden:
1. Terminar el backend (servicio general de «Otros servicios» y sus maestros demo) → QA de la ronda → commit v0.6.3.
Resultado: v0.6.3 (03bbb8b) y v0.6.4; QA ronda 2 en `docs/testing/qa-pulido-post-s5.md`, auditoría 2 con sus 11 hallazgos corregidos. **Ojo:** la suite completa siempre con `-v "$(pwd -W)/frontend:/frontend:ro"`; sin ese montaje faltan 58 pruebas de pantallas.
2. **Auditoría del código** pedida por el usuario: `ponytail-audit` sobre todo el frontend, lo nuevo del backend desde la primera auditoría y lo que esta dejó sin revisar → corrección → QA → commit.

### Rediseño con Bootstrap (2026-10-12) — v0.6.5 a v0.6.8, subido (`f9e509b`)
Pedidos del usuario, uno por versión (detalle en ADR-002 E-4 a E-4.3):
- v0.6.5 (E-4): Bootstrap 5.3.8 alojado y React permitido; «Tu cuenta» en una fila; contenido de la portada centrado.
- v0.6.6 (E-4.1): carrusel de oficios en abanico, dinámico (avanza solo); encabezado rojo con botones blancos de contorno negro.
- v0.6.7 (E-4.2): carrusel sin botones (solo puntos, toque, deslizar y teclado).
- v0.6.8 (E-4.3): contenido centrado en todas las páginas; ficha del maestro en dos columnas con panel «Pide un horario».
- v0.6.9 (E-4.4, 2026-10-31, sin subir): pulido visual moderno (tipografía, sombras, botones, portada, estados de carga), «Ir al contenido», botón «Pausar movimiento» del carrusel, puntos de 44 px, `!important` global de reduced-motion eliminado y DEF-CHR-01 corregido (`mis-trabajos.js`). Pendientes de la auditoría de diseño: M-02, M-03, M-05, M-06, M-07, M-08, M-10, M-11.

**Para retomar:**
- Ver el diseño: `scripts/qa-pulido/capturas.py` (instrucciones dentro; capturas con Playwright en la red `altiro-dev_frontal`, sin cuentas). Las capturas de la extensión de Chrome se congelaban.
- Pendiente del equipo: conformidad del representante, backlog, próximo informe y el riesgo WCAG 2.2.2 (ver `docs/estado-actual.md` → "Pendientes").
- Sugerido: un pase del agente `qa` (lista de `qa.md`) sobre las pantallas de E-4 a E-4.3 y medir de nuevo RNF-02 con Bootstrap.
- Siguiente paso posible con Bootstrap: migrar componentes pantalla por pantalla al tocarlas (no de una vez).

## Trabajo anterior (S5)
S5 cerrado (etiqueta `sprint-5`). Los cinco sprints del informe están construidos. Lo que queda es trabajo del equipo y de la revisión, en una **sesión nueva** (regla 11):
- RNF-13 con personas (DA-26) y RNF-18 manual en navegadores de marca y Android;
- revisar el primer respaldo automático del 2026-10-01 y definir dónde se guarda la copia de la clave;
- responder P-01 a P-33 y revisar los ADR en "Aceptada — PROVISIONAL";
- material de defensa (fila S5 de §5.3.5): borrador en `docs/defensa/guion-defensa.md`, para que el equipo lo ajuste y ensaye.
Ver `docs/estado-actual.md` → "Pendientes" y `docs/testing/cierre-sprint-5.md`.
