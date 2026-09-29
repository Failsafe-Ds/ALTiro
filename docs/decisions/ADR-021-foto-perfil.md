# ADR-021 — Foto de perfil del maestro

- Estado: **Aceptada — PROVISIONAL** (2026-09-29). Se tomó la opción recomendada sin respuesta del equipo, según `docs/Reanudar.md`. Se revisa en la revisión del Sprint 3.
- Relacionado con: RF-13 (dato "fotografía"), RF-14 (parcial), RNF-02, RNF-04, RNF-24, NTI-09; ADR-015
- Origen: propuesta del S3, decisión D-13.

## Decisión
1. **Obligatoria para publicarse:**
   - La foto se captura en S3 y es requisito para que el maestro sea elegible (ADR-019).
   - RF-13 exige "fotografía" en cada tarjeta de resultado, y S4 ya es el sprint más cargado.
   - **[VALIDA REPRESENTANTE] P-14:** si la foto es obligatoria.
2. **Procesamiento:**
   - Se detecta el tipo por el contenido, se limitan los píxeles y el peso, y se recodifica a JPEG sin EXIF ni GPS con Pillow (mismo patrón que ADR-015).
   - Se guardan dos variantes, de 160 px y de 480 px, para no incumplir el límite de 1,5 MB de RNF-02 en S4.
3. **Almacenamiento:**
   - Volumen `fotos`, montado solo en `app`, con nombre UUID.
   - **No se cifra**, porque su finalidad es ser pública.
   - Se entrega por una vista que solo responde si el maestro está publicado (ADR-019). Si no, responde el mismo 404 neutro.
4. **Límite en el proxy:** la ruta de subida de la foto tiene su propia `location` con límite de tamaño (patrón de ADR-015).
5. **Riesgo abierto:** no hay moderación de fotos definida (foto inapropiada). Es una pregunta para el representante.
