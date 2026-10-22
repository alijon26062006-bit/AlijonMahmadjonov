#!/usr/bin/env bash
# Установка и обновление кабинета продавца на сервере Ubuntu/Debian.
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/seller-app/seller/deploy.sh | sudo bash -s -- seller.example.tj
#
# Аргумент — домен (необязательно). С доменом сайт получает HTTPS-сертификат Let's Encrypt,
# без домена открывается по IP-адресу сервера. Повторный запуск обновляет сайт до последней версии.
set -euo pipefail

DOMAIN="${1:-}"
REPO="https://github.com/alijon26062006-bit/AlijonMahmadjonov.git"
BRANCH="seller-app"
APP_DIR="/opt/seller-panel"
WEB_ROOT="$APP_DIR/seller"

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mОшибка: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "запустите с sudo"
command -v apt-get >/dev/null || die "скрипт рассчитан на Ubuntu или Debian"

log "Устанавливаю nginx и git"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx git >/dev/null

log "Скачиваю кабинет продавца"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch -q --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" reset -q --hard "origin/$BRANCH"
else
  rm -rf "$APP_DIR"
  git clone -q --depth 1 --branch "$BRANCH" "$REPO" "$APP_DIR"
fi
chmod -R a+rX "$WEB_ROOT"

log "Настраиваю nginx"
# IPv6 включаем, только если он есть на сервере
LISTEN6=""
[ -f /proc/net/if_inet6 ] && LISTEN6="listen [::]:80;"
cat > /etc/nginx/sites-available/seller-panel <<NGINX
server {
    listen 80;
    $LISTEN6
    server_name ${DOMAIN:-_};
    root $WEB_ROOT;
    index index.html;

    # наружу отдаём только сам кабинет
    location ~ ^/(supabase|README\.md|package\.json|deploy\.sh) { return 404; }
    location / { try_files \$uri \$uri/ =404; }

    location ~* \.(css|js|svg|png|jpg|webp|woff2)$ {
        expires 1h;
        add_header Cache-Control "public";
    }

    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    gzip on;
    gzip_types text/css application/javascript image/svg+xml;
}
NGINX
ln -sf /etc/nginx/sites-available/seller-panel /etc/nginx/sites-enabled/seller-panel
rm -f /etc/nginx/sites-enabled/default
nginx -t -q
if [ -d /run/systemd/system ]; then
  systemctl enable -q --now nginx
  systemctl reload nginx
else
  nginx -s reload 2>/dev/null || nginx   # контейнер без systemd
fi

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 'Nginx Full' >/dev/null
fi

if [ -n "$DOMAIN" ]; then
  log "Получаю HTTPS-сертификат для $DOMAIN"
  apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
  if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect; then
    URL="https://$DOMAIN"
  else
    URL="http://$DOMAIN"
    printf '\nСертификат не получен. Проверьте, что домен %s указывает на IP этого сервера, и запустите команду ещё раз.\n' "$DOMAIN"
  fi
else
  URL="http://$(curl -fsS -4 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
fi

log "Готово: $URL"
