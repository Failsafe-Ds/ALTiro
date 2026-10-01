# ADR-028 — Datos ficticios de demostración con cuentas para el flujo completo

- Estado: **Borrador** (2026-10-01). Lo pidió el usuario el 2026-10-01 y ya está implementado; falta que el equipo lo acepte.
- Relacionado con: RNF-05, RNF-23, RF-36, RF-10 a RF-16 (búsqueda y ticket), CA-23.5; ADR-004, ADR-010, ADR-012, ADR-013 (punto 3), ADR-019, ADR-020, ADR-022, ADR-023, ADR-026 (E-1); propuesta del S4 §2 (volumen de prueba).

## Contexto
`cargar_datos_demo` solo crea servicios del catálogo rotulados "(demo)". En una instalación de demostración no hay maestros publicados ni cuentas con las que entrar: "Buscar un maestro" no devuelve nada y no se puede mostrar el flujo de pedido, aceptación, conversación, precio y evaluación. `generar_volumen_prueba` sí crea maestros publicados y tickets, pero con contraseñas inutilizables y solo para una pila aparte (RNF-01, RNF-03).

Además, la base de demostración tiene oficios `oficio_prueba_s3_<motor>_<n>` y `oficio_qa3_<n>`, desactivados. Los dieron de alta las verificaciones de QA del S3 (RNF-18 con Playwright en Chromium y Firefox, y el script `qa3`) desde la pantalla de comercial **contra la pila de demostración**, y nadie los quitó. No salen en la búsqueda ni en la postulación (solo se listan oficios activos), pero sí en el catálogo de comercial.

## Decisión
1. **Opción explícita** `python manage.py cargar_datos_demo --con-cuentas`. Sin la opción, el comando hace lo mismo que antes.
2. **Qué crea** (idempotente, todo rotulado "(demo)"; código en `busqueda/cuentas_demo.py`):
   - 10 maestros con expediente aprobado, comuna base, cobertura, foto sintética y agenda de lunes a sábado (09:00-13:00 y 14:00-18:00): 7 en el Gran Concepción y 3 en Santiago. Cada uno publica 2 o 3 servicios de 2 oficios **no regulados**, rotando el catálogo (los regulados exigirían licencia vigente con archivo cifrado);
   - RUT sintéticos desde 49.990.001 (el volumen de prueba usa 50.000.000 a 59.999.999), teléfonos `+56 9 0002 0NNN`, correos `@example.com`;
   - cuentas con ingreso: el maestro `49990001-5` (también `maestro.demo@example.com`) y los clientes `cliente.demo.1@example.com` (Concepción) y `cliente.demo.2@example.com` (Santiago). Los otros 9 maestros tienen contraseña inutilizable;
   - 4 tickets del cliente 1 con el maestro con ingreso: pendiente y aceptado (con 2 mensajes) en el futuro, con más de 4 horas de anticipación (RF-16); finalizado con precio coherente con el CHECK de ADR-026 E-1 y sin evaluar; y cerrado por `rechazado_maestro`. Cada uno con su historial en `ticket_evento`. Se crean solo si ese cliente todavía no tiene tickets.
3. **Credenciales:**
   - nunca una contraseña fija en el repositorio;
   - cada ejecución genera una contraseña con `secrets` (16 caracteres en 4 grupos) que pasa `validar_contrasena_nueva` (ADR-013), se guarda con el hasher de ADR-004 y se imprime **una sola vez** en la salida estándar, nunca en el registro (el evento de aplicación lleva solo conteos);
   - las cuentas que ya existen conservan su contraseña, salvo con `--restablecer-contrasenas`. Esa opción usa `identidad.servicios.cambiar_contrasena` (cierra las sesiones abiertas y anula enlaces de recuperación).
4. **Reglas compartidas, no duplicadas:** `busqueda/ficticios.py` reúne el RUT con dígito verificador, la foto sintética, la selección de servicios no regulados, la creación atómica del maestro publicado y la construcción del ticket con `vence_en` de ADR-023. Lo usan `generar_volumen_prueba` y `cuentas_demo`.
5. **Sin bitácora ni avisos** (ADR-010), igual que `cargar_datos_demo` y el volumen de prueba: es una carga de consola, no una acción de una persona en la aplicación.
6. **Limpieza de oficios de prueba:** `python manage.py limpiar_oficios_de_prueba`.
   - Por defecto solo lista; borra con `--confirmo`.
   - Se limita a oficios **desactivados** cuyo código calza exactamente con `oficio_prueba_s3_(chromium|firefox)_<n>` o `oficio_qa3_<n>`. Borra sus servicios y modalidades en una transacción por oficio.
   - Si algo los referencia (`PROTECT`), los conserva. Las entradas de bitácora sobre ellos se conservan.
   - Es idempotente. No se ejecutó sobre la base de demostración: lo decide el equipo.
7. **Usuarios administrativos:** no se crean aquí. Se usa `crear_usuario_administrativo` (ADR-013, punto 8), documentado en el README.

## Alternativas consideradas
- **Usar `generar_volumen_prueba` en la pila de demostración:** crea 100 maestros, 1.000 tickets y 5.000 mensajes sin cuentas con ingreso. Ensucia la demostración y su propósito es medir.
- **Contraseña fija conocida en el código o en `.env.example`:** se descartó. Viola la regla de no guardar secretos en el repositorio y es una credencial por defecto (R-03).
- **Pedir la contraseña por consola como `crear_usuario_administrativo`:** se descartó. Son tres cuentas de juguete, y la contraseña aleatoria impresa una vez es más simple y no la elige un humano.

