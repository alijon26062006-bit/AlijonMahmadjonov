#!/usr/bin/env bash
# Диагностика: почему бот ведёт себя не так, как ждёшь.
#   bash check_shop.sh
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
SERVICE_NAME="almaz-shop"

ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠️  %s\033[0m\n' "$*"; }
bad()  { printf '\033[1;31m❌ %s\033[0m\n' "$*"; }
hdr()  { printf '\n\033[1;36m── %s ─────────────────────────\033[0m\n' "$*"; }

hdr "Папка и код"
echo "Проект: $ROOT"
BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)"
WANT="claude/telegram-digital-sales-bot-jaubw5"
if [ -n "$BRANCH" ] && [ "$BRANCH" != "$WANT" ]; then
  bad "Вы на ветке «$BRANCH», а бот живёт в «$WANT» — обновления сюда не приходят!"
  echo "   Лечится так: bash update_shop.sh"
fi
if [ -d "$ROOT/shop" ]; then ok "Новый бот (папка shop/) на месте"; else bad "Папки shop/ нет — вы не в том каталоге"; fi
git -C "$ROOT" log --oneline -1 2>/dev/null | sed 's/^/Последний коммит: /'
git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null | sed 's/^/Ветка: /'

hdr "Файл .env"
if [ ! -f "$ROOT/.env" ]; then
  bad "Файла .env НЕТ. Создайте: cp .env.shop.example .env"
  exit 1
fi
ok "Файл .env найден"
TOKEN_LINE="$(grep -E '^SHOP_BOT_TOKEN=' "$ROOT/.env" | head -n1 | cut -d= -f2-)"
if [ -z "$TOKEN_LINE" ]; then bad "SHOP_BOT_TOKEN пустой"; else
  echo "Токен: ...${TOKEN_LINE: -6} (показаны последние 6 знаков)"
fi
grep -E '^SHOP_ADMIN_IDS=' "$ROOT/.env" | sed 's/^/Строка в .env: /' || bad "Строки SHOP_ADMIN_IDS нет вообще"

hdr "Как эти настройки читает сам бот"
PYBIN="$ROOT/.venv/bin/python"; [ -x "$PYBIN" ] || PYBIN="python3"
"$PYBIN" - <<'PYEOF'
import sys
sys.path.insert(0, ".")
try:
    from shop.config import load_config
    cfg = load_config()
except Exception as exc:
    print(f"\033[1;31m❌ Настройки прочитать не удалось: {exc}\033[0m")
    sys.exit(1)
if cfg.admin_ids:
    print(f"\033[1;32m✅ Админы, которых видит бот: {', '.join(map(str, cfg.admin_ids))}\033[0m")
else:
    print("\033[1;31m❌ Список админов ПУСТОЙ — панель не откроется никому\033[0m")
print(f"Поставщик: {cfg.supplier} | ключ {'есть' if cfg.supplier_key else 'ПУСТОЙ'} | автовыдача: {'да' if cfg.has_supplier else 'нет'}")
print(f"База: {cfg.db_path}")
PYEOF

hdr "Кто такой этот бот в Telegram"
if [ -n "$TOKEN_LINE" ]; then
  RESP="$(curl -s --max-time 15 "https://api.telegram.org/bot${TOKEN_LINE}/getMe" || true)"
  case "$RESP" in
    *'"ok":true'*)
      NAME="$(printf '%s' "$RESP" | sed -n 's/.*"username":"\([^"]*\)".*/\1/p')"
      ok "Токен рабочий — это бот @${NAME}"
      echo "   Проверьте: вы пишете именно @${NAME}, а не другому боту."
      ;;
    *'"ok":false'*) bad "Telegram отверг токен: $RESP" ;;
    *) warn "Telegram не ответил (сеть). Ответ: ${RESP:-пусто}" ;;
  esac
fi

hdr "Запущен ли бот"
if systemctl list-units --all --type=service 2>/dev/null | grep -q "${SERVICE_NAME}.service"; then
  STATE="$(systemctl is-active "$SERVICE_NAME" 2>/dev/null)"
  if [ "$STATE" = "active" ]; then ok "Служба $SERVICE_NAME работает"; else bad "Служба $SERVICE_NAME в состоянии: $STATE"; fi
  systemctl show "$SERVICE_NAME" -p WorkingDirectory 2>/dev/null | sed 's/^/Рабочая папка службы: /'
else
  warn "Служба не установлена (это нормально, если запускаете руками)"
fi

# Ищем именно процесс python, а не оболочку, которая упоминает это в тексте.
RUNNING="$(pgrep -af 'shop\.main' 2>/dev/null | grep -E '(^|/)[0-9]+ .*python' | grep -v -E 'bash|check_shop' || true)"
[ -n "$RUNNING" ] && ok "Процесс нового бота найден:" && echo "$RUNNING" | sed 's/^/   /'
[ -z "$RUNNING" ] && warn "Процесс 'python -m shop.main' не найден — новый бот сейчас не запущен"

OLD="$(pgrep -af python 2>/dev/null | grep -v 'shop\.main' | grep -v -E 'bash|check_shop|pytest' | grep -Ei 'bot|main\.py' || true)"
if [ -n "$OLD" ]; then
  warn "Работают и ДРУГИЕ python-боты — возможно, вы пишете старому боту:"
  echo "$OLD" | sed 's/^/   /'
fi

hdr "Что делать"
echo "1. Напишите боту /id — он ответит вашим настоящим Telegram ID."
echo "2. Сверьте его со списком админов выше."
echo "3. Не совпал — выполните: bash add_admin.sh <ваш_id>"
echo "4. Совпал, а панели нет — обновитесь и перезапуститесь: bash update_shop.sh"
