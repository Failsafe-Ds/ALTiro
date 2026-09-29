# Catálogo mínimo de oficios — origen de los datos

Archivo: `oficios.csv` (columnas `codigo`, `nombre`, `regulado` = `si`/`no`, `orden`).
Lo carga la migración `catalogo/migrations/0002_carga_oficios.py` de forma idempotente
(ADR-017, punto 1; mismo patrón que el catálogo territorial, ADR-012). Solo lectura:
no hay endpoints de escritura. Es un **adelanto de datos** del S3 (DA-15); no adelanta RF-36.

## Qué está confirmado y qué es supuesto

| Código | Nombre | Regulado | Origen |
|---|---|---|---|
| `gas` | Gas | sí | Informe: §3.4 y RNF-25 ("Ningún servicio de gas o electricidad queda visible sin licencia vigente asociada") |
| `electricidad` | Electricidad | sí | Informe: §3.4 y RNF-25 |
| `gasfiteria` | Gasfitería (agua y alcantarillado) | no | **Supuesto provisional** (P-01, P-02). El informe (§1) nombra al "gasfíter" |
| `carpinteria` | Carpintería | no | **Supuesto provisional** (P-01) |
| `pintura` | Pintura | no | **Supuesto provisional** (P-01) |
| `albanileria` | Albañilería | no | **Supuesto provisional** (P-01) |
| `cerrajeria` | Cerrajería | no | **Supuesto provisional** (P-01) |
| `jardineria` | Jardinería | no | **Supuesto provisional** (P-01) |

- **Supuesto pendiente de validación:** el informe (§2.2) habla de ocho oficios en la red
  pero no los nombra. Sin respuesta del representante del producto, el equipo adoptó la
  lista provisional de `docs/alcance/preguntas-representante-s2.md` ("Decisión provisional
  sobre P-01 y P-02", 2026-09-28). Los nombres se muestran sin rótulo "(por confirmar)".
- **P-02:** la gasfitería de agua no es regulada; la de gas queda cubierta por el oficio
  "Gas" (regulado). Por eso el nombre visible es "Gasfitería (agua y alcantarillado)" y no
  solo "Gasfitería": así un gasfíter de gas ve que su trabajo va en "Gas" y necesita la
  licencia de la Superintendencia de Electricidad y Combustibles (SEC).
- Orden: primero los dos regulados (piden licencia) y después los no regulados, empezando
  por la gasfitería, que el informe nombra junto al eléctrico (§1).
- Las bases cargadas con la versión anterior (`ejemplo_1` a `ejemplo_6`) se corrigen con la
  migración `0003_renombra_oficios_de_ejemplo.py`, que cambia el código en la misma fila
  (`ejemplo_1` → `gasfiteria`, `ejemplo_2` → `carpinteria`, `ejemplo_3` → `pintura`,
  `ejemplo_4` → `albanileria`, `ejemplo_5` → `cerrajeria`, `ejemplo_6` → `jardineria`),
  de modo que los oficios ya declarados por un maestro siguen apuntando a un oficio válido.
- Cuando responda el representante, se corrige este CSV y se agrega una migración de datos
  nueva; no se edita una migración ya aplicada.
- La carga crea o actualiza por `codigo` y **nunca borra** oficios: un oficio ya
  declarado por un maestro no puede desaparecer en silencio.
