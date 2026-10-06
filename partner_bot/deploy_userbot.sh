#!/usr/bin/env bash
# Обновить установленный бот (/opt/stars-bot/stars_bot) этим кодом и подключить
# автоплатёж через юзербота — одной командой.
#
#   sudo bash deploy_userbot.sh API_ID API_HASH BANK_BOT
#
# Что делает:
#   1. копия старого бота (код, .env, база) в /root/stars-bot-backup-ДАТА;
#   2. новый код поверх старого — .env, база, data/ и окружение не трогаются;
#   3. проверка, что новый код запускается; не запускается — откат из копии;
#   4. ключи Telegram и банковский бот в .env;
#   5. перезапуск бота, вход юзербота (код из Telegram вводите здесь), запуск юзербота.
# Ключи в репозиторий не попадают — только в .env на сервере.
set -euo pipefail

API_ID="${1:-}"; API_HASH="${2:-}"; BANK="${3:-}"
APP="${APP:-/opt/stars-bot/stars_bot}"
SERVICE="${SERVICE:-stars-bot}"
RUN_USER="${RUN_USER:-starsbot}"
SRC="$(cd "$(dirname "$0")" && pwd)"

die() { echo "❌ $*"; exit 1; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
echo "$API_ID" | grep -qE '^[0-9]{5,12}$' || die "API_ID — число, например 12345678."
echo "$API_HASH" | grep -qiE '^[a-f0-9]{32}$' || die "API_HASH — 32 знака (цифры и a-f)."
BANK="${BANK#@}"
echo "$BANK" | grep -qE '^[A-Za-z0-9_]{4,32}$' || die "BANK_BOT — юзернейм без @ или числовой id."
[ -f "$APP/.env" ] || die "Не нашёл бота в $APP (нет .env)."
[ -d "$SRC/app" ] || die "Рядом со скриптом нет папки app."

BACKUP="/root/stars-bot-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
tar -C "$APP" --exclude=./.venv --exclude='__pycache__' -czf "$BACKUP/stars_bot.tgz" .
echo "✅ Копия старого бота: $BACKUP/stars_bot.tgz"

rollback() {
    echo "↩️  Возвращаю старую версию…"
    rm -rf "$APP/app"
    tar -C "$APP" -xzf "$BACKUP/stars_bot.tgz"
    systemctl restart "$SERVICE"
    die "Новый код не запустился — бот возвращён как был. Пришлите вывод выше."
}

rm -rf "$APP/app"
tar -C "$SRC" --exclude=./.env --exclude=./data --exclude=./.venv --exclude=./tests \
    --exclude='*.sqlite3*' --exclude='*.session*' --exclude='__pycache__' -cf - . | tar -C "$APP" -xf -
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt" || rollback
( cd "$APP" && sudo -u "$RUN_USER" "$APP/.venv/bin/python" -c "import app.main, app.userbot.runner" ) || rollback
echo "✅ Код обновлён"

setenv() {
    if grep -q "^$1=" "$APP/.env"; then
        sed -i "s|^$1=.*|$1=$2|" "$APP/.env"
    else
        printf '\n%s=%s\n' "$1" "$2" >> "$APP/.env"
    fi
}
setenv TG_API_ID "$API_ID"
setenv TG_API_HASH "$API_HASH"
setenv BANK_BOT "$BANK"
echo "✅ Ключи Telegram и банковский бот (@$BANK) записаны в .env"

mkdir -p "$APP/data"
chown "$RUN_USER" "$APP/data"
systemctl restart "$SERVICE"
sleep 3
systemctl is-active --quiet "$SERVICE" || rollback
echo "✅ Бот перезапущен — теперь чек при оплате картой не нужен"

# Служба юзербота: создаём, если её ещё нет.
UNIT="/etc/systemd/system/$SERVICE-userbot.service"
if [ ! -f "$UNIT" ]; then
    cat > "$UNIT" <<EOF
[Unit]
Description=Stars Bot — приём оплат от банковского бота
After=network-online.target $SERVICE.service
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APP
ExecStart=$APP/.venv/bin/python -m app.userbot
Restart=always
RestartSec=15
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP/data

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
fi

# Вход: на время входа служба остановлена — два процесса на одном сеансе мешают.
systemctl stop "$SERVICE-userbot" 2>/dev/null || true
echo ""
echo "═══ Вход юзербота в ваш Telegram ═══"
if ( cd "$APP" && sudo -u "$RUN_USER" "$APP/.venv/bin/python" -m app.userbot.login ) </dev/tty; then
    systemctl enable --now "$SERVICE-userbot"
    sleep 5
    echo ""
    journalctl -u "$SERVICE-userbot" -n 15 --no-pager | grep USERBOT || true
    echo ""
    echo "✅ Готово. Автоплатёж работает. Смотреть живьём: journalctl -u $SERVICE-userbot -f"
else
    echo "⚠️ Вход не завершён. Бот работает, но оплаты пока подтверждаются вручную."
    echo "   Повторить вход: sudo bash $0 $API_ID <API_HASH> $BANK"
    exit 1
fi
