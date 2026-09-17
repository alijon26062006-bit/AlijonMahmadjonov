#!/usr/bin/env bash
# Развернуть бота на новом сервере из архива backup_bot.sh.
#   bash restore_bot.sh ~/almaz-backup-20260917-0530.tar.gz
set -uo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
ARCHIVE="${1:-}"

ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
bad()  { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }
say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠️  %s\033[0m\n' "$*"; }

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  bad "Укажите архив: bash restore_bot.sh ~/almaz-backup-ГГГГММДД-ЧЧММ.tar.gz"
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
tar -xzf "$ARCHIVE" -C "$TMP" || { bad "Архив не читается"; exit 1; }
[ -f "$TMP/.env" ] || { bad "В архиве нет .env — это не та резервная копия"; exit 1; }

# Если на этом сервере уже что-то есть — не затираем молча.
if [ -f "$ROOT/.env" ] || [ -f "$ROOT/data/shop.sqlite3" ]; then
  SAVE="$ROOT/before-restore-$(date +%Y%m%d-%H%M)"
  mkdir -p "$SAVE"
  [ -f "$ROOT/.env" ] && cp "$ROOT/.env" "$SAVE/"
  [ -f "$ROOT/data/shop.sqlite3" ] && cp "$ROOT/data/shop.sqlite3" "$SAVE/"
  warn "Здесь уже были данные — сохранил их в $SAVE"
fi

say "Ставлю настройки..."
cp "$TMP/.env" "$ROOT/.env"
chmod 600 "$ROOT/.env"

mkdir -p "$ROOT/data"
if [ -f "$TMP/data/shop.sqlite3" ]; then
  say "Ставлю базу..."
  # Старые WAL-файлы от прежней базы убираем, иначе они перекроют новую.
  rm -f "$ROOT/data/shop.sqlite3-wal" "$ROOT/data/shop.sqlite3-shm"
  cp "$TMP/data/shop.sqlite3" "$ROOT/data/shop.sqlite3"
fi
ok "Данные на месте"

PYBIN="$ROOT/.venv/bin/python"; [ -x "$PYBIN" ] || PYBIN="python3"
if [ -f "$ROOT/data/shop.sqlite3" ]; then
  "$PYBIN" - "$ROOT/data/shop.sqlite3" <<'PYEOF'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
def n(table):
    try: return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception: return 0
money = con.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]
print(f"   Перенесено: пользователей {n('users')}, партнёров {n('partners')},")
print(f"               заказов {n('orders')}, платежей {n('topups')},")
print(f"               на счетах {money/100:.2f} с.")
PYEOF
fi

echo
say "Запускаю бота..."
exec bash "$ROOT/install_bot_command.sh"
