#!/usr/bin/env bash
# Установка Sitora (бот Stars / Premium / подарки) на тот же сервер, ОТДЕЛЬНО от Donatix:
# свой пользователь sitora, своя папка /home/sitora/app, своя база, служба sitora (внутренний порт 8020).
# Мини-приложение — по скрытому адресу https://donatix.tj/_xxxxxxxxxx/ (случайный, сайт Donatix на него не ссылается).
# Код и база Donatix не меняются; в его nginx добавляется одна строка include (с копией и автооткатом).
#
#   sudo bash install.sh
#
# Спросит токен бота, ваш Telegram ID и ключи. Токен и ключи вводятся скрыто (на экране не видно)
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
apt-get install -y -qq python3 python3-venv git >/dev/null

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
  DOMAIN=$(cat /home/donatix/.donatix_domain 2>/dev/null || echo donatix.tj)
  SECRET="_$(tr -dc 'a-z0-9' </dev/urandom | head -c 10)"     # скрытый адрес: случайный, никто не угадает
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
SITORA_BASE_URL=https://$DOMAIN/$SECRET
SITORA_DB=data/sitora.db
SITORA_FAZER_KEY=$FKEY
SITORA_FAZER_URL=https://reseller.fazercards.com/api/v2
SITORA_OPENAI_KEY=$OKEY
SITORA_SUPPORT=$SUP
ENV
  chown $APP_USER:$APP_USER "$ENV_FILE"; chmod 600 "$ENV_FILE"
  unset TOKEN FKEY OKEY
fi
BASE=$(grep -oP '^SITORA_BASE_URL=\K.*' "$ENV_FILE")

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

say "Скрытый адрес на домене Donatix"
bash "$APP_DIR/sitora/deploy/nginx-path.sh"

sleep 2
systemctl is-active --quiet sitora && echo "✅ Готово. Откройте бота и нажмите /start. Адрес мини-приложения (для @BotFather): $BASE/app" \
  || { echo "❌ Служба не запустилась:"; journalctl -u sitora -n 30 --no-pager; }
