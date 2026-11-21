#!/usr/bin/env bash
# Установка Sitora (бот Stars / Premium / подарки) на тот же сервер, ОТДЕЛЬНО от Donatix:
# свой пользователь sitora, своя папка /home/sitora/app, своя база, служба sitora (внутренний порт 8020).
# Мини-приложение — по скрытому адресу https://donatix.tj/_xxxxxxxxxx/ (случайный, сайт Donatix на него не ссылается).
# Код и база Donatix не меняются; в его nginx добавляется одна строка include (с копией и автооткатом).
#
#   sudo bash install.sh
#
# Спросит только токен бота (вводится скрыто), потом ждёт, пока вы нажмёте /start в боте, —
# так берёт ваш Telegram ID и делает вас админом. Ключ поставщика вписывается позже: deploy/set-key.sh.
# Всё хранится только в /home/sitora/app/sitora/.env (доступ только у пользователя sitora).
set -euo pipefail
APP_USER=sitora
APP_DIR=/home/$APP_USER/app
ENV_FILE=$APP_DIR/sitora/.env
PORT=8020
BRANCH="${SITORA_BRANCH:-claude/website-api-sales-96wxcs}"
trap 'echo "❌ Ошибка (строка $LINENO): $BASH_COMMAND"' ERR
get_code() {  # код берём через копию Donatix (у неё доступ к GitHub уже настроен); Donatix не меняется
  sudo -u donatix git -C /home/donatix/app fetch -q origin "$BRANCH"
  mkdir -p "$APP_DIR"
  sudo -u donatix git -C /home/donatix/app archive FETCH_HEAD sitora | tar -x -C "$APP_DIR"
  chown -R $APP_USER:$APP_USER "$APP_DIR"
  echo "   версия: $(sudo -u donatix git -C /home/donatix/app log -1 --format='%h %s' FETCH_HEAD)"
}
say() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo (под root)."; exit 1; }


say "Пакеты"
apt-get install -y -qq python3 python3-venv git >/dev/null

id "$APP_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$APP_USER"
chmod 750 /home/$APP_USER

say "Код ($BRANCH)"
get_code
sudo -u $APP_USER python3 -m venv "$APP_DIR/sitora/.venv"
sudo -u $APP_USER "$APP_DIR/sitora/.venv/bin/pip" install -q -r "$APP_DIR/sitora/requirements.txt"

set_env() {  # set_env KEY VALUE — заменить/добавить строку в .env (значение не попадает в аргументы процессов)
  KEY="$1" VAL="$2" python3 - "$ENV_FILE" <<'PY2'
import os, sys
p, k, v = sys.argv[1], os.environ["KEY"], os.environ["VAL"]
lines = open(p, encoding="utf-8").read().splitlines()
lines = [l for l in lines if not l.startswith(k + "=")] + [f"{k}={v}"]
open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY2
}
env_get() { grep -oP "^$1=\K.*" "$ENV_FILE" 2>/dev/null || true; }

if [ ! -f "$ENV_FILE" ]; then
  DOMAIN=$(cat /home/donatix/.donatix_domain 2>/dev/null || echo donatix.tj)
  SECRET="_$(tr -dc 'a-z0-9' </dev/urandom | head -c 10)"     # скрытый адрес: случайный, никто не угадает
  umask 077
  cat > "$ENV_FILE" <<ENV
SITORA_NAME=${SITORA_NAME:-Sitora}
SITORA_BOT_TOKEN=
SITORA_ADMIN_IDS=
SITORA_BASE_URL=https://$DOMAIN/$SECRET
SITORA_DB=data/sitora.db
SITORA_FAZER_KEY=
SITORA_FAZER_URL=https://reseller.fazercards.com/api/v2
SITORA_OPENAI_KEY=
SITORA_SUPPORT=
ENV
  chown $APP_USER:$APP_USER "$ENV_FILE"; chmod 600 "$ENV_FILE"
fi

# 1) токен бота — вводится скрыто, проверяется сразу
if [ -z "$(env_get SITORA_BOT_TOKEN)" ]; then
  say "Токен бота"
  while :; do
    read -rsp "Вставьте токен бота от @BotFather (на экране не видно) и нажмите Enter: " TOKEN; echo
    TOKEN=$(printf '%s' "$TOKEN" | tr -d '[:space:]')
    [ -n "$TOKEN" ] && TG_TOKEN="$TOKEN" python3 - <<'PY2' && break
import json, os, sys, urllib.request
try:
    r = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{os.environ['TG_TOKEN']}/getMe", timeout=15))
    print("✅ Бот:", "@" + r["result"]["username"])
except Exception:
    print("❌ Токен не подошёл, попробуйте ещё раз."); sys.exit(1)
PY2
  done
  set_env SITORA_BOT_TOKEN "$TOKEN"; unset TOKEN
fi

# 2) админ — ваш ID берётся сам, когда вы нажмёте /start в боте
if [ -z "$(env_get SITORA_ADMIN_IDS)" ]; then
  say "Ваш Telegram ID"
  systemctl stop sitora 2>/dev/null || true        # чтобы бот не перехватил ваше нажатие
  ADMIN=$(TG_TOKEN="$(env_get SITORA_BOT_TOKEN)" python3 "$APP_DIR/sitora/deploy/wait_start.py")
  set_env SITORA_ADMIN_IDS "$ADMIN"
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
systemctl is-active --quiet sitora && printf '\n✅ Готово. В боте нажмите /start, потом /admin.\n   Адрес мини-приложения (для @BotFather): %s/app\n   Ключ поставщика потом: sudo bash %s/sitora/deploy/set-key.sh\n' "$BASE" "$APP_DIR" \
  || { echo "❌ Служба не запустилась:"; journalctl -u sitora -n 30 --no-pager; }
