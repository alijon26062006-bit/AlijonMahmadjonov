#!/usr/bin/env bash
# Запуск сервера на своей машине для проверки.
set -euo pipefail
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

export ADMIN_PASSWORD=${ADMIN_PASSWORD:-burger}
export SECRET_KEY=${SECRET_KEY:-$(python3 -c "import secrets; print(secrets.token_hex(32))")}

echo "Админка:  http://127.0.0.1:8000/admin   (пароль: $ADMIN_PASSWORD)"
echo "Меню API: http://127.0.0.1:8000/api/menu"
exec .venv/bin/python -m uvicorn app:app --reload --port 8000
