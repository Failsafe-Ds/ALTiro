FROM alpine:3.24.2

RUN apk add --no-cache openssl

COPY generar.sh /usr/local/bin/generar.sh
# Defensa ante fines de línea CRLF si el archivo se editó en Windows (ADR-009).
RUN sed -i 's/\r$//' /usr/local/bin/generar.sh && chmod 0755 /usr/local/bin/generar.sh

ENTRYPOINT ["/usr/local/bin/generar.sh"]
