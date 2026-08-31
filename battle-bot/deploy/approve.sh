#!/usr/bin/env bash
# Принять все накопленные заявки в канал — одной командой.
# Ставится как /usr/local/bin/battle-approve.
#
#   sudo battle-approve
#
# Скрипт спросит api_id, api_hash (берутся один раз на https://my.telegram.org)
# и канал, покажет, сколько заявок ждёт, и примет их все.
set -euo pipefail

APP_DIR=/opt/battle-bot
VENV="$APP_DIR/.venv"

if [ ! -d "$VENV" ]; then
    echo "Бот не установлен: нет $VENV" >&2
    exit 1
fi

# telethon нужен только этому инструменту, поэтому ставится по требованию
"$VENV/bin/python" -c "import telethon" 2>/dev/null \
    || "$VENV/bin/pip" install --quiet telethon

exec "$VENV/bin/python" "$APP_DIR/tools/approve_all.py"
