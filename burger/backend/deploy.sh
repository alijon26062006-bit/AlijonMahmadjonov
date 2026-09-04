#!/usr/bin/env bash
# Установка сервера The Burger на Ubuntu или Debian.
# Запускать от root на чистом VPS:  sudo bash deploy.sh
set -euo pipefail

APP_DIR=${APP_DIR:-/srv/burger}
SERVICE=burger
PORT=${PORT:-8000}
BRANCH=${BRANCH:-claude/phone-store-frontend-design-fzwpi1}

# Всё можно передать одной строкой:
#   bash deploy.sh theburger.tj 123456:ABC... 987654321
#   bash deploy.sh theburger.tj --clean      — снести прошлую установку и поставить заново
CLEAN=''
ARGS=()
for a in "$@"; do
  case "$a" in
    --clean|clean) CLEAN=1 ;;
    *) ARGS+=("$a") ;;
  esac
done

DOMAIN=${ARGS[0]:-${DOMAIN:-}}
BOT=${ARGS[1]:-${TG_TOKEN:-}}
CHAT=${ARGS[2]:-${TG_ADMIN_CHAT:-}}

say() { printf '\n\033[1;33m→ %s\033[0m\n' "$1"; }

[ "$(id -u)" -eq 0 ] || { echo "Запустите от root: bash deploy.sh вашдомен.tj"; exit 1; }
[ -n "$DOMAIN" ] || { echo "Укажите домен: bash deploy.sh theburger.tj"; exit 1; }

if [ -n "$CLEAN" ]; then
  say "Убираем прошлую установку"
  # база — единственное, что нельзя терять. Копия остаётся, даже если её не просили.
  if [ -f "$APP_DIR/burger/backend/data/burger.db" ]; then
    mkdir -p /srv/backup
    KEEP="/srv/backup/burger-before-clean-$(date +%F-%H%M).db"
    cp "$APP_DIR/burger/backend/data/burger.db" "$KEEP"
    echo "База сохранена: $KEEP"
  fi
  systemctl stop $SERVICE 2>/dev/null || true
  systemctl disable $SERVICE 2>/dev/null || true
  rm -f /etc/systemd/system/$SERVICE.service /etc/cron.daily/burger-backup
  systemctl daemon-reload 2>/dev/null || true
  rm -rf "$APP_DIR"
fi

# Токен можно не передавать в командной строке — спросим и не оставим в истории.
if [ -z "$BOT" ] && [ -e /dev/tty ]; then
  printf '\nТокен бота у @BotFather (Enter — настроить позже): '
  read -r BOT < /dev/tty || BOT=''
  if [ -n "$BOT" ]; then
    printf 'Ваш id у @userinfobot — куда слать заказы: '
    read -r CHAT < /dev/tty || CHAT=''
  fi
fi

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
REPO=${REPO:-https://github.com/alijon26062006-bit/AlijonMahmadjonov.git}
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" checkout -B "$BRANCH" FETCH_HEAD
else
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$APP_DIR"
fi
[ -f "$APP_DIR/burger/backend/app.py" ] || { echo "В репозитории нет burger/backend — не та ветка?"; exit 1; }

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
PUBLIC_URL=https://$DOMAIN
TG_HOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(8))")
ALLOWED_ORIGINS=https://$DOMAIN
ORDER_COOLDOWN=20
ENV
  chmod 600 "$BACKEND/.env"
  NEW_PASS=$ADMIN_PASS
else
  # домен могли поменять — держим настройки в согласии с ним
  sed -i "s|^PUBLIC_URL=.*|PUBLIC_URL=https://$DOMAIN|" "$BACKEND/.env"
  sed -i "s|^ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=https://$DOMAIN|" "$BACKEND/.env"
fi

# токен и чат — только если их передали, иначе не трогаем уже настроенное
if [ -n "$BOT" ]; then
  sed -i "s|^TG_TOKEN=.*|TG_TOKEN=$BOT|" "$BACKEND/.env"
fi
if [ -n "$CHAT" ]; then
  sed -i "s|^TG_ADMIN_CHAT=.*|TG_ADMIN_CHAT=$CHAT|" "$BACKEND/.env"
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

say "Домен $DOMAIN и HTTPS"
cat > /etc/caddy/Caddyfile <<CADDY
$DOMAIN, www.$DOMAIN {
    encode gzip

    # всё, что относится к серверу: меню, заказы, админка, кухня, курьеры
    @backend path /api/* /admin* /kitchen* /courier* /tg/* /uploads/* /static/*
    reverse_proxy @backend 127.0.0.1:$PORT

    # сам сайт — обычные файлы, отдаются без Python
    root * $APP_DIR/burger
    file_server

    header /assets/* Cache-Control "public, max-age=604800"
}
CADDY
systemctl reload caddy || systemctl restart caddy

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

if grep -q '^TG_TOKEN=.\+' "$BACKEND/.env"; then
  say "Включаем бота курьеров"
  (cd "$BACKEND" && "$BACKEND/.venv/bin/python" hook.py on) || \
    echo "Вебхук не включился. Проверьте домен и повторите: cd $BACKEND && .venv/bin/python hook.py on"
  BOT_READY=1
fi

cat <<DONE

Готово. Сайт: https://$DOMAIN

Проверьте, что A-запись домена (и www) указывает на этот сервер —
без неё Caddy не получит сертификат, и сайт откроется только по IP.

${BOT_READY:+Бот включён. Курьер жмёт «Старт» у бота и появляется на
https://$DOMAIN/admin/couriers — нажмите «Допустить», и заказы пойдут ему в чат.}
${BOT_READY:-Бот пока не настроен. Когда будет токен у @BotFather:

     sudo bash deploy.sh $DOMAIN ТОКЕН ВАШ_ID
}
${NEW_PASS:+Пароль в админку: $NEW_PASS  (сохраните, второй раз не покажу)}

Админка: https://$DOMAIN/admin
Кухня:   https://$DOMAIN/kitchen
Проверка: curl https://$DOMAIN/api/health
DONE
