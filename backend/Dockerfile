FROM python:3.13.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Usuario sin privilegios. El UID 10001 coincide con infra/init/generar.sh,
# que asigna la propiedad de los archivos de secretos.
RUN groupadd --system --gid 10001 altiro \
    && useradd --system --uid 10001 --gid altiro --no-create-home \
       --home-dir /nonexistent --shell /usr/sbin/nologin altiro

COPY requirements.txt requirements-pruebas.txt ./
# Las dependencias de pruebas se instalan para poder ejecutar pytest dentro
# del contenedor (ADR-014).
RUN pip install -r requirements.txt -r requirements-pruebas.txt && pip check

# Punto de montaje del volumen "documentos" (ADR-015, D-3). Docker copia el
# dueño y los permisos de este directorio de la imagen al volumen con nombre
# la primera vez que lo monta vacío: así el volumen queda de 10001:10001 y 0700
# sin montarlo en "init" (solo lo montan app y, desde el incremento 5, el
# planificador). Un volumen creado antes con otro dueño no se corrige solo.
RUN mkdir /documentos && chown altiro:altiro /documentos && chmod 0700 /documentos

# Punto de montaje del volumen "fotos" (ADR-021, punto 3), mismo patrón: solo
# lo monta app.
RUN mkdir /fotos && chown altiro:altiro /fotos && chmod 0700 /fotos

# Punto de montaje del volumen "buzon" (ADR-027, punto 4), mismo patrón: solo
# lo monta app.
RUN mkdir /buzon && chown altiro:altiro /buzon && chmod 0700 /buzon

COPY . .
# Defensa ante fines de línea CRLF si el archivo se editó en Windows (ADR-009).
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod 0755 /app/entrypoint.sh

USER altiro
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
