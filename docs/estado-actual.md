# Estado actual del proyecto (hoja corta para agentes)

> Leer esto **en lugar de** recorrer todos los ADR, propuestas y cierres. Abrir un ADR o una propuesta solo si el encargo lo cita o si una regla de abajo no alcanza. Si hay contradicción, prevalecen el informe y el ADR (CLAUDE.md §2).
> Actualizar esta hoja al cerrar cada incremento: una línea por cambio, sin narrativa.

Última actualización: 2026-09-30 (S4, incrementos 1 a 6 hechos, commit siguiente a `1bcf954`; suite 1678).

## Sprints
| Sprint | Estado | Etiqueta / cierre |
|---|---|---|
| S1 Identidad, roles y acceso | Cerrado | `sprint-1`, `docs/testing/cierre-sprint-1.md` |
| S2 Expediente y curatoría | Cerrado | `sprint-2`, `cierre-sprint-2.md` |
| S3 Catálogo, cobertura y agenda | Cerrado con observaciones | `sprint-3`, `cierre-sprint-3.md` |
| S4 Búsqueda y ticket | En curso: incrementos 1 a 6 hechos; faltan 7 a 9 | propuesta §9 y §11 |
| S5 Mensajería, evaluación, bitácora e indicadores | No iniciado | — |

## Stack y cómo correr
- Docker Compose: `init`, `db` (PostgreSQL 16), `app` (Django 5.2 + gunicorn), `proxy` (Nginx, TLS autofirmado, gzip) y `planificador` (cada 300 s).
- Frontend estático en HTML, CSS y JS, sin framework y con CSP estricta (sin inline).
- **Suite completa** (Git Bash, desde la raíz): `MSYS_NO_PATHCONV=1 docker compose run --rm -v "$(pwd -W)/backend:/app" --entrypoint pytest app -q`. Tarda unos 8 min y hoy pasan 1678.
- **Durante el desarrollo**, solo pruebas dirigidas: el mismo comando con `tests/test_x.py -k nombre`.
- Migrar: `docker compose exec app python manage.py migrate`. Tras cambiar la plantilla del proxy: `docker compose up -d --force-recreate proxy`.

## Apps del backend (`backend/`)
`identidad` (usuario propio, sesión, Argon2id) · `autorizacion` (políticas, `obtener_autorizado`, enlaces firmados) · `bitacora` (solo inserción) · `territorio` · `catalogo` · `expediente` (documentos cifrados, curatoría, planificador) · `perfil` (servicios, cobertura, agenda, foto, publicación, ocurrencias, ocupación) · `busqueda` · `tickets` · `comun` (API, middleware, errores).

## Invariantes transversales (resumen de ADR)
- **Rutas privadas por defecto:** `@publica` para abrir una ruta. Verificar siempre identidad, rol, propiedad y estado en el servidor.
- **Acceso a recursos ajenos (ADR-011):**
  - recurso ajeno → **404 idéntico** y registro en `acceso_denegado`;
  - rol o parte equivocada → 403 registrado;
  - las URL usan `ref` UUID, nunca `id`.
  - Toda ruta nueva con `<uuid:ref>` necesita prueba de terceros. La prueba de control de rutas no admite exenciones nuevas.
- **Errores (ADR-013):** formato `{mensaje, errores}`. Una clave desconocida da 400 general; un campo no permitido da 400 en ese campo. Sin códigos internos.
- **Bitácora, `ticket_evento` y `acceso_denegado`:** solo inserción, con triggers y `managed=False`, sin FK de autor (ADR-010).
- **Sesión (ADR-005):** 1800 s deslizantes; las consultas automáticas no la renuevan. CSRF: reintento único ante `AlTiro-Rechazo: csrf`.
- **Documentos (ADR-015):** AES-256-GCM, sin EXIF y máximo 8 MB. Enlace firmado de 600 s. El volumen de documentos solo va montado en `app`.
- **Publicación (ADR-019):** la visibilidad se calcula en cada lectura con `perfil/publicacion.py` y nunca se guarda una marca. Elegible = aprobado + comuna base + foto.
- **Agenda (ADR-020):**
  - minutos múltiplos de 30, sin cruzar la medianoche;
  - `perfil/ocurrencias.py` resuelve el horario de verano (America/Santiago);
  - los plazos se miden en tiempo real.
