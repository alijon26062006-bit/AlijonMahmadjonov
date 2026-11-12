#!/usr/bin/env bash
# Установка панели хостинга на чистый сервер Ubuntu 22.04 / 24.04.
#
#   sudo bash deploy/install.sh
#
# Что делает:
#   1) ставит Python, nginx и certbot;
#   2) копирует панель в /opt/averix и ставит зависимости;
#   3) спрашивает домен и ключи и создаёт /opt/averix/.env (существующий .env не трогает);
#   4) включает автозапуск (systemd), nginx и бесплатный HTTPS (Let's Encrypt);
#   5) включает ежедневную резервную копию базы.
# Повторный запуск безопасен: обновляет код и перезапускает панель.
set -euo pipefail

# Домен и название вшиты; при необходимости их можно задать заранее: AVERIX_DOMAIN=... AVERIX_BRAND=...
DOMAIN="${AVERIX_DOMAIN:-averix.dev}"
BRAND="${AVERIX_BRAND:-Averix}"
APP_DIR=/opt/averix
APP_USER=averix
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

say() { printf '\n\033[1;34m▶ %s\033[0m\n' "$*"; }
# Вопросы читаются с клавиатуры (/dev/tty) — так установщик работает и при запуске через «curl | bash».
ask() { local var="$1" prompt="$2" def="${3:-}" val; read -r -p "$prompt${def:+ [$def]}: " val </dev/tty; printf -v "$var" '%s' "${val:-$def}"; }
ask_secret() { local var="$1" prompt="$2" val; read -r -s -p "$prompt (ввод скрыт): " val </dev/tty; echo; printf -v "$var" '%s' "$val"; }
ask_required() { local var="$1" prompt="$2" val=""; while [[ -z "$val" ]]; do read -r -p "$prompt: " val </dev/tty; done; printf -v "$var" '%s' "$val"; }

is_ip() { [[ "$1" =~ ^[0-9]+(\.[0-9]+){3}$ || "$1" == *:* ]]; }
ask_domain() {
  while true; do
    ask_required DOMAIN "Домен сайта, например averix.dev (не IP-адрес; A-запись домена должна указывать на IP этого сервера)"
    DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"; DOMAIN="${DOMAIN,,}"
    if is_ip "$DOMAIN"; then echo "  ❌ Это IP-адрес. Нужен домен, например averix.dev"; continue; fi
    if [[ "$DOMAIN" != *.* ]]; then echo "  ❌ Похоже, это не домен. Пример: averix.dev"; continue; fi
    break
  done
}

if [[ $EUID -ne 0 ]]; then echo "Запустите от root: sudo bash deploy/install.sh"; exit 1; fi
if [[ ! -f "$SRC_DIR/run.py" ]]; then echo "Не найден код панели рядом со скриптом (run.py)"; exit 1; fi
if ! : </dev/tty 2>/dev/null; then echo "Нужен интерактивный терминал: запустите команду в SSH-сессии"; exit 1; fi

say "1/5 Ставлю системные пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx certbot python3-certbot-nginx sqlite3 rsync curl >/dev/null

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
  say "3/5 Ключи (всё остальное — реквизиты, оплата, контакты — настраивается на сайте: Админка → Настройки)"
  echo "Токен Hetzner: console.hetzner.com → ваш проект → Security → API tokens → Generate (Read & Write)."
  HETZNER=""
  for attempt in 1 2 3; do
    ask_secret HETZNER "Вставьте токен Hetzner"
    if [[ -z "$HETZNER" ]]; then echo "  Пусто — серверы будут в демо-режиме (без настоящих заказов)."; break; fi
    CODE=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $HETZNER" https://api.hetzner.cloud/v1/locations || true)
    if [[ "$CODE" == "200" ]]; then
      # Пустой запрос на создание ничего не создаёт: read-only токен получит 403, нормальный — 422.
      WCODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $HETZNER" \
        -H "Content-Type: application/json" -d '{}' https://api.hetzner.cloud/v1/servers || true)
      if [[ "$WCODE" == "403" ]]; then
        echo "  ❌ У токена только право на чтение. Создайте новый токен с правами Read & Write."
        HETZNER=""; continue
      fi
      echo "  ✅ Токен работает"; break
    fi
    echo "  ❌ Hetzner не принял токен (ответ $CODE). Проверьте, что скопировали его целиком."
    HETZNER=""
  done
  echo
  echo "Ключи ResellerClub (домены): manage.resellerclub.com → Settings → API. Enter — пропустить, добавите позже."
  ask RC_USER "ResellerClub: Reseller ID"
  RC_KEY=""; RC_CUST=""
  if [[ -n "$RC_USER" ]]; then
    ask_secret RC_KEY "ResellerClub: API key"
    ask_required RC_CUST "ResellerClub: Customer ID (Customers → ваш клиент)"
  fi
  echo
  ask_required ADMIN "Email администратора"
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

