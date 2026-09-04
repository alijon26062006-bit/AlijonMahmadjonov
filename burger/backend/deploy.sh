#!/usr/bin/env bash
# Установка сервера The Burger на Ubuntu или Debian.
# Запускать от root на чистом VPS:  sudo bash deploy.sh
set -euo pipefail

APP_DIR=${APP_DIR:-/srv/burger}
SERVICE=burger
PORT=${PORT:-8000}

say() { printf '\n\033[1;33m→ %s\033[0m\n' "$1"; }

[ "$(id -u)" -eq 0 ] || { echo "Запустите от root: sudo bash deploy.sh"; exit 1; }

say "Ставим Python и Caddy"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl debian-keyring debian-archive-keyring apt-transport-https
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy
fi

say "Кладём код в $APP_DIR"
mkdir -p "$APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone --depth 1 "${REPO:-https://github.com/alijon26062006-bit/AlijonMahmadjonov.git}" "$APP_DIR"
fi

BACKEND="$APP_DIR/burger/backend"
python3 -m venv "$BACKEND/.venv"
"$BACKEND/.venv/bin/pip" install -q --upgrade pip
"$BACKEND/.venv/bin/pip" install -q -r "$BACKEND/requirements.txt"

say "Настройки"
if [ ! -f "$BACKEND/.env" ]; then
  ADMIN_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(12))")
  cat > "$BACKEND/.env" <<ENV
ADMIN_PASSWORD=$ADMIN_PASS
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
TG_TOKEN=
TG_ADMIN_CHAT=
PUBLIC_URL=
TG_HOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(8))")
ALLOWED_ORIGINS=*
ORDER_COOLDOWN=20
ENV
  chmod 600 "$BACKEND/.env"
  NEW_PASS=$ADMIN_PASS
fi

say "Служба systemd"
cat > /etc/systemd/system/$SERVICE.service <<UNIT
[Unit]
Description=The Burger
After=network.target

[Service]
WorkingDirectory=$BACKEND
EnvironmentFile=$BACKEND/.env
ExecStart=$BACKEND/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now $SERVICE
systemctl restart $SERVICE

say "Ежедневная копия базы"
mkdir -p /srv/backup
cat > /etc/cron.daily/burger-backup <<'CRON'
#!/bin/sh
sqlite3 /srv/burger/burger/backend/data/burger.db ".backup /srv/backup/burger-$(date +%F).db" 2>/dev/null
find /srv/backup -name 'burger-*.db' -mtime +14 -delete
CRON
chmod +x /etc/cron.daily/burger-backup

sleep 2
if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null; then
  say "Сервер поднят"
else
  echo "Сервер не ответил. Смотрите: journalctl -u $SERVICE -n 50"; exit 1
fi

cat <<DONE

Готово. Осталось два шага:

1. Домен. Впишите свой в /etc/caddy/Caddyfile:

     api.вашдомен.tj {
         reverse_proxy 127.0.0.1:$PORT
     }

   потом: systemctl reload caddy
   HTTPS Caddy оформит сам.

2. Бот. Токен у @BotFather, свой id у @userinfobot — впишите
   в $BACKEND/.env (TG_TOKEN и TG_ADMIN_CHAT), потом:

     systemctl restart $SERVICE

3. Курьеры. В .env впишите PUBLIC_URL (адрес сайта с https),
   перезапустите службу и один раз включите вебхук:

     cd $BACKEND && python3 hook.py on

   Дальше курьер жмёт «Старт» у бота, а вы допускаете его
   на странице /admin/couriers.

${NEW_PASS:+Пароль в админку: $NEW_PASS  (сохраните, второй раз не покажу)}

Админка:  http://адрес-сервера/admin
Проверка: curl http://127.0.0.1:$PORT/api/health
DONE
