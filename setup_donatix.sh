#!/usr/bin/env bash
# Подключить Donatix: Telegram Stars и Premium пойдут через него.
#   bot donatix              — спросит ключ (его не видно при вводе)
#   bot donatix dx_live_...  — ключ сразу в команде
#   bot donatix off          — отключить, Stars снова через FireLoot
set -uo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
ENV_FILE="$ROOT/.env"
URL="https://donatix.tj/api/v1"

ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
bad()  { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }
say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }

[ -f "$ENV_FILE" ] || { bad "Файла .env нет — сначала установите бота."; exit 1; }

set_key() {
  # Меняем строку, если есть, иначе дописываем. Файл пишем атомарно.
  local tmp
  tmp="$(mktemp "$ROOT/.env.XXXXXX")"
  grep -v '^SHOP_DONATIX_KEY=' "$ENV_FILE" > "$tmp" || true
  if [ -n "$1" ]; then
    printf '\n# Donatix — Telegram Stars и Premium\nSHOP_DONATIX_KEY=%s\n' "$1" >> "$tmp"
  fi
  chmod 600 "$tmp"
  mv "$tmp" "$ENV_FILE"
}

if [ "${1:-}" = "off" ]; then
  set_key ""
  ok "Donatix отключён. Stars — через FireLoot, Premium — вручную."
  exec bot
fi

KEY="${1:-}"
if [ -z "$KEY" ]; then
  say "Вставьте ключ Donatix (dx_live_...) и нажмите Enter."
  echo "Ключ при вводе не отображается — это нормально."
  read -r -s KEY
  echo
fi
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"

case "$KEY" in
  dx_*) ;;
  *) bad "Это не похоже на ключ Donatix (должен начинаться с dx_)."; exit 1 ;;
esac

say "Проверяю ключ..."
if command -v curl >/dev/null 2>&1; then
  RESP="$(curl -sS -m 20 -w '\n%{http_code}' "$URL/balance" -H "X-API-Key: $KEY" 2>&1)"
  CODE="$(printf '%s' "$RESP" | tail -n 1)"
  BODY="$(printf '%s' "$RESP" | sed '$d')"
  case "$CODE" in
    200) ok "Ключ рабочий: $BODY" ;;
    401|403) bad "Donatix не принял ключ ($CODE): $BODY"; exit 1 ;;
    *) bad "Donatix не ответил как надо ($CODE): $BODY"
       echo "   Ключ всё равно сохраню — проверьте позже: bot api"
       ;;
  esac
fi

set_key "$KEY"
ok "Ключ записан в .env (в git он не попадает)."
echo

say "Перезапускаю бота..."
bot || exit 1
echo
say "Как бот будет продавать Stars и Premium:"
bash "$ROOT/check_api.sh"
