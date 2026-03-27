#!/bin/sh
set -e

DOMAIN="app.arccoai.com"
SSL_DIR="/etc/nginx/ssl"
LE_CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
LE_KEY="/etc/letsencrypt/live/$DOMAIN/privkey.pem"

mkdir -p "$SSL_DIR"

# ── Funcao: copiar cert real do Let's Encrypt para /etc/nginx/ssl/ ──────────
copy_real_cert() {
    cp "$LE_CERT" "$SSL_DIR/fullchain.pem"
    cp "$LE_KEY" "$SSL_DIR/privkey.pem"
    echo "[entrypoint] Certificado Let's Encrypt copiado para $SSL_DIR"
}

# ── Se o cert real ja existe, usa direto ────────────────────────────────────
if [ -f "$LE_CERT" ] && [ -f "$LE_KEY" ]; then
    echo "[entrypoint] Certificado Let's Encrypt encontrado!"
    copy_real_cert
    echo "[entrypoint] Iniciando Nginx com HTTPS (cert real)"
    exec nginx -g "daemon off;"
fi

# ── Cert real nao existe — gera self-signed temporario ──────────────────────
echo "[entrypoint] Certificado Let's Encrypt NAO encontrado — gerando self-signed temporario..."

openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$SSL_DIR/privkey.pem" \
    -out "$SSL_DIR/fullchain.pem" \
    -subj "/CN=$DOMAIN" \
    2>/dev/null

echo "[entrypoint] Self-signed gerado. Iniciando Nginx + aguardando Certbot..."

# Inicia Nginx em background (porta 80 para ACME + 443 com self-signed)
nginx &
NGINX_PID=$!

# ── Aguarda Certbot gerar o cert real (polling a cada 2s, max 120s) ─────────
ATTEMPTS=0
MAX_ATTEMPTS=60

while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    if [ -f "$LE_CERT" ] && [ -f "$LE_KEY" ]; then
        echo "[entrypoint] Certbot gerou o certificado real!"
        copy_real_cert
        echo "[entrypoint] Recarregando Nginx com cert real..."
        nginx -s reload
        echo "[entrypoint] HTTPS ativo com certificado Let's Encrypt!"
        break
    fi
    ATTEMPTS=$((ATTEMPTS + 1))
    sleep 2
done

if [ $ATTEMPTS -eq $MAX_ATTEMPTS ]; then
    echo "[entrypoint] Certbot nao gerou cert em 120s — Nginx continua com self-signed"
    echo "[entrypoint] Rode 'docker restart arccoai-nginx-1' apos Certbot concluir"
fi

# Mantem o processo em foreground (PID 1)
wait $NGINX_PID
