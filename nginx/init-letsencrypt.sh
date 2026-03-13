#!/bin/bash
# ============================================================
# Script de inicialização do SSL com Let's Encrypt
# Executar UMA VEZ na VPS para gerar certificados iniciais.
#
# Uso:
#   chmod +x nginx/init-letsencrypt.sh
#   ./nginx/init-letsencrypt.sh
# ============================================================

# ── CONFIGURAÇÃO (editar antes de rodar) ──────────────
DOMAIN="your-domain.com"          # <-- TROCAR pelo seu domínio
EMAIL="your-email@example.com"    # <-- TROCAR pelo seu email
STAGING=1                          # 1 para teste, 0 para produção

# ── Script ─────────────────────────────────────────────
set -e

data_path="./certbot"
rsa_key_size=4096

if [ -d "$data_path/conf/live/$DOMAIN" ]; then
    echo "Certificados já existem para $DOMAIN."
    echo "Para renovar, delete $data_path/conf/live/$DOMAIN e rode novamente."
    exit 0
fi

echo "### Criando diretórios..."
mkdir -p "$data_path/conf" "$data_path/www"

echo "### Baixando parâmetros TLS recomendados..."
if [ ! -e "$data_path/conf/options-ssl-nginx.conf" ] || [ ! -e "$data_path/conf/ssl-dhparams.pem" ]; then
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$data_path/conf/options-ssl-nginx.conf"
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$data_path/conf/ssl-dhparams.pem"
fi

echo "### Criando certificado dummy para Nginx iniciar..."
mkdir -p "$data_path/conf/live/$DOMAIN"
openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 1 \
    -keyout "$data_path/conf/live/$DOMAIN/privkey.pem" \
    -out "$data_path/conf/live/$DOMAIN/fullchain.pem" \
    -subj "/CN=localhost"

echo "### Iniciando Nginx..."
docker compose up -d nginx

echo "### Removendo certificado dummy..."
rm -rf "$data_path/conf/live/$DOMAIN"

echo "### Solicitando certificado Let's Encrypt..."

staging_arg=""
if [ $STAGING != "0" ]; then
    staging_arg="--staging"
fi

docker compose run --rm certbot certonly --webroot \
    -w /var/www/certbot \
    $staging_arg \
    --email $EMAIL \
    -d $DOMAIN \
    --rsa-key-size $rsa_key_size \
    --agree-tos \
    --force-renewal \
    --no-eff-email

echo "### Reiniciando Nginx com certificado real..."
docker compose exec nginx nginx -s reload

echo ""
echo "============================================================"
echo "✅ SSL configurado com sucesso para: $DOMAIN"
echo ""
echo "Próximos passos:"
echo "1. Edite nginx/nginx.conf:"
echo "   - Descomentar o bloco HTTPS (server 443)"
echo "   - Descomentar o redirect HTTP→HTTPS"
echo "   - Trocar 'your-domain.com' pelo seu domínio"
echo "2. Rode: docker compose up -d --build nginx"
echo ""
if [ $STAGING != "0" ]; then
    echo "⚠️  ATENÇÃO: Certificado de STAGING (teste)."
    echo "   Para produção, altere STAGING=0 e rode novamente."
fi
echo "============================================================"
