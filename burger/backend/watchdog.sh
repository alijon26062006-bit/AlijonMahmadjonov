#!/bin/sh
# Сторож. Запускается по расписанию раз в пять минут.
#
# Проверяет, что сервер отвечает, что на диске есть место и что база на месте.
# Если сервер молчит — поднимает его и пишет хозяину в Telegram. Молча падать
# ночью, когда никто не смотрит, проект не должен.

set -u

BACKEND=${BACKEND:-/srv/burger/burger/backend}
SERVICE=${SERVICE:-burger}
PORT=${PORT:-8000}
DB="$BACKEND/data/burger.db"
STATE=/var/tmp/burger-watchdog

say() { logger -t burger-watchdog "$1"; }

tell() {
    # токен и чат берём из .env, отдельно ничего настраивать не надо
    token=$(grep '^TG_ADMIN_TOKEN=' "$BACKEND/.env" 2>/dev/null | cut -d= -f2-)
    [ -z "$token" ] && token=$(grep '^TG_TOKEN=' "$BACKEND/.env" 2>/dev/null | cut -d= -f2-)
    chat=$(grep '^TG_ADMIN_CHAT=' "$BACKEND/.env" 2>/dev/null | cut -d= -f2-)
    [ -z "$token" ] || [ -z "$chat" ] && return 0
    curl -sS -m 10 -o /dev/null "https://api.telegram.org/bot$token/sendMessage" \
        --data-urlencode "chat_id=$chat" --data-urlencode "text=$1" || true
}

# ── сервер отвечает? ───────────────────────────────────
if curl -fsS -m 10 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    if [ -f "$STATE.down" ]; then
        rm -f "$STATE.down"
        say "сервер снова отвечает"
        tell "✅ Сайт снова работает."
    fi
else
    sleep 10          # мог просто перезапускаться
    if ! curl -fsS -m 10 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
        say "сервер не отвечает, поднимаю"
        systemctl restart "$SERVICE"
        sleep 8
        if curl -fsS -m 10 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
            touch "$STATE.down"
            tell "⚠️ Сайт падал, я его поднял. Всё работает."
        else
            touch "$STATE.down"
            tell "🚨 Сайт лежит и не поднимается. Нужна помощь: journalctl -u $SERVICE -n 50"
        fi
    fi
fi

# ── место на диске ─────────────────────────────────────
used=$(df -P "$BACKEND" | awk 'NR==2 {print $5}' | tr -d '%')
if [ "${used:-0}" -ge 90 ]; then
    if [ ! -f "$STATE.disk" ]; then
        touch "$STATE.disk"
        say "диск занят на ${used}%"
        tell "⚠️ На сервере кончается место: занято ${used}%. Заказы могут перестать сохраняться."
    fi
else
    rm -f "$STATE.disk"
fi

# ── база цела? ─────────────────────────────────────────
if [ -f "$DB" ] && command -v sqlite3 >/dev/null; then
    if ! sqlite3 "$DB" 'PRAGMA quick_check;' 2>/dev/null | grep -q '^ok$'; then
        say "база повреждена"
        tell "🚨 База данных повреждена. Свежая копия — в /srv/backup."
    fi
fi
