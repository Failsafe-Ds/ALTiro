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

## Siguiente trabajo
S5 (mensajería, evaluación, bitácora e indicadores), en una **sesión nueva** (regla 11). Primer paso: `architect` escribe la propuesta corta del S5 y un ADR, incluyendo la revisión pendiente de la excepción `ParteEquivocada` (propuesta del S4, §11, aclaración 20) y los pasos al S5 de DA-22 a DA-26. Ver `docs/estado-actual.md` → "Pendientes".
