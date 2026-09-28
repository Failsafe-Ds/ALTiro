# ADR-015 — Documentos del maestro: almacenamiento, cifrado y validación

- Estado: **Aceptada** — 2026-09-28, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-28
- Relacionado con: RF-04, RNF-04, RNF-06, RNF-15, RNF-24, RNF-27, HU-11, HU-25, NTI-09, M-02, R-01, R-09, V-04
- Origen: propuesta del S2, decisiones D-3, D-4 y D-5.

## Contexto
- RNF-06: "Guardados fuera de las carpetas accesibles desde internet y entregados con un enlace que caduca a los 10 minutos".
- M-02 (§6.2): "Retención acotada, cifrado en reposo y acceso restringido a curatoría". §2.8: "cifrar documentos de identidad".
- RF-04: documentos "como fotografía".
- RNF-04: "No más de 2 GB de memoria para todo el sistema".

## Decisión
1. **Almacenamiento (D-3):**
   - Volumen `documentos`, montado **solo** en `app` y en `planificador`, nunca en `proxy`.
   - El servidor genera el nombre del archivo (UUID4); el nombre original no se guarda.
   - Permisos 0600 para el UID 10001.
   - Solo se entrega mediante una vista de Django que vuelve a aplicar la autorización. El enlace firmado de 600 s (`autorizacion/enlaces.py`) no reemplaza la política.
   - `FILE_UPLOAD_MAX_MEMORY_SIZE` es mayor o igual al máximo de subida, para que la foto no quede en claro en `/tmp`.
2. **Cifrado en reposo (D-4):**
   - AES-256-GCM por archivo con `cryptography`, con nonce aleatorio.
   - Datos asociados: `ref` del documento más la cara (anverso o reverso). Así no se pueden intercambiar archivos entre registros.
   - Clave de 32 bytes en `/secretos/documentos_clave`, generada por `init` (patrón `*_FILE`, ADR-009). La aplicación no arranca sin ella (RNF-24).
3. **Formatos y validación (D-5):**
   - Solo JPEG y PNG, detectados por el contenido y no por la extensión.
   - Pillow decodifica la imagen, limita los píxeles (`DecompressionBombError` responde 400) y **la recodifica a JPEG sin metadatos**. Así se elimina el EXIF con GPS (minimización, NTI-09) y se neutralizan los archivos políglotas.
   - Tamaño:
     - el cliente comprime la imagen (lado mayor de unos 2000 px);
     - el servidor acepta hasta **8 MB por archivo**;
     - en el proxy, `client_max_body_size` y `client_body_buffer_size` se fijan solo en la ruta de subida (1 MB en el resto);
     - si se supera, el 413 responde en JSON y en español.
   - Un documento ya vencido al cargarlo se rechaza con un mensaje que indica qué hacer (decisión del equipo).
   - No hay antivirus: ClamAV no cabe en el límite de RNF-04.
4. **Dependencias nuevas** con versión exacta y revisión de avisos de seguridad (RNF-27): `Pillow` y `cryptography`.

## Consecuencias
- Perder la clave es perder los documentos. La clave se respalda aparte de los datos (RNF-19, S5).
- Los archivos se conservan hasta RNF-26 y V-04 (S5). Por eso R-09 crece durante el S2.

## Pendiente
- **[VALIDA REPRESENTANTE]** Si se acepta PDF para el certificado de antecedentes (RF-04 dice "como fotografía").
- **[VALIDA REPRESENTANTE]** V-04 no cubre al postulante rechazado.
