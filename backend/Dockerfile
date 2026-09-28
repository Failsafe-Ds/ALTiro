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

COPY . .
# Defensa ante fines de línea CRLF si el archivo se editó en Windows (ADR-009).
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod 0755 /app/entrypoint.sh

USER altiro
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
