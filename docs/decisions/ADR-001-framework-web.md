# ADR-001 — Framework web del backend

- Estado: **Aceptada** — 2026-09-27, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-27
- Relacionado con: RF-01, RF-02, RF-03, RNF-05, RNF-07, RNF-09, RNF-11; CP-10

## Contexto
El informe fija backend en Python (§4.1), pero no el framework. El Sprint 1 necesita modelo de usuario, hash de contraseñas, sesiones en servidor, CSRF, migraciones y un cliente de pruebas. CP-10 (§5.1): "La tecnología es conocida solo parcialmente por el equipo".

## Decisión propuesta
- **Django**, con `django.contrib.admin` fuera de `INSTALLED_APPS`.
- Modelo de usuario propio basado en `AbstractBaseUser` **sin** `PermissionsMixin`, con `AUTH_USER_MODEL` fijado en la primera migración (cambiarlo después es muy costoso en Django).

### Por qué se excluye el panel de administración
El panel solo expone los modelos que se registran explícitamente, pero aun así se excluye porque:
1. Salta las reglas de dominio: motivo obligatorio (RF-32, CA-19.1), bloqueo de oficios regulados (RF-33) y escritura en la bitácora (RF-37, CA-19.3).
2. Es un CRUD genérico sobre datos sensibles que ignora las políticas por recurso y por finalidad (RNF-07, reglas de HU-25).
3. Agrega una segunda superficie de inicio de sesión que podría quedar fuera del limitador de intentos.
4. Crea un segundo sistema de roles (`is_staff`, `is_superuser`, grupos) paralelo a `usuario_rol`.

## Alternativas consideradas
- **FastAPI + SQLAlchemy + Alembic**: más explícito, pero sesiones y CSRF se construyen a mano (más riesgo de seguridad).
- **Flask**: mismo problema que FastAPI.

## Consecuencias
- Menos código propio de seguridad.
- Curatoría (HU-19, RF-32, RF-33, S2) y comercial (HU-20, RF-36, S3) necesitan pantallas propias, que el informe exige de todos modos.
- `django.core.signing` sirve para los enlaces temporales de RNF-06.

## Pendiente
- ~~Confirmar que el equipo conoce Django o puede aprenderlo a tiempo (CP-10). Es la decisión más costosa de revertir.~~ **Resuelto** — 2026-09-27: el equipo de desarrollo aprobó este ADR.
