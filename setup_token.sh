#!/usr/bin/env bash
# Поставить новый токен бота. Все копии со СТАРЫМ токеном сразу перестают работать,
# где бы они ни были (другой сервер, старая установка, чужой компьютер).
#   1) @BotFather → /mybots → бот → API Token → Revoke current token
#   2) bot token            — спросит новый токен (при вводе не виден)
#      bot token 123:ABC... — токен сразу в команде
set -uo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
ENV_FILE="$ROOT/.env"

ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
bad()  { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }
say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }

[ -f "$ENV_FILE" ] || { bad "Файла .env нет — сначала установите бота."; exit 1; }

TOKEN="${1:-}"
if [ -z "$TOKEN" ]; then
  say "Вставьте НОВЫЙ токен от @BotFather и нажмите Enter."
  echo "Токен при вводе не отображается — это нормально."
  read -r -s TOKEN
  echo
fi
TOKEN="$(printf '%s' "$TOKEN" | tr -d '[:space:]')"

if ! printf '%s' "$TOKEN" | grep -Eq '^[0-9]{5,}:[A-Za-z0-9_-]{30,}$'; then
  bad "Это не похоже на токен бота (вид: 123456789:AAH...)."
  exit 1
fi

OLD="$(grep -E '^SHOP_BOT_TOKEN=' "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '[:space:]"'"'")"
if [ "$TOKEN" = "$OLD" ]; then
  bad "Это тот же токен, что уже стоит. Сначала в @BotFather нажмите Revoke и возьмите новый."
  exit 1
fi
# Номер до двоеточия — это сам бот. После Revoke он не меняется.
if [ -n "$OLD" ] && [ "${TOKEN%%:*}" != "${OLD%%:*}" ]; then
  bad "Это токен ДРУГОГО бота (номер ${TOKEN%%:*}, а у вашего ${OLD%%:*})."
  echo "   Покупатели и база привязаны к старому боту. Возьмите новый токен того же бота."
  exit 1
fi

say "Проверяю токен в Telegram..."
if command -v curl >/dev/null 2>&1; then
  RESP="$(curl -sS -m 20 "https://api.telegram.org/bot${TOKEN}/getMe" 2>&1)"
  if printf '%s' "$RESP" | grep -q '"ok":true'; then
    NAME="$(printf '%s' "$RESP" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)"
    ok "Токен рабочий: @${NAME}"
  else
    bad "Telegram не принял токен: $RESP"
    exit 1
  fi
fi

TMP="$(mktemp "$ROOT/.env.XXXXXX")"
grep -v '^SHOP_BOT_TOKEN=' "$ENV_FILE" > "$TMP" || true
printf 'SHOP_BOT_TOKEN=%s\n' "$TOKEN" >> "$TMP"
chmod 600 "$TMP"
mv "$TMP" "$ENV_FILE"
ok "Новый токен записан в .env. Старый больше нигде не работает."
echo

say "Перезапускаю бота с новым токеном..."
exec bot
