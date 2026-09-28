# ADR-004 — Hash de contraseñas

- Estado: **Aceptada** — 2026-09-28, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-27
- Relacionado con: RNF-04, RNF-05, R-03

## Contexto
RNF-05: "Ninguna contraseña se puede recuperar desde la base de datos, porque se almacena mediante un hash adaptativo diseñado para resistir ataques". RNF-04 limita los recursos del equipo de demostración. La política funcional de contraseña (12 a 128 caracteres, sin recorte, lista local de contraseñas comunes) quedó cerrada en ADR-013; este ADR decide solo el algoritmo y sus parámetros.

## Decisión propuesta
**Argon2id** mediante `argon2-cffi`, como primer hasher de Django. Si cambian los parámetros, el hash se recalcula al iniciar sesión.

### Parámetros
Los valores por defecto del hasher de Django usan del orden de 100 MiB por verificación (`memory_cost=102400`). Con 10 usuarios simultáneos (concurrencia objetivo) eso ronda 1 GB y presiona RNF-04. Se fijarán parámetros explícitos, del orden de 19–64 MiB de memoria, con un tiempo de verificación de ~250 ms o menos, medidos en el equipo de referencia.

## Alternativas consideradas
- **bcrypt**: aceptable; límite de 72 bytes, que no cubre contraseñas de hasta 128 caracteres sin recortarlas (ADR-013, punto 3).
- **PBKDF2** (por defecto en Django): cumple, pero es menos resistente a GPU.

## Pendiente
- Registrar aquí los parámetros finales (memoria, iteraciones, paralelismo) tras medir en el equipo de demostración.

## Decisión (2026-09-28)
- **Argon2id** con `argon2-cffi` 25.1.0 (dependencias fijadas en `backend/requirements.txt`), como único hasher configurado en `PASSWORD_HASHERS`.
- Parámetros: `memory_cost=65536` (64 MiB), `time_cost=3`, `parallelism=1`.
- Medición (2026-09-28, equipo de desarrollo, Windows 11 con Docker Desktop, imagen `python:3.13.15-slim-bookworm`, promedio de 10 verificaciones): 135 ms por verificación. Otras combinaciones medidas: 19 MiB/t=2: 18 ms; 46 MiB/t=1: 44 ms; 64 MiB/t=2: 98 ms.
- Memoria: con 2 workers síncronos de gunicorn hay como máximo 2 verificaciones simultáneas (unos 128 MiB), dentro del techo de 2 GB de RNF-04. Si se aumentan los workers, revisar este cálculo.
- Si cambian los parámetros, Django recalcula el hash al siguiente inicio de sesión correcto.
