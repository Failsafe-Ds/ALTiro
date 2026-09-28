# ADR-014 — Herramienta de pruebas

- Estado: **Aceptada** — 2026-09-27, aprobada por el equipo.
- Fecha: 2026-09-27
- Relacionado con: RNF-07, RNF-09, RNF-10, RNF-21, RNF-27

## Contexto
Varias pruebas del Sprint 1 dependen del tiempo (expiración de sesión, ventana de intentos) y de recorrer todas las rutas registradas.

## Decisión
**pytest** con **pytest-django** y **time-machine** para congelar el tiempo. Versiones exactas fijadas (RNF-27).

## Notas de implementación
- Cuando una prueba dependa del tiempo, la hora debe salir de Python y no de `now()` de SQL, porque `time-machine` no controla el reloj de la base de datos.

## Alternativas consideradas
- **Runner de Django**: sin dependencias extra, pero menos cómodo para fixtures y control del tiempo.

## Consecuencias
- Las pruebas de control de acceso cuentan para la cobertura que exige RNF-21 (S4).
