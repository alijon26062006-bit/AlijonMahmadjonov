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
    STAMP=$(date +%F-%H%M)
    KEEP="/srv/backup/burger-before-clean-$STAMP.db"
    cp "$APP_DIR/burger/backend/data/burger.db" "$KEEP"
    echo "База сохранена: $KEEP"
    if [ -d "$APP_DIR/burger/backend/receipts" ]; then
      tar -czf "/srv/backup/receipts-before-clean-$STAMP.tgz" \
          -C "$APP_DIR/burger/backend" receipts 2>/dev/null || true
      echo "Чеки сохранены: /srv/backup/receipts-before-clean-$STAMP.tgz"
    fi
  fi
  systemctl stop $SERVICE 2>/dev/null || true
  systemctl disable $SERVICE 2>/dev/null || true
  rm -f /etc/systemd/system/$SERVICE.service /etc/cron.daily/burger-backup
  systemctl daemon-reload 2>/dev/null || true
  rm -rf "$APP_DIR"
fi

ADMIN_BOT=${ARGS[3]:-${TG_ADMIN_TOKEN:-}}

# Токены можно не передавать в командной строке — спросим и не оставим в истории.
if [ -z "$BOT" ] && [ -e /dev/tty ]; then
  printf '\nТокен бота КУРЬЕРОВ у @BotFather (Enter — настроить позже): '
  read -r BOT < /dev/tty || BOT=''
  if [ -n "$BOT" ]; then
    printf 'Ваш id у @userinfobot — куда слать заказы: '
    read -r CHAT < /dev/tty || CHAT=''
    printf 'Токен второго бота, для АДМИНКИ (Enter — пропустить): '
    read -r ADMIN_BOT < /dev/tty || ADMIN_BOT=''
  fi
fi

say "Ставим Python и Caddy"
apt-get update -qq
# sqlite3 нужен для ежедневной копии базы: без него копия молча не делалась
apt-get install -y -qq python3 python3-pip python3-venv git curl sqlite3 \
  debian-keyring debian-archive-keyring apt-transport-https
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
TG_ADMIN_TOKEN=
PUBLIC_URL=https://$DOMAIN
TG_HOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(8))")
TG_ADMIN_HOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(8))")
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
if [ -n "$ADMIN_BOT" ]; then
  # в базах, поставленных до второго бота, этих строк ещё нет
  grep -q '^TG_ADMIN_TOKEN=' "$BACKEND/.env" || echo 'TG_ADMIN_TOKEN=' >> "$BACKEND/.env"
  grep -q '^TG_ADMIN_HOOK_SECRET=' "$BACKEND/.env" || \
    echo "TG_ADMIN_HOOK_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(8))')" >> "$BACKEND/.env"
  sed -i "s|^TG_ADMIN_TOKEN=.*|TG_ADMIN_TOKEN=$ADMIN_BOT|" "$BACKEND/.env"
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
{
    servers {
        timeouts {
            read_body   30s
            read_header 10s
            write       60s
            idle        2m
        }
    }
}

$DOMAIN, www.$DOMAIN {
    encode gzip

    # ни один честный запрос не весит больше: чек — до 8 МБ, фото блюда — до 6
    request_body {
        max_size 12MB
    }

    header {
        # браузер не должен додумывать тип файла и показывать сайт в чужой рамке
        X-Content-Type-Options nosniff
        Referrer-Policy same-origin
        X-Frame-Options SAMEORIGIN
        Strict-Transport-Security "max-age=31536000"
        -Server
    }

    # всё, что относится к серверу: меню, заказы, админка, кухня, курьеры
    @backend path /api/* /admin* /kitchen* /courier* /tg/* /uploads/* /static/*
    reverse_proxy @backend 127.0.0.1:$PORT

    # сам сайт — обычные файлы, отдаются без Python
    root * $APP_DIR/burger
    file_server

    header /assets/* Cache-Control "public, max-age=604800"
    header /css/* Cache-Control "public, max-age=86400"
    header /js/* Cache-Control "public, max-age=86400"

    # чеки об оплате рядом с фото блюд не лежат, но на всякий случай запрещаем
    respond /uploads/receipt-* 404
}
CADDY
systemctl reload caddy || systemctl restart caddy

say "Сторож: следит, что сервер жив"
cat > /etc/cron.d/burger-watchdog <<CRON
# раз в пять минут: сервер отвечает? место есть? база цела?
*/5 * * * * root BACKEND=$BACKEND SERVICE=$SERVICE PORT=$PORT sh $BACKEND/watchdog.sh
CRON
chmod 644 /etc/cron.d/burger-watchdog

say "Ежедневная копия базы"
mkdir -p /srv/backup
cat > /etc/cron.daily/burger-backup <<'CRON'
#!/bin/sh
# Копия базы и чеков. Ошибки пишем в журнал, а не в тишину:
# незамеченная поломка копий обнаруживается ровно в тот день, когда они нужны.
set -e
DB=/srv/burger/burger/backend/data/burger.db
OUT=/srv/backup/burger-$(date +%F).db

if ! sqlite3 "$DB" ".backup '$OUT'"; then
  logger -t burger-backup "копия базы не сделана"
  exit 1
fi
gzip -f "$OUT"

tar -czf "/srv/backup/receipts-$(date +%F).tgz" \
    -C /srv/burger/burger/backend receipts 2>/dev/null || true

find /srv/backup -name 'burger-*.db.gz' -mtime +30 -delete
find /srv/backup -name 'receipts-*.tgz' -mtime +30 -delete
logger -t burger-backup "копия готова: $OUT.gz"
CRON
chmod +x /etc/cron.daily/burger-backup

say "Ждём, пока сервер поднимется"
UP=''
for _ in $(seq 1 40); do            # первый запуск наполняет базу — это пара секунд
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then UP=1; break; fi
  sleep 1
done

if [ -n "$UP" ]; then
  say "Сервер поднят"
else
  echo
  echo "Сервер не ответил. Вот что пишет журнал:"
  echo "──────────────────────────────────────────"
  journalctl -u $SERVICE -n 30 --no-pager || true
  echo "──────────────────────────────────────────"
  exit 1
fi

if grep -qE '^TG_(ADMIN_)?TOKEN=.+' "$BACKEND/.env"; then
  say "Включаем ботов"
  (cd "$BACKEND" && "$BACKEND/.venv/bin/python" hook.py on) || \
    echo "Вебхук не включился. Проверьте домен и повторите: cd $BACKEND && .venv/bin/python hook.py on"
  BOT_READY=1
fi

cat <<DONE

Готово. Сайт: https://$DOMAIN

Проверьте, что A-запись домена (и www) указывает на этот сервер —
без неё Caddy не получит сертификат, и сайт откроется только по IP.

${BOT_READY:+Боты включены.
— Админка открывается прямо в Telegram: напишите боту админки «Старт»
  и нажмите «Открыть админку».
— Курьер жмёт «Старт» у бота курьеров, отправляет номер и имя, а вы
  нажимаете «Допустить» — в чате или на https://$DOMAIN/admin/couriers.}
${BOT_READY:-Боты пока не настроены. Когда будут токены у @BotFather:

     bash deploy.sh $DOMAIN ТОКЕН_КУРЬЕРОВ ВАШ_ID ТОКЕН_АДМИНКИ
}
${NEW_PASS:+Пароль в админку: $NEW_PASS  (сохраните, второй раз не покажу)}

Админка: https://$DOMAIN/admin
Кухня:   https://$DOMAIN/kitchen
Проверка: curl https://$DOMAIN/api/health
DONE
