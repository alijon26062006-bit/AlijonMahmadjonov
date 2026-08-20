#!/usr/bin/env bash
# Установка бота на Debian/Ubuntu-сервер. Запускать от root.
#
#   bash deploy/install.sh
#
# Скрипт НЕ создаёт .env — заполните его сами перед стартом службы.
set -euo pipefail

APP_DIR=/opt/battle-bot
APP_USER=battlebot

echo "==> Пакеты"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git

echo "==> Пользователь $APP_USER"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"

echo "==> Код в $APP_DIR"
mkdir -p "$APP_DIR"
cp -r "$(dirname "$0")/.."/* "$APP_DIR"/
rm -rf "$APP_DIR/deploy"

echo "==> Виртуальное окружение"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo "!! Создан $APP_DIR/.env из шаблона — заполните BOT_TOKEN, CHANNEL_ID, ADMIN_IDS"
fi
chmod 600 "$APP_DIR/.env"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> Служба systemd"
cp "$(dirname "$0")/battle-bot.service" /etc/systemd/system/battle-bot.service
systemctl daemon-reload
systemctl enable battle-bot

cat <<'DONE'

Готово. Дальше:

  nano /opt/battle-bot/.env      # заполнить настройки
  systemctl start battle-bot
  journalctl -u battle-bot -f    # смотреть логи

DONE