- **Búsqueda (ADR-022):**
  - filtros excluyentes;
  - puntaje `6·D + 4·C`, nunca expuesto;
  - desempate con `sha256(ref+fecha)`;
  - sugerencias en una sección aparte;
  - horizonte de 14 días.
- **Ticket (ADR-023):**
  - un solo registro para ticket y orden;
  - estados `pendiente`, `aceptado`, `finalizado` y `cerrado`, con 5 motivos de cierre;
  - `vence_en = LEAST(enviado + 24 h, inicio − 4 h)`;
  - se bloquea primero el expediente del maestro y después los tickets;
  - mientras está pendiente, el maestro no recibe dirección, teléfono ni nombre del cliente;
  - contacto mutuo solo tras aceptar.
  - transiciones en `tickets/transiciones.py`: aceptar y rechazar (maestro), cancelar (cliente); repetir da 200, lo demás 409 accionable;
  - la parte equivocada recibe 403 registrado con `ParteEquivocada` (middleware de `autorizacion`);
  - cierre por vencimiento: tarea `cerrar_vencidos` del planificador (`skip_locked`) y protección al actuar (cierra, guarda y responde 409), con autor Sistema;
  - `ticket_cerrado` va a ambas partes; con `bloque_tomado`, el aviso del cliente trae `enlace` a `buscar.html` (CA-23.5).
- **Avisos de tickets (ADR-024):** tabla `aviso_ticket`, sin datos personales. En pantalla se dice "pedido" y "horario".
- **Pruebas:** reglas críticas con `@pytest.mark.regla`, catalogadas en `tests/reglas_rnf21.py`, al menos 60 % por grupo (activos: filtros, puntaje, acceso y cierre). Fechas con time-machine.
- **Datos:** solo ficticios. Nunca datos personales, contraseñas ni tokens en registros.

## Decisiones provisionales abiertas
ADR-016 E-1 y ADR-018 a ADR-024 están en "Aceptada — PROVISIONAL" y se revisan en la revisión del sprint. Las preguntas al representante P-01 a P-23 (`docs/alcance/preguntas-representante-s2.md`) siguen sin respuesta.

## Pendientes y riesgos vigentes
- **S4:**
  - incremento 7: bandejas, avisos y pantallas "mis pedidos" y "mis trabajos";
  - incremento 7: los botones aceptar, rechazar y cancelar, y mostrar el `enlace` del aviso de `bloque_tomado`;
  - incremento 8: RF-12, si hay capacidad;
  - incremento 9: mediciones de RNF-01 a 04, RNF-21 y RNF-14 a 18 con 1.000 tickets en una pila aparte, más el QA.
- **RNF-13** sin ejecutar (DA-17: antes de la revisión del S4; requiere personas).
- **RNF-18:** falta el pase manual en navegadores de marca y en Android.
- **Observaciones del S3:** OBS-S3-02 (precios de referencia sin pantalla pública), OBS-S3-04 (scripts de Playwright sin el campo `bloques`) y OBS-S3-05 (contrastes del S3).

## Consumo de agentes (tokens informados al terminar)
| Fecha | Tarea | Agente / modelo | Tokens |
|---|---|---|---|
| 2026-09-29 | QA de cierre del S3 | qa (principal) | ~338 mil |
| 2026-09-29 | S4 incremento 4 (tickets) | backend (principal) | ~341 mil |
| 2026-09-30 | S4 incrementos 5 y 6 (transiciones y cierre) | backend (principal) | ~177 mil (69 pasos; dos incrementos juntos) |
