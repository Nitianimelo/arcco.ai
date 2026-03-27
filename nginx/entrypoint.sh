#!/bin/sh
set -e

DOMAIN="app.arccoai.com"
SSL_DIR="/etc/nginx/ssl"
LE_CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
LE_KEY="/etc/letsencrypt/live/$DOMAIN/privkey.pem"

mkdir -p "$SSL_DIR"

# Se o certificado real (Let's Encrypt) ja existe, usa ele
if [ -f "$LE_CERT" ] && [ -f "$LE_KEY" ]; then
    echo "[entrypoint] Certificado Let's Encrypt encontrado — copiando para $SSL_DIR"
    cp "$LE_CERT" "$SSL_DIR/fullchain.pem"
    cp "$LE_KEY" "$SSL_DIR/privkey.pem"
    echo "[entrypoint] Iniciando Nginx com HTTPS (cert real)"
    exec nginx -g "daemon off;"
fi

# Certificado nao existe — gera self-signed temporario em /etc/nginx/ssl/
# (separado do /etc/letsencrypt/ para nao confundir o Certbot)
echo "[entrypoint] Certificado Let's Encrypt NAO encontrado — gerando self-signed temporario..."

openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$SSL_DIR/privkey.pem" \
    -out "$SSL_DIR/fullchain.pem" \
    -subj "/CN=$DOMAIN" \
    2>/dev/null

echo "[entrypoint] Self-signed gerado em $SSL_DIR"
echo "[entrypoint] Nginx vai subir nas portas 80 + 443"
echo "[entrypoint] Apos Certbot gerar o cert real, reinicie:"
echo "[entrypoint]   docker restart arccoai-nginx-1"

exec nginx -g "daemon off;"
