#!/usr/bin/env bash
# Установка бота «Битва ников» на Debian/Ubuntu-сервер. Запускать от root:
#
#   bash deploy/install.sh
#
# Скрипт спросит токен, ID канала и ID админа — редактировать файлы руками
# не нужно. Повторный запуск обновляет код и сохраняет настройки и базу.
set -euo pipefail

APP_DIR=/opt/battle-bot
APP_USER=battlebot
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Запустите от root: sudo bash deploy/install.sh" >&2
    exit 1
fi

echo "==> Пакеты"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip

echo "==> Пользователь $APP_USER"
id -u "$APP_USER" >/dev/null 2>&1 \
    || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"

echo "==> Код в $APP_DIR"
mkdir -p "$APP_DIR"
# .env и базу не трогаем — обновление не должно стирать настройки и статистику
find "$SRC_DIR" -mindepth 1 -maxdepth 1 ! -name deploy ! -name '.env' ! -name '*.db*' \
    -exec cp -r {} "$APP_DIR"/ \;

echo "==> Виртуальное окружение"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
    echo
    echo "==> Настройка (Enter — оставить значение по умолчанию)"

    read -rsp "Токен от @BotFather: " BOT_TOKEN; echo
    while [ -z "${BOT_TOKEN:-}" ]; do
        read -rsp "Токен обязателен, введите: " BOT_TOKEN; echo
    done

    read -rp  "ID канала (вида -100...): " CHANNEL_ID
    read -rp  "Ваш Telegram ID (админ):  " ADMIN_IDS
    read -rp  "Время итогов по МСК [18:00,19:30,21:00,22:15,23:30]: " ROUND_TIMES
    read -rp  "Призы за 1/2/3 место в звёздах [1000,500,250]: " PRIZES

    sed \
        -e "s|^BOT_TOKEN=.*|BOT_TOKEN=${BOT_TOKEN}|" \
        -e "s|^CHANNEL_ID=.*|CHANNEL_ID=${CHANNEL_ID}|" \
        -e "s|^ADMIN_IDS=.*|ADMIN_IDS=${ADMIN_IDS}|" \
        -e "s|^DB_PATH=.*|DB_PATH=${APP_DIR}/battle.db|" \
        -e "s|^ROUND_TIMES=.*|ROUND_TIMES=${ROUND_TIMES:-18:00,19:30,21:00,22:15,23:30}|" \
        -e "s|^PRIZES=.*|PRIZES=${PRIZES:-1000,500,250}|" \
        "$APP_DIR/.env.example" > "$APP_DIR/.env"
    echo "Настройки записаны в $APP_DIR/.env"
fi

chmod 600 "$APP_DIR/.env"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> Команда обновления"
# battle-update — подтянуть код и перезапустить бота одной командой
BRANCH="$(git -C "$SRC_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
REPO_DIR="$(git -C "$SRC_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$SRC_DIR")"
sed -e "s|__REPO_DIR__|${REPO_DIR}|" -e "s|__BRANCH__|${BRANCH}|" \
    "$SRC_DIR/deploy/update.sh" > /usr/local/bin/battle-update
chmod +x /usr/local/bin/battle-update

echo "==> Служба systemd"
cp "$SRC_DIR/deploy/battle-bot.service" /etc/systemd/system/battle-bot.service
systemctl daemon-reload
systemctl enable --quiet battle-bot
systemctl restart battle-bot

echo "==> Проверка запуска"
sleep 5
if systemctl is-active --quiet battle-bot; then
    echo
    echo "✅ Бот работает."
    journalctl -u battle-bot -n 15 --no-pager | sed 's/^/   /'
    echo
    echo "Логи в реальном времени:  journalctl -u battle-bot -f"
    echo "Обновить бота одной командой:  battle-update"
else
    echo
    echo "❌ Бот не поднялся. Причина в логе:"
    journalctl -u battle-bot -n 30 --no-pager | sed 's/^/   /'
    exit 1
fi
