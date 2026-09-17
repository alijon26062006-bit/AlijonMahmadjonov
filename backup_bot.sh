#!/usr/bin/env bash
# Собрать архив со ВСЕМИ данными бота: настройки и база.
#   bash backup_bot.sh            → архив в домашней папке
#   bash backup_bot.sh /путь      → архив в указанной папке
set -uo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
OUT_DIR="${1:-$HOME}"
STAMP="$(date +%Y%m%d-%H%M)"
ARCHIVE="$OUT_DIR/almaz-backup-$STAMP.tar.gz"

ok()  { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
bad() { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }

[ -f "$ROOT/.env" ] || { bad "Файла .env нет — переносить нечего."; exit 1; }

PYBIN="$ROOT/.venv/bin/python"; [ -x "$PYBIN" ] || PYBIN="python3"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/data"

say "Копирую настройки..."
cp "$ROOT/.env" "$TMP/.env"

DB="$ROOT/data/shop.sqlite3"
if [ -f "$DB" ]; then
  say "Снимаю копию базы (бот можно не останавливать)..."
  # Родное копирование SQLite: целостный снимок даже во время работы бота.
  "$PYBIN" - "$DB" "$TMP/data/shop.sqlite3" <<'PYEOF'
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
src.close(); dst.close()
PYEOF
  [ $? -eq 0 ] || { bad "Базу скопировать не удалось"; exit 1; }
else
  say "Базы ещё нет — переносим только настройки."
fi

tar -czf "$ARCHIVE" -C "$TMP" . || { bad "Архив не собрался"; exit 1; }
chmod 600 "$ARCHIVE"

SIZE="$(du -h "$ARCHIVE" | cut -f1)"
ok "Архив готов: $ARCHIVE  ($SIZE)"

if [ -f "$TMP/data/shop.sqlite3" ]; then
  "$PYBIN" - "$TMP/data/shop.sqlite3" <<'PYEOF'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1]); con.row_factory = sqlite3.Row
def n(table):
    try: return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception: return 0
money = con.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]
print(f"   Внутри: пользователей {n('users')}, из них партнёров {n('partners')}")
print(f"           заказов {n('orders')}, платежей {n('topups')}, отзывов {n('reviews')}")
print(f"           на счетах {money/100:.2f} с., каналов подписки {n('channels')}")
PYEOF
fi

echo
echo "⚠️  В архиве токен бота и ключ поставщика — не выкладывайте его никуда."
echo
echo "Перенести на новый сервер:"
echo "   scp $ARCHIVE root@НОВЫЙ_СЕРВЕР:~/"
