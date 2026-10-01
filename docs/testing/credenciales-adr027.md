# Evidencia — cambio de contraseña, cambio de correo y recuperación (ADR-027, DA-27)

- Fecha: 2026-09-30. Preparado por Claude. Pila local (Docker Compose), `app` reconstruida con la migración `identidad.0004` y el volumen `buzon`.
- Requisitos: RNF-09 (reautenticación), RNF-10, RNF-14 a RNF-16, RNF-18; reglas A-26 a A-30 (`tests/reglas_rnf21.py`).
- Datos ficticios en la pila principal:
  - `qa.cred.*@example.com` y `qa.humo.*@example.com`;
  - RUT sintéticos 32.xxx.xxx y 33.xxx.xxx.

## 1. Pruebas automáticas
`backend/tests/test_credenciales.py`: 29 pruebas (32 casos con los parámetros), todas pasan. Cubren:

| Regla | Qué se prueba |
|---|---|
| A-26 | Sin la contraseña actual, o con una equivocada, → 400 en `contrasena` y nada cambia, tanto en contraseña como en correo |
| A-27 | 5 fallos de reautenticación → 429 con `Retry-After: 900`, aunque después se escriba la correcta |
| A-28 | Cambiar o recuperar la contraseña deja las demás sesiones en 401; la propia sigue (cambio) o no se inicia (recuperación) |
| A-29 | La solicitud responde 202 con el mismo cuerpo exista o no la cuenta y tenga o no correo; solo envía a cuentas con correo; 6.ª solicitud del mismo origen → 429 |
| A-30 | Enlace de un solo uso; vence a los 30 min; uno nuevo o un cambio de contraseña anulan los anteriores; el comando asistido crea un enlace que funciona |

También se prueba:
- la política de contraseña y "distinta de la actual";
- correo ajeno o igual al actual;
- un maestro sin correo puede agregarlo;
- 3 enlaces por cuenta y hora;
- borrado de las solicitudes de más de 24 h;
- el token no se guarda en claro (solo SHA-256) y va en el fragmento `#t=`;
- ni el token, ni la contraseña, ni el correo llegan al registro;
- un buzón que falla no cambia la respuesta.

Además, PI-252 (`test_api_sesion.py`) se actualizó: antes comprobaba que estas rutas *no* existieran.

## 2. Navegador (Playwright 1.63, 360 × 740)

| Paso | Chromium | Firefox |
|---|---|---|
| `cuenta.html`: contraseña actual equivocada → "La contraseña actual no es correcta…"; campos de contraseña vaciados | Cumple | — |
| Cambio de contraseña → mensaje de éxito; otra sesión abierta queda en `ingresar.html?aviso=sesion` | Cumple | Cumple |
| Cambio de correo → «Mis datos» muestra el correo nuevo | Cumple | Cumple |
| Maestro sin correo → el formulario dice «Agregar mi correo» | Cumple | Cumple |
| «Olvidé mi contraseña» desde `ingresar.html` → mensaje único | Cumple | Cumple |
| `nueva-contrasena.html#t=…` (token leído del buzón): el `#t=` desaparece de la barra; contraseña corta → error en el campo; contraseña válida → «Listo…» e ingreso con la nueva | Cumple | — |
| Reusar el enlace → "Este enlace ya no sirve…" con «Pedir un enlace nuevo» | Cumple | — |
| Página sin token → aviso con «Pedir un enlace nuevo» | Cumple | — |
| axe-core 4.10.3 (WCAG 2.0/2.1/2.2 AA) en `cuenta`, `recuperar` y `nueva-contrasena` (2 estados) | 0 violaciones | 0 violaciones (cuenta, recuperar) |
| Objetivos táctiles < 44 px y desborde lateral | 0 y no | 0 y no |
| Errores de JavaScript o de CSP | 0 | 0 |

- **Buzón:** 3 correos escritos en `/buzon` (contraseña cambiada, correo cambiado, enlace de recuperación). El directorio es `drwx------ altiro`.
- **Registros:** el token del enlace aparece **0 veces** en `docker compose logs proxy` y 0 veces en `logs app`.
- **Comando asistido:** `crear_enlace_recuperacion --cuenta <RUT>` imprime el enlace de 30 minutos y la advertencia de verificar la identidad.

## 3. Revisión de redundancias (mismo cambio)

| Duplicado | Copias | Ahora |
|---|---|---|
| `elemento(etiqueta, clase, ...hijos)` en JS | 14 idénticas | `frontend/js/dom.js` (`dom.elemento`), cargado después de `api.js` en 16 páginas |
| `parrafo` en JS | 2 idénticas | `dom.elemento("p", …)` |
| `opcion` en `buscar.js` y `hora24.js` | 2 idénticas | `dom.opcion` (las de `territorio.js` y `mis-servicios.js` son distintas y se mantienen) |
| `_json` (JSON con `no-store`) | 7 idénticas | `comun.api.respuesta_json` |
| `_instante` (ISO en hora de Santiago) | 3 idénticas | `perfil.ocurrencias.iso_local` |
| `_valores(choices)` y `[valor for valor, _ in X.choices]` | 2 + 9 | `X.values` de Django (`makemigrations --check`: sin cambios) |
| Búsqueda de cuenta por correo o RUT | 2 (`autenticar`, comando administrativo) | `identidad.autenticacion.buscar_usuario` |
| Respuesta 429 con `Retry-After` | 1 (+3 nuevas) | `identidad.vistas._respuesta_espera` |

- **Prueba de humo tras el cambio:** 18 pantallas, sin sesión y con cliente, maestro y administrador, en Chromium y Firefox: 0 errores de JavaScript ni de consola.
- **Se revisaron y no se unificaron** (mismo nombre, distinto comportamiento): `sinAcceso`, `errorCarga`, `textoPrecio`, `avisarSesionTerminada`, `_fecha`, `_motivo`, `_validar` y `_pagina`.

## 4. Suite completa

`pytest -q` (comando de `docs/estado-actual.md`): **1920 pasan en 10 min 10 s** (antes 1888).
