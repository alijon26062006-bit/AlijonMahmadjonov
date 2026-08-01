#!/usr/bin/env bash
# Установка Cargo Bot на сервер (Ubuntu/Debian). Запускать от root.
#
# Способ 1 — скрипт сам спросит токен и ваш Telegram ID:
#   curl -fsSL <URL этого файла> -o i.sh && bash i.sh
#
# Способ 2 — передать сразу, без вопросов:
#   BOT_TOKEN='...' ADMIN_IDS='...' bash i.sh
#
# Повторный запуск безопасен: код обновится, а .env и база данных сохранятся.
set -euo pipefail

APP_DIR=/opt/cargo_bot
BRANCH="claude/tariff-management-admin-panel-6ojoo2"
REPO="https://github.com/alijon26062006-bit/AlijonMahmadjonov.git"

if [ "$(id -u)" -ne 0 ]; then
    echo "❌ Запустите скрипт от root (или через sudo)."
    exit 1
fi

# ---------- 1. Токен и админ ----------
HAVE_ENV=0
[ -f "$APP_DIR/.env" ] && HAVE_ENV=1

if [ "$HAVE_ENV" -eq 1 ]; then
    echo "ℹ️  Найден $APP_DIR/.env — настройки берутся из него, вопросов не будет."
else
    if [ -z "${BOT_TOKEN:-}" ]; then
        read -rp "Введите токен бота (от @BotFather): " BOT_TOKEN
    fi
    if [ -z "${ADMIN_IDS:-}" ]; then
        read -rp "Введите ваш Telegram ID (кто будет админом): " ADMIN_IDS
    fi
    if [ -z "${BOT_TOKEN:-}" ] || [ -z "${ADMIN_IDS:-}" ]; then
        echo "❌ Токен и Telegram ID обязательны."
        exit 1
    fi
fi

# ---------- 2. Системные пакеты ----------
echo "==> Устанавливаю системные пакеты..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -q
apt-get install -y -q python3 python3-venv python3-pip git curl

PYV=$(python3 -c 'import sys; print("%d%02d" % sys.version_info[:2])')
if [ "$PYV" -lt 310 ]; then
    echo "❌ Боту нужен Python 3.10 или новее, а найден $(python3 -V)."
    echo "   Варианты: обновить ОС до Ubuntu 22.04+/Debian 12,"
    echo "   либо установить новый Python: apt-get install -y python3.11 python3.11-venv"
    exit 1
fi
echo "    Python: $(python3 -V) — подходит."

# ---------- 3. Проверка токена ----------
if [ "$HAVE_ENV" -eq 0 ]; then
    echo "==> Проверяю токен в Telegram..."
    RESP=$(curl -fsS --max-time 25 "https://api.telegram.org/bot${BOT_TOKEN}/getMe" || true)
    if echo "$RESP" | grep -q '"ok":true'; then
        BOT_USERNAME=$(echo "$RESP" | sed -n 's/.*"username":"\([^"]*\)".*/\1/p')
        echo "    ✅ Токен рабочий. Бот: @${BOT_USERNAME}"
    else
        echo "    ❌ Telegram не принял этот токен."
        echo "       Проверьте его у @BotFather (/mybots → API Token) и запустите скрипт заново."
        exit 1
    fi
fi

# ---------- 4. Код бота ----------
echo "==> Загружаю код бота из GitHub..."
rm -rf /tmp/cargo_src
git clone --depth 1 -b "$BRANCH" "$REPO" /tmp/cargo_src -q
mkdir -p "$APP_DIR"
cp -r /tmp/cargo_src/cargo_bot/. "$APP_DIR"/
rm -rf /tmp/cargo_src

# ---------- 5. Зависимости ----------
echo "==> Устанавливаю Python-зависимости (может занять минуту)..."
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# ---------- 6. Настройки ----------
if [ "$HAVE_ENV" -eq 0 ]; then
    echo "==> Создаю файл настроек .env..."
    cat > "$APP_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
DATABASE_URL=sqlite+aiosqlite:///$APP_DIR/cargo.db
SEED_ON_START=true
EOF
    chmod 600 "$APP_DIR/.env"
fi

# ---------- 7. Служба systemd ----------
echo "==> Настраиваю автозапуск (systemd)..."
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
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cargo-bot >/dev/null 2>&1
systemctl restart cargo-bot

# ---------- 8. Результат ----------
sleep 5
echo
if systemctl is-active --quiet cargo-bot; then
    echo "=================================================="
    echo "✅ ГОТОВО! Бот запущен и работает."
    echo "   Он будет сам подниматься после перезагрузки сервера"
    echo "   и автоматически перезапускаться при сбоях."
    echo "=================================================="
    echo
    echo "Откройте бота в Telegram и отправьте /start"
    echo "Панель администратора — команда /admin"
else
    echo "=================================================="
    echo "⚠️  Бот установлен, но не запустился. Последние логи:"
    echo "=================================================="
    journalctl -u cargo-bot -n 25 --no-pager || true
fi
echo
echo "Полезные команды:"
echo "  journalctl -u cargo-bot -f     # смотреть логи вживую (выход: Ctrl+C)"
echo "  systemctl restart cargo-bot    # перезапустить бота"
echo "  systemctl stop cargo-bot       # остановить бота"
echo "  nano $APP_DIR/.env             # изменить токен или админов"
