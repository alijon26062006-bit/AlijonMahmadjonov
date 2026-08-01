#!/usr/bin/env bash
# Установка Cargo Bot на сервер (Ubuntu/Debian) одной командой.
#
# Использование (от root):
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/claude/tariff-management-admin-panel-6ojoo2/cargo_bot/deploy/install.sh \
#     | BOT_TOKEN='ваш_токен' ADMIN_IDS='ваш_id' bash
#
# Повторный запуск безопасен: обновляет код, но сохраняет .env и базу данных.
set -euo pipefail

: "${BOT_TOKEN:?Не задан BOT_TOKEN. Запустите: BOT_TOKEN='...' ADMIN_IDS='...' bash install.sh}"
: "${ADMIN_IDS:?Не задан ADMIN_IDS. Запустите: BOT_TOKEN='...' ADMIN_IDS='...' bash install.sh}"

APP_DIR=/opt/cargo_bot
BRANCH="claude/tariff-management-admin-panel-6ojoo2"
REPO="https://github.com/alijon26062006-bit/AlijonMahmadjonov.git"

echo "==> Установка системных пакетов..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -q
apt-get install -y -q python3 python3-venv python3-pip git

echo "==> Загрузка кода бота..."
rm -rf /tmp/cargo_src
git clone --depth 1 -b "$BRANCH" "$REPO" /tmp/cargo_src
mkdir -p "$APP_DIR"
cp -r /tmp/cargo_src/cargo_bot/. "$APP_DIR"/
rm -rf /tmp/cargo_src

echo "==> Установка Python-зависимостей..."
if [ ! -d "$APP_DIR/.venv" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
    echo "==> Создание .env..."
    cat > "$APP_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
DATABASE_URL=sqlite+aiosqlite:///$APP_DIR/cargo.db
SEED_ON_START=true
EOF
    chmod 600 "$APP_DIR/.env"
else
    echo "==> .env уже существует — не трогаю (настройки сохранены)."
fi

echo "==> Настройка systemd-службы..."
cat > /etc/systemd/system/cargo-bot.service <<EOF
[Unit]
Description=Cargo Telegram Bot (China -> Tajikistan)
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cargo-bot >/dev/null 2>&1
systemctl restart cargo-bot

sleep 3
echo
echo "================================================"
systemctl --no-pager -l status cargo-bot | head -12 || true
echo "================================================"
echo
echo "✅ Готово! Бот запущен и будет автоматически стартовать после перезагрузки."
echo
echo "Полезные команды:"
echo "  journalctl -u cargo-bot -f      # смотреть логи"
echo "  systemctl restart cargo-bot     # перезапустить"
echo "  systemctl stop cargo-bot        # остановить"
echo "  nano $APP_DIR/.env              # изменить токен/настройки"
