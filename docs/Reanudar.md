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

## ▶ Sesión nueva — empezar aquí (dejado el 2026-11-01)
Todo está commiteado y subido a `origin/main` (v0.6.16). Leer solo este archivo y `docs/estado-actual.md`.

**Hecho en las sesiones del 2026-10-31 y 2026-11-01:**
- v0.6.9: pulido visual, «Ir al contenido», pausa del carrusel, DEF-CHR-01. QA en `docs/testing/qa-v0.6.9-2026-10-31.md`. ADR-033 (skills `impeccable` y `security-audit`, Propuesta).
- v0.6.10: los 2 hallazgos de la auditoría de seguridad run-1 (primer correo con contraseña, ADR-013 E-10; tope en `/api/cuenta/correo` y zona Nginx, ADR-027 E-2).
- v0.6.11 y v0.6.12: pendientes de diseño M-02, M-03, M-06, M-07, M-10, M-11 y el marcador de foto. QA en `docs/testing/qa-pendientes-v0.6.12-2026-10-31.md`.
- v0.6.13 a v0.6.16 (ADR-002 E-4.7 a E-4.10), a pedido del usuario:
  - rojo más suave (#B3353A);
  - portada rehecha: foto arriba con «Buscar un maestro» y «Crear mi cuenta», carrusel grande de oficios, franja «¿Eres maestro?», «Cómo funciona» plegado al fondo;
  - foto de Wikimedia (CC BY-SA 4.0, `docs/creditos-imagenes.md`) en la portada y en el ingreso, con fondo de respaldo;
  - búsqueda en dos columnas en escritorio.
- Suite completa: **2139 passed** (con el montaje de `frontend/`).

**Lecciones de diseño de esta ronda (el usuario las pidió explícitamente):**
- Menos piezas y una jerarquía clara. La portada de v0.6.13 («cosas y cosas») se rechazó.
- Registrarse y buscar deben verse sin desplazarse. Lo informativo va al fondo, plegado.
- El carrusel debe moverse solo. Con `prefers-reduced-motion` no se mueve y no muestra el botón de pausa. Si el usuario dice que no se mueve, revisar «Efectos de animación» de Windows.
- Revisar siempre las capturas a 390 y 1280 px antes de entregar (`scripts/qa-pulido/capturas.py`, o un script de Playwright en la red `altiro-dev_frontal`).

**Pendientes para retomar:**
1. **El usuario dijo «después trabajamos más»:** preguntar qué quiere seguir mejorando de la interfaz antes de proponer.
2. **M-08** («Pedir de nuevo a este maestro»): no tiene respaldo en ninguna HU ni RF. Decide el equipo: backlog (CLAUDE.md §11) o solo un enlace al perfil.
3. **RNF-02 en la página de resultados** con red emulada a 4 Mbps (solo se midió la portada: 0,55 s).
4. **Recortar el CSS de Bootstrap** (232 KB).
5. **Pistas de seguridad `needs_validation`, para el equipo:**
   - se confía en X-Real-IP / X-Forwarded-Proto entre contenedores;
   - la conversación se entrega sin paginar;
   - `restaurar.sh` no comprueba la integridad del respaldo.
6. **Ratificar las decisiones en Propuesta:** ADR-033, ADR-013 E-10, ADR-027 E-2 y ADR-002 E-4.7 a E-4.10 (incluida la desviación de 44 px de los puntos del carrusel en el celular, E-4.9).
7. **Tema para el equipo:** la calificación es una sola por maestro aunque tenga varios oficios (RF-30). Calificar por oficio sería un cambio de alcance.

**Antes de cada push** (pedido del usuario):
- correr la suite completa;
- revisar `git diff origin/main..HEAD` buscando secretos, `.env`, respaldos, contraseñas demo, datos personales reales, rutas personales y EXIF en imágenes.

`Glosario-terminos-Informe2.pdf` e `Informe2ALTiroDanielSebastianLuciano-v5.docx` (en la raíz) son del equipo: no agregarlos sin preguntar.

**Entorno:**
- `altiro-dev` corre en https://localhost:8443. Docker Desktop puede tardar en arrancar.
- Contraseñas demo: regenerarlas con `cargar_datos_demo --con-cuentas --restablecer-contrasenas`, que las muestra una sola vez. Nunca copiarlas al repo.
- En altiro-dev quedaron pedidos de prueba del QA («QA ACEPTAR», «QA RECHAZAR», «QA aviso v0.6.12 prueba»).
- La copia de demostración (clon de GitHub, `altiro`, puerto 443) necesita `git pull` y `docker compose up -d --build`. Incluye un cambio en la plantilla del proxy.

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
