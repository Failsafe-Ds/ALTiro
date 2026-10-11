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

## Enmiendas

### E-1 — Sugerencias de toda la región y comunas atendidas en la tarjeta
- **Fecha:** 2026-10-04. Pedido del usuario al revisar la demo; registrado como DA-28.
- **Cambio en el punto 6 (sugerencias):**
  - si no hay resultados, la sugerencia por comuna considera toda la **región** de la comuna pedida, no solo su provincia;
  - los que atienden alguna comuna de la misma provincia van primero; dentro de cada grupo, el orden de siempre (puntaje y desempate);
  - el texto del criterio incumplido pasa a "No trabaja en la comuna que elegiste, pero sí en otra de la misma región.";
  - sigue el máximo de 5, la sección aparte y que nunca se relaja el oficio ni la publicación;
  - rendimiento: la primera carga trae solo a quien atiende la comuna pedida, y la región se carga solo si no hubo resultados. El número de consultas con resultados sigue siendo constante (RNF-01).
- **Cambio en el punto 5 (tarjeta):**
  - la tarjeta agrega `atiende_en` (hasta 3 nombres de comuna) y `atiende_en_mas` (cuántas más), y la pantalla muestra "Atiende en: …";
  - **no se marca la comuna base**. El orden es fijo: primero la comuna buscada, después las de la misma región y al final las demás, cada grupo en orden alfabético. Así el orden no la delata;
  - es la misma información que ya muestra la ficha pública (ADR-019, D-14: comunas atendidas sin indicar la base). Siguen fuera de la respuesta el puntaje, la cercanía, `es_base`, el RUT y el contacto;
  - límite conocido: si un maestro atiende una sola comuna, esa es su base. Pasa lo mismo en la ficha.
- **Pruebas:** `tests/test_busqueda.py` (sugerencias de otra provincia de la región, nunca de otra región, prioridad de la provincia, orden de `atiende_en` igual con cualquier base, máximo de 3 más el conteo).
- **Aprobación:** usuario / equipo de desarrollo, 2026-10-04. Falta la conformidad del representante del producto.

### E-2 — Precio publicado en la tarjeta
- **Fecha:** 2026-10-11. Pedido del usuario en el pulido post-S5; registrado como DA-29.
- **Cambio en el punto 5 (tarjeta):**
  - cada resultado y cada sugerencia agrega `precio`: `{modalidad, modalidad_texto, monto, desde}`, con los mismos nombres y valores que los servicios de la ficha pública (punto 4);
  - es el precio del servicio **visible** del oficio buscado (la misma regla que decide si el maestro entra, RNF-25, CA-24.4). Un servicio de otro oficio nunca cuenta;
  - si el maestro tiene más de un servicio visible de ese oficio, va el de **menor monto** (empate: el más antiguo) y `desde` es verdadero; la pantalla dice "Desde $25.000 por trabajo" o "$12.000 por hora";
  - es un dato que el maestro ya publica en su ficha; no revela la comuna base ni datos personales.
- **Sin filtro ni orden por precio:** el precio no entra al puntaje (punto 2) ni al desempate (punto 3). El orden es el mismo con cualquier precio.
- **Rendimiento (RNF-01):** sale de la misma consulta de servicios que ya hace la búsqueda (`cargar_candidatos`); no agrega consultas ni crece con los resultados.
- **Pruebas:** `tests/test_busqueda.py` (campo en resultados y sugerencias, menor monto con "Desde", otro oficio no cuenta, el orden no cambia al invertir los precios, consultas constantes).
- **Aprobación:** usuario, 2026-10-11 (DA-29). Falta la conformidad del representante del producto.
