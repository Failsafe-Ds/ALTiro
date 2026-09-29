# ADR-018 — Catálogo administrable de oficios, servicios y precios de referencia

- Estado: **Aceptada — PROVISIONAL** (2026-09-29). Se tomó la opción recomendada sin respuesta del equipo, según `docs/Reanudar.md`. Se revisa en la revisión del Sprint 3.
- Relacionado con: RF-36, RF-37, RF-05, RNF-11, RNF-25, HU-20, CA-20.1, CA-20.2, NTI-05, NTI-12, DA-15
- Origen: propuesta del S3, decisiones D-1 a D-4 y D-16.

## Decisión
1. **Modelo (D-1):**
   - Tablas `oficio`, `servicio` y `servicio_modalidad(servicio, modalidad, precio_referencia)`.
   - La modalidad pertenece a una lista **cerrada**: {`por_trabajo`, `por_hora`}. RF-05 fija solo esas dos, y RF-27 define una regla de aceptación del precio para cada una.
   - "Administrar la modalidad" significa decidir qué modalidades admite cada servicio y con qué precio de referencia. Todo servicio activo tiene al menos una modalidad.
2. **`regulado` (D-2):**
   - Es obligatorio al crear un oficio y no tiene valor por defecto.
   - Después es **inmutable** desde la aplicación: cambiarlo exige una migración y un ADR.
   - Motivo: pasar Gas o Electricidad a "no regulado" publicaría servicios sin licencia (RNF-25, seguridad operacional).
   - **[VALIDA REPRESENTANTE] P-12:** si comercial puede declarar un oficio como regulado.
3. **Carga inicial (D-3):**
   - El CSV de oficios (ADR-017) queda solo como carga inicial.
   - `catalogo.carga.cargar` pasa a **solo insertar** (`ON CONFLICT DO NOTHING`), para no pisar lo que haya cambiado comercial.
   - Una prueba verifica que ninguna migración posterior a `0003` recargue el CSV.
4. **Auditoría y concurrencia (D-4):**
   - Todo alta, modificación o baja registra una entrada en la bitácora (RF-37) en la misma transacción:
     - acciones `catalogo.oficio.crear`, `catalogo.oficio.modificar`, `catalogo.servicio.crear` y `catalogo.servicio.modificar`;
     - valores con solo los campos del catálogo.
   - Motivo obligatorio para modificar o dar de baja. Al crear se usa un motivo fijo que se puede completar.
   - Campo `version`: si no coincide, 409.
   - Sin borrado físico: las bajas se hacen con `activo=false`.
5. **Caché (D-16):** `GET /api/oficios` y `GET /api/catalogo` usan `Cache-Control: no-cache` con ETag. El `max-age=3600` anterior incumpliría CA-20.2 ("ve el valor actualizado").
6. **Autorización:** las rutas `/api/comercial/` usan `@requiere_rol("comercial")`. Las lecturas públicas no llevan datos personales. No hay conflicto de interés definido en el informe para el catálogo, así que no se inventa uno (ADR-013, punto 2.5).