## Consecuencias
- En la demostración se puede buscar (Concepción, Talcahuano, San Pedro, Chiguayante, Coronel, Santiago, Providencia, Ñuñoa…), pedir, aceptar, conversar, registrar precio y evaluar.
- Quien pierda la contraseña impresa la reemplaza con `--restablecer-contrasenas`.
- Con el tiempo, el ticket pendiente vence (planificador) y el aceptado pasa a pasado. Volver a ejecutar el comando no los recrea mientras el cliente 1 tenga tickets.
- Las pruebas que se corran contra la pila de demostración deben limpiar lo que crean, o correr en una pila aparte (`-p`). Es una lección del S3.
- Pruebas: `backend/tests/test_cuentas_demo.py`.

## Enmienda E-1 (2026-10-01) — Maestros por comuna y cuentas administrativas demo
Pedido del usuario el 2026-10-01: "mínimo 3 maestros por comuna, quiero un volumen de maestros de prueba para probar los filtros" (RF-09 a RF-12), y cuentas administrativas demo. El ADR sigue en **Borrador**.

1. **Opción explícita** `cargar_datos_demo --maestros-por-comuna [N] [--region R]` (N entre 1 y 10, por defecto 3; código en `busqueda/maestros_por_comuna.py`). Garantiza al menos N maestros de demostración **publicados** con comuna base en cada comuna (346 → unos 1.040 con N = 3). Idempotente: cuenta por comuna los maestros demo publicados que ya hay (RUT de 48.000.000 a 49.999.999, incluidos los 10 de `--con-cuentas`) y crea solo los que faltan. Sin la opción, el comando hace lo mismo que antes. Se puede combinar con `--con-cuentas`.
2. **Rotulado y resguardos:** "Maestro/Maestra Demo NNNN (datos de prueba)"; RUT sintético `48.000.000 + comuna·100 + puesto` (48.110.100 a 49.630.599: no choca con `--con-cuentas`, desde 49.990.001, ni con `generar_volumen_prueba`, desde 50.000.000); teléfono ficticio `+56 9 XXXX XXXX` con `comuna·100 + puesto` (0011 0100 a 0163 0599, fuera de los rangos 0000 a 0003 de las otras cargas); sin correo; contraseña **inutilizable**. El nombre no revela la comuna base (ADR-019, D-14).
3. **Variedad para probar filtros y orden (ADR-022):**
   - oficio principal que rota con la comuna y el puesto (distinto entre los maestros de una comuna) y, a veces, un segundo oficio; quedan combinaciones oficio + comuna sin maestro con base allí, a propósito, para ver las sugerencias;
   - cobertura: la comuna base y, a veces, 1 o 2 comunas de la misma provincia (cercanía 100 o 60);
   - agenda: mañana (09-13), tarde (14-18), jornada (08:30-17:30) o vespertino (17-21), en distintos grupos de días, a veces mañana unos días y tarde otros;
   - modalidad al azar entre las que admite el catálogo y monto entre 0,7 y 1,6 veces el precio de referencia;
   - un grupo fijo de 20 clientes ficticios sin ingreso (`cliente.volumen.demo.NN@example.com`): cerca de un tercio de los maestros tiene un ticket **aceptado** en los próximos días (bloque ocupado, CA-14.3) y algunos tienen 1 a 3 órdenes **finalizadas** en las últimas 4 semanas (precio coherente con ADR-026 E-1, historial en `ticket_evento`), la mayoría con la evaluación del cliente (desempate de RF-11). Solo se crean tickets para los maestros nuevos de cada ejecución.
4. **Oficios regulados:** gas y electricidad entran en la rotación. La licencia SEC se carga con el servicio real (`expediente.servicios.cargar_documento`: validación, recodificación y cifrado AES-256-GCM de ADR-015) a partir de una imagen sintética sin datos de nadie, vence en 2 años (no genera avisos, RF-35) y se marca `validado` directamente, sin revisor: igual que el expediente `aprobado` de estos maestros, nadie de curatoría la revisó y no se escribe bitácora (ADR-010). Así el servicio regulado es visible por la regla única (RNF-25). La regla vive en `busqueda/ficticios.py` (`crear_maestro_publicado(..., licencias=True)`); sin esa opción se siguen rechazando los oficios regulados.
5. **Foto:** cada maestro lleva su foto sintética propia (JPEG de un color, `perfil.fotos`), porque la foto es condición de publicación (ADR-019) y compartir un archivo entre perfiles haría que el cambio de foto de uno borrara la de otros. Cuesta unos 4 ms y 1,3 KB por maestro.
6. **Rendimiento de la carga:** cada maestro en su transacción (la regla atómica de `ficticios`); tickets, historial y evaluaciones con `bulk_create` en lotes. El costo dominante es el hash Argon2id de la contraseña aleatoria antes de inutilizarla (unos 0,13 s por cuenta, ADR-004): no se salta, para no abrir otra vía de alta de cuentas.
7. **Cuentas administrativas demo** (reemplaza el punto 7 de la Decisión): `--con-cuentas` crea una cuenta por rol administrativo existente (`ROLES_ADMINISTRATIVOS`: curatoría, comercial, moderación y control de gestión), `<rol>.demo@example.com` (`control.gestion.demo@example.com`), con `identidad.servicios.crear_cuenta_administrativa` y el evento de aplicación de `crear_usuario_administrativo`, sin duplicar su lógica. Reciben la misma contraseña aleatoria impresa una vez que las demás cuentas demo y `--restablecer-contrasenas` también las alcanza. `crear_usuario_administrativo` sigue siendo la vía para cuentas reales.
8. **Pruebas:** `backend/tests/test_maestros_por_comuna.py` (región 15, 4 comunas) y `test_cuentas_demo.py`.