# Способы оплаты, реквизиты, контакты, Telegram и почта задаются на сайте: Админка → Настройки
PAYMENT_METHODS=
PAYMENT_INSTRUCTIONS=

TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=

COMPANY_NAME=
COMPANY_DETAILS=
SUPPORT_TELEGRAM=
SUPPORT_EMAIL=$ADMIN
SUPPORT_PHONE=
ENV
  umask 022
else
  say "3/5 Файл $APP_DIR/.env уже есть — оставляю как есть"
  DOMAIN=$(grep -E '^PUBLIC_URL=' "$APP_DIR/.env" | sed -E 's#^PUBLIC_URL=https?://##; s#/.*##')
  ADMIN=$(grep -E '^ADMIN_EMAIL=' "$APP_DIR/.env" | cut -d= -f2-)
fi

# ── Адрес сайта ──
# Основной домен (averix.dev). Если его DNS ещё не указывает на этот сервер,
# сайт временно работает на бесплатном адресе вида 1-2-3-4.sslip.io (с настоящим HTTPS).
# Когда домен заработает, повторный запуск этой же команды сам переключит сайт на него.
set_env() { if grep -qE "^$1=" "$APP_DIR/.env"; then sed -i -E "s#^$1=.*#$1=$2#" "$APP_DIR/.env"; else echo "$1=$2" >> "$APP_DIR/.env"; fi; }
points_here() { local ip; for ip in $(getent ahostsv4 "$1" | awk '{print $1}' | sort -u); do [[ "$ip" == "$MY_IP" ]] && return 0; done; return 1; }
MY_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") print $(i + 1)}')
[[ -z "$MY_IP" ]] && MY_IP=$(hostname -I | awk '{print $1}')
MAIN_DOMAIN="${AVERIX_DOMAIN:-$(grep -E '^MAIN_DOMAIN=' "$APP_DIR/.env" | cut -d= -f2- || true)}"
if [[ -z "$MAIN_DOMAIN" ]] || is_ip "$MAIN_DOMAIN"; then MAIN_DOMAIN=averix.dev; fi
TEMP_DOMAIN="${MY_IP//./-}.sslip.io"
if points_here "$MAIN_DOMAIN"; then
  DOMAIN="$MAIN_DOMAIN"; TEMP=no
else
  DOMAIN="$TEMP_DOMAIN"; TEMP=yes
  echo "  $MAIN_DOMAIN пока не указывает на этот сервер ($MY_IP) — запускаю сайт на временном адресе $DOMAIN"
fi
set_env MAIN_DOMAIN "$MAIN_DOMAIN"
set_env PUBLIC_URL "https://$DOMAIN"
SERVER_NAMES="$TEMP_DOMAIN"
[[ "$TEMP" == no ]] && SERVER_NAMES="$MAIN_DOMAIN www.$MAIN_DOMAIN $TEMP_DOMAIN"

