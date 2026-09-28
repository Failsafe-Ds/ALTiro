#!/bin/sh
# Genera, solo si no existen, los secretos y el certificado TLS autofirmado
# de la demostración local (ADR-008, ADR-009). Es idempotente.
# Nunca imprime el valor de un secreto.
set -eu

SECRETOS_DIR=/secretos
CERT_DIR=/certificados

# UID del usuario de la aplicación (backend/Dockerfile) y GID del grupo
# "postgres" de la imagen oficial postgres:*-bookworm.
APP_UID=10001
PG_GID=999

SAN="${ALTIRO_TLS_SAN:-DNS:localhost,IP:127.0.0.1}"
NOMBRE_CERT="AlTiro demo local, autofirmado"

umask 077
mkdir -p "$SECRETOS_DIR" "$CERT_DIR"
chmod 0755 "$SECRETOS_DIR" "$CERT_DIR"

# generar_secreto <archivo> <dueño> <modo>
generar_secreto() {
    archivo="$1"
    dueno="$2"
    modo="$3"
    if [ -s "$archivo" ]; then
        echo "Secreto $(basename "$archivo"): ya existe, se conserva."
    else
        openssl rand -hex 32 | tr -d '\n' > "$archivo.tmp"
        mv "$archivo.tmp" "$archivo"
        echo "Secreto $(basename "$archivo"): generado."
    fi
    chown "$dueno" "$archivo"
    chmod "$modo" "$archivo"
}

# Contraseña del rol administrativo de PostgreSQL (POSTGRES_USER): solo la lee
# el contenedor de la base (root y grupo postgres). La app no puede leerla.
generar_secreto "$SECRETOS_DIR/db_admin_password" "0:$PG_GID" 0440
# Contraseña del rol de la aplicación: la leen la app (dueño) y el script de
# inicialización de la base (grupo postgres).
generar_secreto "$SECRETOS_DIR/db_app_password" "$APP_UID:$PG_GID" 0440
# Clave de Django: solo la app.
generar_secreto "$SECRETOS_DIR/django_secret_key" "$APP_UID:$APP_UID" 0400
# Clave de cifrado de los documentos del maestro (ADR-015, D-4): 32 bytes
# aleatorios escritos en hexadecimal (64 caracteres), solo para la app (y el
# planificador, que corre con el mismo UID). Nunca se regenera si ya existe:
# perderla o cambiarla deja ilegibles los documentos guardados. Se respalda
# aparte de los datos (RNF-19).
generar_secreto "$SECRETOS_DIR/documentos_clave" "$APP_UID:$APP_UID" 0400

# Certificado: se regenera si falta, si cambió el SAN o si vence en menos de un día.
regenerar=0
if [ ! -s "$CERT_DIR/cert.pem" ] || [ ! -s "$CERT_DIR/key.pem" ]; then
    regenerar=1
elif [ "$(cat "$CERT_DIR/san.txt" 2>/dev/null || true)" != "$SAN" ]; then
    echo "Certificado: el SAN configurado cambió, se regenera."
    regenerar=1
elif ! openssl x509 -checkend 86400 -noout -in "$CERT_DIR/cert.pem" >/dev/null 2>&1; then
    echo "Certificado: vencido o por vencer, se regenera."
    regenerar=1
fi

if [ "$regenerar" -eq 1 ]; then
    openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 365 \
        -keyout "$CERT_DIR/key.pem.tmp" \
        -out "$CERT_DIR/cert.pem.tmp" \
        -subj "/O=$NOMBRE_CERT/CN=$NOMBRE_CERT" \
        -addext "subjectAltName=$SAN" \
        -addext "basicConstraints=critical,CA:FALSE" \
        -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
        -addext "extendedKeyUsage=serverAuth" \
        || { echo "Certificado: no se pudo generar. Revise ALTIRO_TLS_SAN (ejemplo: DNS:localhost,IP:127.0.0.1)." >&2; exit 1; }
    mv "$CERT_DIR/key.pem.tmp" "$CERT_DIR/key.pem"
    mv "$CERT_DIR/cert.pem.tmp" "$CERT_DIR/cert.pem"
    printf '%s' "$SAN" > "$CERT_DIR/san.txt"
    echo "Certificado: generado ($NOMBRE_CERT; SAN: $SAN)."
else
    echo "Certificado: ya existe y es válido, se conserva."
fi

# La clave privada la lee el proceso maestro de Nginx (root).
chown 0:0 "$CERT_DIR/key.pem" "$CERT_DIR/cert.pem" "$CERT_DIR/san.txt"
chmod 0400 "$CERT_DIR/key.pem"
chmod 0444 "$CERT_DIR/cert.pem" "$CERT_DIR/san.txt"

echo "Inicialización completa."
