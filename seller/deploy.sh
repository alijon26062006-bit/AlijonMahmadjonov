#!/usr/bin/env bash
# Установка и обновление кабинета продавца на сервере Ubuntu/Debian.
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/seller-app/seller/deploy.sh | sudo bash -s -- seller.example.tj
#
# Аргумент — домен (необязательно). С доменом сайт получает HTTPS-сертификат Let's Encrypt,
# без домена открывается по IP-адресу сервера. Повторный запуск обновляет сайт за несколько секунд.
set -euo pipefail

DOMAIN="${1:-}"
REPO="https://github.com/alijon26062006-bit/AlijonMahmadjonov.git"
BRANCH="seller-app"
APP_DIR="/opt/seller-panel"
WEB_ROOT="$APP_DIR/seller"
APT_WAIT=600   # сколько секунд ждать, пока Ubuntu закончит свои обновления

log()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }
die()  { printf '\n\033[1;31mОшибка: %s\033[0m\n' "$*" >&2; exit 1; }
STARTED=$(date +%s)

[ "$(id -u)" -eq 0 ] || die "запустите с sudo"
command -v apt-get >/dev/null || die "скрипт рассчитан на Ubuntu или Debian"

# ставим пакеты только если их нет; если установщик занят обновлениями Ubuntu — говорим об этом и ждём
apt_install() {
  local missing=()
  for pkg in "$@"; do dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg"); done
  [ ${#missing[@]} -eq 0 ] && { note "уже установлено: $*"; return; }
  if fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; then
    note "Ubuntu сейчас ставит свои обновления, ждём (до $((APT_WAIT / 60)) минут)…"
  fi
  export DEBIAN_FRONTEND=noninteractive
  local apt=(apt-get -o DPkg::Lock::Timeout=$APT_WAIT -o Acquire::Retries=3)
  if [ -z "$(find /var/lib/apt/lists -maxdepth 1 -name '*Packages*' -mmin -720 2>/dev/null | head -1)" ]; then
    note "обновляю список пакетов…"
    "${apt[@]}" update -qq
  fi
  note "устанавливаю: ${missing[*]}"
  "${apt[@]}" install -y -qq --no-install-recommends "${missing[@]}" >/dev/null
}

log "Проверяю nginx и git"
apt_install nginx git ca-certificates

log "Скачиваю кабинет продавца, приложения покупателя и курьера"
# только папки seller/, client/ и courier/, без остального репозитория; прерванный запуск ничего не ломает
rm -rf "$APP_DIR.new"
git clone -q --depth 1 --filter=blob:none --sparse --branch "$BRANCH" "$REPO" "$APP_DIR.new"
git -C "$APP_DIR.new" sparse-checkout set seller client courier
# приложение покупателя открывается по адресу /app/ того же сайта
cp -a "$APP_DIR.new/client" "$APP_DIR.new/seller/app"
# приложение курьера — по адресу /courier/
cp -a "$APP_DIR.new/courier" "$APP_DIR.new/seller/courier"
rm -rf "$APP_DIR.old"
[ -d "$APP_DIR" ] && mv "$APP_DIR" "$APP_DIR.old"
mv "$APP_DIR.new" "$APP_DIR"
rm -rf "$APP_DIR.old"
chmod -R a+rX "$WEB_ROOT"
note "версия: $(git -C "$APP_DIR" log -1 --format='%h, %cd' --date=format:'%d.%m.%Y %H:%M')"

log "Настраиваю nginx"
CONF=/etc/nginx/sites-available/seller-panel
# конфиг пишем один раз: после certbot в нём настройки HTTPS, их не трогаем
if [ ! -f "$CONF" ] || ! grep -q "server_name ${DOMAIN:-_};" "$CONF"; then
  LISTEN6=""
  [ -f /proc/net/if_inet6 ] && LISTEN6="listen [::]:80;"
  cat > "$CONF" <<NGINX
server {
    listen 80;
    $LISTEN6
    server_name ${DOMAIN:-_};
    root $WEB_ROOT;
    index index.html;

    # наружу отдаём только сам кабинет
    location ~ ^/(supabase|README\.md|package\.json|deploy\.sh|uninstall\.sh) { return 404; }
    location / { try_files \$uri \$uri/ =404; }

    # код браузер сверяет с сервером при каждом открытии: после обновления у всех сразу новая версия
    location ~* \.(css|js)$ { expires -1; add_header Cache-Control "no-cache"; }
    location ~* \.(svg|png|jpg|webp|woff2)$ {
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
fi
# сервер, настроенный раньше: код кэшировался на час — теперь сверяется каждый раз (остальное в конфиге не трогаем)
perl -0pi -e 's/location ~\* \\\.\(css\|js\|svg\|png\|jpg\|webp\|woff2\)\$ \{/location ~* \\.(css|js)\$ { expires -1; add_header Cache-Control "no-cache"; }\n    location ~* \\.(svg|png|jpg|webp|woff2)\$ {/' "$CONF"
ln -sf "$CONF" /etc/nginx/sites-enabled/seller-panel
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

URL="http://${DOMAIN:-$(curl -fsS -4 --max-time 5 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')}"
if [ -n "$DOMAIN" ]; then
  if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    note "HTTPS-сертификат уже есть"
    URL="https://$DOMAIN"
  else
    log "Получаю HTTPS-сертификат для $DOMAIN"
    apt_install certbot python3-certbot-nginx
    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect -q; then
      URL="https://$DOMAIN"
    else
      SERVER_IP=$(curl -fsS -4 --max-time 5 https://ifconfig.me 2>/dev/null || echo "IP этого сервера")
      note "Сертификат не получен. На duckdns.org укажите для $DOMAIN адрес $SERVER_IP и запустите команду ещё раз."
    fi
  fi
fi

log "Готово за $(( $(date +%s) - STARTED )) с"
note "кабинет продавца:     $URL"
note "приложение покупателя: ${URL%/}/app/"
note "приложение курьера:   ${URL%/}/courier/"