# Порт панели: 8000, а если он занят другой программой — первый свободный после него.
systemctl stop averix.service 2>/dev/null || true
PORT=$(grep -E '^PANEL_PORT=' "$APP_DIR/.env" | cut -d= -f2- || true)
if [[ -z "$PORT" ]]; then
  PORT=8000
  while ss -ltnH "( sport = :$PORT )" | grep -q .; do PORT=$((PORT + 1)); done
  echo "PANEL_PORT=$PORT" >> "$APP_DIR/.env"
fi
[[ "$PORT" != 8000 ]] && echo "  Порт 8000 занят другой программой — панель будет на порту $PORT"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

say "4/5 Автозапуск, nginx и HTTPS"
cat > /etc/systemd/system/averix.service <<UNIT
[Unit]
Description=Averix hosting panel
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/uvicorn run:app --host 127.0.0.1 --port $PORT --proxy-headers --forwarded-allow-ips=127.0.0.1
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
systemctl enable --now averix.service
systemctl restart averix.service

cat > /etc/nginx/sites-available/averix <<NGINX
server {
    listen 80;
    server_name $SERVER_NAMES;
    client_max_body_size 8m;   # фото чеков до 5 МБ
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/averix /etc/nginx/sites-enabled/averix
# Другие сайты на этом сервере не трогаем: наш блок отвечает только за свой домен.
nginx -t && systemctl reload nginx
if command -v ufw >/dev/null && ufw status | grep -q active; then ufw allow 'Nginx Full' >/dev/null; fi

# HTTPS: для временного адреса — сразу; для основного домена — когда он указывает на сервер.
# certbot запускается каждый раз: конфиг nginx выше перезаписан, и сертификат нужно подключить снова
# (если он ещё действует, новый не выпускается).
CERT_DOMAINS=(-d "$DOMAIN")
if [[ "$TEMP" == no ]]; then
  if points_here "www.$MAIN_DOMAIN"; then CERT_DOMAINS+=(-d "www.$MAIN_DOMAIN"); fi
  CERT_DOMAINS+=(-d "$TEMP_DOMAIN")   # старый временный адрес продолжает работать
fi
certbot --nginx --cert-name averix "${CERT_DOMAINS[@]}" --non-interactive --agree-tos -m "$ADMIN" \
  --redirect --keep-until-expiring --expand || \
  echo "⚠ HTTPS не выпущен. Запустите команду установки ещё раз через несколько минут."

say "5/5 Ежедневная резервная копия базы (хранится 14 дней)"
cat > /etc/cron.daily/averix-backup <<CRON
#!/bin/sh
sqlite3 $APP_DIR/data/hosting.db ".backup '$APP_DIR/backups/hosting-\$(date +%F).db'"
find $APP_DIR/backups -name 'hosting-*.db' -mtime +14 -delete
CRON
chmod +x /etc/cron.daily/averix-backup

STARTED=no
for _ in $(seq 1 20); do
  if curl -fs -o /dev/null "http://127.0.0.1:$PORT/api/config"; then STARTED=yes; break; fi
  sleep 1
done
if [[ "$STARTED" == yes ]]; then
  echo
  echo "✅ Готово: https://$DOMAIN"
  if [[ "$TEMP" == yes ]]; then
    echo "   Это временный адрес: $MAIN_DOMAIN пока не указывает на IP $MY_IP."
    echo "   Поставьте у регистратора A-записи @ и www → $MY_IP, подождите 10–30 минут"
    echo "   и запустите эту же команду ещё раз — сайт сам переедет на https://$MAIN_DOMAIN"
  fi
  echo "   1) Зарегистрируйтесь на сайте с email $ADMIN — вы станете администратором."
  echo "   2) Откройте Админку → «Готовность» и доведите все пункты до зелёного."
  echo "   3) Настройки: $APP_DIR/.env, после правки: systemctl restart averix"
  echo "   Логи: journalctl -u averix -f"
else
  echo "⚠ Панель не запустилась. Последние строки журнала (пришлите их скриншотом):"
  echo "────────────────────────────────────────"
  journalctl -u averix -n 25 --no-pager | cut -c1-220
  echo "────────────────────────────────────────"
  exit 1
fi
