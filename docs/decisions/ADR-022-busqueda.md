# ADR-022 — Búsqueda, filtros excluyentes y ordenamiento

- Estado: **Aceptada — PROVISIONAL** (2026-09-29). Se aplicó la opción recomendada sin respuesta del equipo, según `docs/Reanudar.md`. Se revisa en la revisión del Sprint 4.
- Relacionado con: RF-09 a RF-14, RNF-01, RNF-02, RNF-03, RNF-21, RNF-25, HU-02 a HU-05, CA-02.x, CA-03.x, CA-04.1, CA-13.2, CA-14.3, CA-24.4; ADR-019, ADR-020
- Origen: propuesta del S4, D-2 a D-8, D-18 y D-19.

## Decisión
1. **Filtros (RF-09):**
   - `oficio` y `comuna` son obligatorios. La comuna viene precargada con la del perfil del cliente.
   - `fecha`, `inicio` y `fin` son opcionales, pero van los tres juntos o ninguno.
   - Parámetros desconocidos: 400 general. Parámetros inválidos: 400 en el campo.
   - Un maestro entra en los resultados principales solo si se cumple todo lo siguiente:
     - está publicado según la regla única (ADR-019);
     - tiene un servicio **visible** del oficio (RNF-25, CA-24.4);
     - la comuna pedida está en su cobertura (CA-13.2);
     - si hay filtro de bloque, tiene una ocurrencia **ofrecible** ese día que **contiene** el rango pedido.
   - Una ocurrencia es ofrecible si su bloque está activo, no se cruza con un ticket aceptado o finalizado (CA-14.3) y empieza en más de 4 horas (RF-16).
   - La decisión final pasa por la función pura de la regla única. Una prueba de propiedad compara la búsqueda con la regla aplicada maestro por maestro.
2. **Puntaje (RF-10), tal como lo da el informe:** `0,6·D + 0,4·C`, que se calcula como `6·D + 4·C` en enteros.
   - Disponibilidad (D):
     - 100 si hay filtro de bloque (todos los que pasan el filtro lo cumplen);
     - sin filtro de bloque: 60 si tiene una ocurrencia ofrecible hoy, 30 si la tiene entre hoy+1 y hoy+3, y 0 si no.
   - Cercanía (C): 100 si la comuna pedida es su comuna base; 60 si está en su cobertura.
   - **El puntaje y sus componentes no van en la respuesta**, porque la cercanía revelaría la comuna base (ADR-019, D-14). La fórmula se publica en una página de ayuda.
3. **Desempate (RF-11):**
   - primero la calificación promedio y después la cantidad de evaluaciones (valen `None` y 0 hasta el S5);
   - al final, `sha256(ref pública + fecha de hoy)`, un sorteo diario que es determinista dentro del día.
4. **Ficha (RF-14):** agrega `bloques` de los próximos **14 días** (P-19), cada uno libre u ocupado.
   - Un bloque ocupado no lleva ningún dato del ticket.
   - Se omiten las ocurrencias que empiezan en 4 horas o menos.
   - Los servicios exponen la ref del catálogo, no la de `servicio_maestro`.
5. **Tarjeta (RF-13):** ref pública, nombre, foto de 160 px, oficio y "Todavía no tiene evaluaciones". Nunca la comuna base, el RUT, el contacto ni el puntaje.
6. **Sugerencias (RF-12, condicionado):**
   - solo cuando no hay resultados principales;
   - se relaja un filtro a la vez: primero el bloque, después la comuna de la misma provincia;
   - nunca se relaja el oficio ni la regla de publicación;
   - como máximo 5, en una sección separada y cada una con el criterio que incumple.
7. **Rendimiento (RNF-01):**
   - el contexto se carga en lote (ADR-019 E-1) con un número de consultas constante;
   - índices nuevos;
   - páginas de 20;
   - `Cache-Control: no-store`.
8. **Medición:**
   - **RNF-21:** por reglas, con un catálogo `tests/reglas_rnf21.py` y la marca `@pytest.mark.regla`. Exige 60 % **por grupo** (filtros, puntaje, cierre y acceso).
   - **RNF-01:** script con 10 hilos y al menos 200 búsquedas sobre el volumen sintético. Al menos el 95 % debe responder en 2 s o menos.
   - **RNF-02:** Playwright con 4 Mbps de bajada, 1 Mbps de subida y 150 ms de latencia.
