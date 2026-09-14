#!/usr/bin/env bash
# Добавить админа бота одной командой:
#   bash add_admin.sh 7418217143
# Можно сразу несколько:
#   bash add_admin.sh 7418217143 6488858943
# Убрать админа:
#   bash add_admin.sh --remove 7418217143
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ENV_FILE=".env"
SERVICE_NAME="almaz-shop"
KEY="SHOP_ADMIN_IDS"

ok()  { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
err() { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }

[ -f "$ENV_FILE" ] || { err "Файла .env нет. Сначала: cp .env.shop.example .env"; exit 1; }

REMOVE=0
if [ "${1:-}" = "--remove" ]; then REMOVE=1; shift; fi
[ $# -gt 0 ] || { err "Укажите Telegram ID. Пример: bash add_admin.sh 7418217143"; exit 1; }

for id in "$@"; do
  case "$id" in
    ''|*[!0-9]*) err "«$id» — это не Telegram ID (нужны только цифры)."; exit 1 ;;
  esac
done

current="$(grep -E "^${KEY}=" "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"

# Собираем список без пустых значений и без повторов.
result=""
add_id() {
  local want="$1" item
  for item in ${result//,/ }; do [ "$item" = "$want" ] && return 0; done
  result="${result:+$result,}$want"
}
for item in ${current//,/ }; do
  [ -n "$item" ] || continue
  skip=0
  if [ $REMOVE -eq 1 ]; then
    for id in "$@"; do [ "$item" = "$id" ] && skip=1; done
  fi
  [ $skip -eq 0 ] && add_id "$item"
done
if [ $REMOVE -eq 0 ]; then
  for id in "$@"; do add_id "$id"; done
fi

if [ $REMOVE -eq 1 ] && [ -z "$result" ]; then
  err "Нельзя убрать всех админов — панель станет недоступна."
  exit 1
fi

cp "$ENV_FILE" "${ENV_FILE}.bak"
if grep -qE "^${KEY}=" "$ENV_FILE"; then
  # Пишем через python: значение может содержать что угодно, sed тут ненадёжен.
  python3 - "$ENV_FILE" "$KEY" "$result" <<'PYEOF'
import sys
path, key, value = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(path, encoding="utf-8").read().splitlines(keepends=True)
out = []
for line in lines:
    if line.startswith(key + "="):
        ending = "\n" if line.endswith("\n") else ""
        out.append(f"{key}={value}{ending}")
    else:
        out.append(line)
open(path, "w", encoding="utf-8").writelines(out)
PYEOF
else
  printf '\n%s=%s\n' "$KEY" "$result" >> "$ENV_FILE"
fi

ok "Админы теперь: $result"
echo "   (старый .env сохранён как ${ENV_FILE}.bak)"

if systemctl list-units --all --type=service 2>/dev/null | grep -q "${SERVICE_NAME}.service"; then
  SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
  $SUDO systemctl restart "$SERVICE_NAME"
  ok "Бот перезапущен — зайдите в бота и нажмите /admin"
else
  echo "ℹ️  Служба не установлена: перезапустите бота вручную (Ctrl+C и bash start_shop.sh)"
fi
