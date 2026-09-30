# Plazos de retención de documentos del maestro (RNF-26; ADR-026, E-9)

> **Estado: pendiente V-04 / P-07 (y P-30).** Ningún plazo está definido. Mientras no haya una definición escrita acordada con el representante, las variables quedan vacías y **no se elimina ningún documento**. El planificador deja una advertencia por cada tipo sin plazo que tenga documentos sujetos a retención.

RNF-26 (informe §4.2.2): "Existe un plazo escrito por tipo de documento y cada eliminación queda registrada en la bitácora con fecha y motivo."
V-04 (supuesto, sin validar): retención mientras el maestro esté activo, más el plazo de reclamo del consumidor.

## Tabla de tipos
| Tipo (`documento.tipo`) | Documento | Variable | Plazo (días) | Estado |
|---|---|---|---|---|
| `cedula_identidad` | Cédula de identidad (anverso y reverso) | `RETENCION_DIAS_CEDULA_IDENTIDAD` | — | Pendiente V-04/P-07 |
| `certificado_antecedentes` | Certificado de antecedentes | `RETENCION_DIAS_CERTIFICADO_ANTECEDENTES` | — | Pendiente V-04/P-07 |
| `licencia_sec` | Licencia SEC | `RETENCION_DIAS_LICENCIA_SEC` | — | Pendiente V-04/P-07 |

## Regla aplicada (`backend/expediente/retencion.py`, tarea del planificador)
- **Desde cuándo:** la fecha en que el expediente pasó a `rechazado` o `suspendido` (`expediente.estado_cambiado_en`). Esto es lo que se entiende por "deja de estar activo" (E-9.2, supuesto V-04/P-07).
- **Qué no se toca:** los expedientes `en_revision`, `observado` y `aprobado`, y cualquier documento antes de que se cumpla el plazo.
- **Qué hace al cumplirse el plazo:** borra los archivos cifrados, marca `eliminado_en` y `motivo_eliminacion` en la fila (que se conserva) y escribe en la bitácora `documento_eliminado_retencion` con autor Sistema, el tipo, el plazo aplicado y el motivo (RF-37).
- **Después de eliminar:** el enlace responde 409 con un mensaje accionable. Un enlace emitido antes responde 404. Curatoría ve el documento con `eliminado: true` y no puede revisarlo (409). El documento ya no cuenta para aprobar ni para habilitar un oficio.

## Cómo fijar un plazo
Cuando el representante lo defina, anote aquí el valor, la fuente y la fecha, y configure la variable en `.env` (la lee el servicio `planificador`, RNF-24). Por ejemplo: `RETENCION_DIAS_CEDULA_IDENTIDAD=<días>`.
