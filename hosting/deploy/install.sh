#!/usr/bin/env bash
# Установка панели хостинга на чистый сервер Ubuntu 22.04 / 24.04.
#
#   sudo bash deploy/install.sh
#
# Что делает:
#   1) ставит Python, nginx и certbot;
#   2) копирует панель в /opt/amcloud и ставит зависимости;
#   3) спрашивает домен и ключи и создаёт /opt/amcloud/.env (существующий .env не трогает);
#   4) включает автозапуск (systemd), nginx и бесплатный HTTPS (Let's Encrypt);
#   5) включает ежедневную резервную копию базы.
# Повторный запуск безопасен: обновляет код и перезапускает панель.
set -euo pipefail

APP_DIR=/opt/amcloud
APP_USER=amcloud
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

say() { printf '\n\033[1;34m▶ %s\033[0m\n' "$*"; }
ask() { local var="$1" prompt="$2" def="${3:-}" val; read -r -p "$prompt${def:+ [$def]}: " val; printf -v "$var" '%s' "${val:-$def}"; }
ask_secret() { local var="$1" prompt="$2" val; read -r -s -p "$prompt (ввод скрыт, Enter — пропустить): " val; echo; printf -v "$var" '%s' "$val"; }

if [[ $EUID -ne 0 ]]; then echo "Запустите с sudo: sudo bash deploy/install.sh"; exit 1; fi
if [[ ! -f "$SRC_DIR/run.py" ]]; then echo "Запускайте из папки hosting (рядом должен быть run.py)"; exit 1; fi

say "1/5 Ставлю системные пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx certbot python3-certbot-nginx sqlite3 rsync >/dev/null

say "2/5 Копирую панель в $APP_DIR"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"
rsync -a --exclude '.env' --exclude 'data/' --exclude '__pycache__' --exclude '.venv' --exclude 'tests/' --exclude 'prototype/' \
  "$SRC_DIR/" "$APP_DIR/"
mkdir -p "$APP_DIR/data" "$APP_DIR/backups"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  say "3/5 Настройка (потом можно поменять в $APP_DIR/.env)"
  ask DOMAIN "Домен панели, например my.example.com"
  ask ADMIN "Ваш email (станет администратором)"
  ask BRAND "Название хостинга" "AM Cloud"
  ask_secret HETZNER "Токен Hetzner Cloud (Read & Write)"
  ask RC_USER "ResellerClub: Reseller ID (Enter — домены в демо-режиме)"
  RC_KEY=""; RC_CUST=""
  if [[ -n "$RC_USER" ]]; then
    ask_secret RC_KEY "ResellerClub: API key"
    ask RC_CUST "ResellerClub: Customer ID, на которого регистрировать домены"
  fi
  ask METHODS "Способы оплаты через запятую" "Алиф Моби,Душанбе Сити"
  ask INSTR "Реквизиты для перевода (одной строкой)" "Переведите сумму на карту 0000 0000 0000 0000 и укажите ваш email в комментарии"
  ask TG "Telegram поддержки без @ (Enter — пропустить)"
  ask COMPANY "Название ИП/компании для документов"
  SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
  VPS=demo; DNS=demo; REG=demo
  [[ -n "$HETZNER" ]] && VPS=hetzner && DNS=hetzner
  [[ -n "$RC_USER" ]] && REG=resellerclub
  umask 077
  cat > "$APP_DIR/.env" <<ENV
BRAND_NAME=$BRAND
SECRET_KEY=$SECRET
DATABASE_PATH=data/hosting.db
CURRENCY=USD
ADMIN_EMAIL=$ADMIN
COOKIE_SECURE=true
PUBLIC_URL=https://$DOMAIN
DEMO_PAYMENTS=false
GRACE_DAYS=3
NEW_USER_SERVER_LIMIT=1

VPS_PROVIDER=$VPS
DNS_PROVIDER=$DNS
HETZNER_TOKEN=$HETZNER

REGISTRAR=$REG
RESELLERCLUB_USER_ID=$RC_USER
RESELLERCLUB_API_KEY=$RC_KEY
RESELLERCLUB_CUSTOMER_ID=$RC_CUST
RESELLERCLUB_TEST=true

PAYMENT_METHODS=$METHODS
PAYMENT_INSTRUCTIONS=$INSTR

TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=

COMPANY_NAME=$COMPANY
COMPANY_DETAILS=
SUPPORT_TELEGRAM=$TG
SUPPORT_EMAIL=$ADMIN
SUPPORT_PHONE=
ENV
  umask 022
else
  say "3/5 Файл $APP_DIR/.env уже есть — оставляю как есть"
  DOMAIN=$(grep -E '^PUBLIC_URL=' "$APP_DIR/.env" | sed -E 's#^PUBLIC_URL=https?://##; s#/.*##')
  ADMIN=$(grep -E '^ADMIN_EMAIL=' "$APP_DIR/.env" | cut -d= -f2-)
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

say "4/5 Автозапуск, nginx и HTTPS"
cat > /etc/systemd/system/amcloud.service <<UNIT
[Unit]
Description=AM Cloud hosting panel
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/uvicorn run:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=$APP_DIR/data $APP_DIR/backups

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now amcloud.service
systemctl restart amcloud.service

cat > /etc/nginx/sites-available/amcloud <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 1m;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/amcloud /etc/nginx/sites-enabled/amcloud
[[ -e /etc/nginx/sites-enabled/default ]] && unlink /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
if command -v ufw >/dev/null && ufw status | grep -q active; then ufw allow 'Nginx Full' >/dev/null; fi
if ! certbot certificates 2>/dev/null | grep -q "Domains: $DOMAIN"; then
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$ADMIN" --redirect || \
    echo "⚠ HTTPS не выпущен. Проверьте, что DNS-запись A для $DOMAIN указывает на IP этого сервера, и запустите: certbot --nginx -d $DOMAIN"
fi

say "5/5 Ежедневная резервная копия базы (хранится 14 дней)"
cat > /etc/cron.daily/amcloud-backup <<CRON
#!/bin/sh
sqlite3 $APP_DIR/data/hosting.db ".backup '$APP_DIR/backups/hosting-\$(date +%F).db'"
find $APP_DIR/backups -name 'hosting-*.db' -mtime +14 -delete
CRON
chmod +x /etc/cron.daily/amcloud-backup

sleep 2
if systemctl is-active --quiet amcloud.service; then
  echo
  echo "✅ Готово: https://$DOMAIN"
  echo "   1) Зарегистрируйтесь на сайте с email $ADMIN — вы станете администратором."
  echo "   2) Откройте Админку → «Готовность» и доведите все пункты до зелёного."
  echo "   3) Настройки: $APP_DIR/.env, после правки: systemctl restart amcloud"
  echo "   Логи: journalctl -u amcloud -f"
else
  echo "⚠ Панель не запустилась. Смотрите: journalctl -u amcloud -n 50"
  exit 1
fi
