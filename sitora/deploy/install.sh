#!/usr/bin/env bash
# Установка Sitora (бот Stars / Premium / подарки) на тот же сервер, ОТДЕЛЬНО от Donatix:
# свой пользователь sitora, своя папка /home/sitora/app, своя база, служба sitora (порт 8020), свой поддомен.
# Donatix этот скрипт не трогает.
#
#   sudo bash install.sh
#
# Спросит поддомен, токен бота, ваш Telegram ID и ключи. Токен и ключи вводятся скрыто (на экране не видно)
# и сохраняются только в /home/sitora/app/sitora/.env (доступ только у пользователя sitora).
set -euo pipefail
APP_USER=sitora
APP_DIR=/home/$APP_USER/app
ENV_FILE=$APP_DIR/sitora/.env
PORT=8020
BRANCH="${SITORA_BRANCH:-claude/website-api-sales-96wxcs}"
say() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo (под root)."; exit 1; }

REPO="${SITORA_REPO:-}"
if [ -z "$REPO" ] && [ -d /home/donatix/app/.git ]; then REPO=$(git -C /home/donatix/app remote get-url origin); fi
REPO="${REPO:-https://github.com/alijon26062006-bit/AlijonMahmadjonov.git}"

say "Пакеты"
apt-get install -y -qq python3 python3-venv git nginx certbot python3-certbot-nginx >/dev/null

id "$APP_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$APP_USER"
chmod 750 /home/$APP_USER

say "Код ($BRANCH)"
if [ -d "$APP_DIR/.git" ]; then
  sudo -u $APP_USER git -C "$APP_DIR" fetch -q origin "$BRANCH" && sudo -u $APP_USER git -C "$APP_DIR" reset -q --hard FETCH_HEAD
else
  sudo -u $APP_USER git clone -q --depth 50 -b "$BRANCH" "$REPO" "$APP_DIR"
fi
sudo -u $APP_USER python3 -m venv "$APP_DIR/sitora/.venv"
sudo -u $APP_USER "$APP_DIR/sitora/.venv/bin/pip" install -q -r "$APP_DIR/sitora/requirements.txt"

if [ ! -f "$ENV_FILE" ]; then
  say "Настройки (токен и ключи на экране не видно — это нормально)"
  read -rp  "Поддомен для мини-приложения [stars.donatix.tj]: " SUB; SUB=${SUB:-stars.donatix.tj}
  read -rp  "Название бота [Sitora]: " NAME; NAME=${NAME:-Sitora}
  read -rsp "Токен бота от @BotFather: " TOKEN; echo
  read -rp  "Ваш Telegram ID (админ; несколько — через запятую): " ADMINS
  read -rsp "API-ключ поставщика для ЭТОГО бота (можно пусто и вписать позже): " FKEY; echo
  read -rsp "Ключ OpenAI для проверки чеков (можно пусто): " OKEY; echo
  read -rp  "Контакт поддержки, например @my_support (можно пусто): " SUP
  umask 077
  cat > "$ENV_FILE" <<ENV
SITORA_NAME=$NAME
SITORA_BOT_TOKEN=$TOKEN
SITORA_ADMIN_IDS=$ADMINS
SITORA_BASE_URL=https://$SUB
SITORA_DB=data/sitora.db
SITORA_FAZER_KEY=$FKEY
SITORA_FAZER_URL=https://reseller.fazercards.com/api/v2
SITORA_OPENAI_KEY=$OKEY
SITORA_SUPPORT=$SUP
ENV
  chown $APP_USER:$APP_USER "$ENV_FILE"; chmod 600 "$ENV_FILE"
  unset TOKEN FKEY OKEY
fi
SUB=$(grep -oP '^SITORA_BASE_URL=https://\K.*' "$ENV_FILE")

say "Проверка настроек"
sudo -u $APP_USER bash -c "cd $APP_DIR/sitora && .venv/bin/python -m sitora check" || true

say "Служба sitora (порт $PORT)"
cat > /etc/systemd/system/sitora.service <<UNIT
[Unit]
Description=Sitora — Stars, Premium, gifts bot
After=network-online.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR/sitora
ExecStart=$APP_DIR/sitora/.venv/bin/python -m sitora serve --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=3
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable -q sitora
systemctl restart sitora

say "Сайт $SUB (nginx + HTTPS)"
cat > /etc/nginx/sites-available/sitora <<NGINX
server {
    listen 80;
    server_name $SUB;
    client_max_body_size 12m;
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/sitora /etc/nginx/sites-enabled/sitora
nginx -t && systemctl reload nginx
if ! getent hosts "$SUB" >/dev/null; then
  echo "⚠ Домен $SUB пока не найден в DNS. Добавьте в Cloudflare запись A: имя ${SUB%%.*} → IP этого сервера ($(curl -4 -s ifconfig.me || echo IP)),"
  echo "  подождите 1–2 минуты и запустите этот скрипт ещё раз — он получит сертификат HTTPS."
else
  certbot --nginx -d "$SUB" --non-interactive --agree-tos --register-unsafely-without-email --redirect -q \
    || echo "⚠ Сертификат не получен. Проверьте DNS-запись $SUB и запустите скрипт ещё раз."
fi

sleep 2
systemctl is-active --quiet sitora && echo "✅ Готово. Откройте бота в Telegram и нажмите /start. Мини-приложение: https://$SUB/app" \
  || { echo "❌ Служба не запустилась:"; journalctl -u sitora -n 30 --no-pager; }
