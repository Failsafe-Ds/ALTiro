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
| `ejemplo_1` a `ejemplo_6` | Oficio de ejemplo N (por confirmar) | no | **Datos ficticios.** El informe (§2.2) habla de ocho oficios en la red pero no los nombra |

- **Supuesto pendiente:** los nombres de los seis oficios no regulados y si "gasfitería"
  es regulada o solo lo es "gas" se preguntan al representante del producto
  (`docs/alcance/preguntas-representante-s2.md`, P-01 y P-02). Mientras no responda,
  estos seis registros son ficticios y se rotulan "(por confirmar)" en la demostración.
- Cuando llegue la respuesta, se corrige este CSV (códigos y nombres) y se agrega una
  migración de datos nueva; no se edita la migración ya aplicada.
- La carga crea o actualiza por `codigo` y **nunca borra** oficios: un oficio ya
  declarado por un maestro no puede desaparecer en silencio.
