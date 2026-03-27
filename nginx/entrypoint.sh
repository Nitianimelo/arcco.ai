#!/bin/sh
set -e

DOMAIN="app.arccoai.com"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
CERT_FILE="$CERT_DIR/fullchain.pem"
KEY_FILE="$CERT_DIR/privkey.pem"

# Se o certificado real (Let's Encrypt) ja existe, usa ele direto
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo "[entrypoint] Certificado SSL encontrado em $CERT_DIR — iniciando Nginx com HTTPS"
    exec nginx -g "daemon off;"
fi

# Certificado nao existe ainda — gera self-signed temporario
# para o Nginx subir e o Certbot poder validar via porta 80
echo "[entrypoint] Certificado SSL NAO encontrado — gerando self-signed temporario..."

mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/CN=$DOMAIN" \
    2>/dev/null

echo "[entrypoint] Self-signed gerado. Nginx vai subir nas portas 80 + 443."
echo "[entrypoint] Apos Certbot gerar o cert real, reinicie o container nginx:"
echo "[entrypoint]   docker restart arccoai-nginx-1"

exec nginx -g "daemon off;"
