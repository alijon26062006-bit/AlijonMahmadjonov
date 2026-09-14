#!/usr/bin/env bash
# Обновить бота до свежей версии и перезапустить — одной командой.
#   bash update_shop.sh
set -uo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
SERVICE_NAME="almaz-shop"
BRANCH="${SHOP_BRANCH:-claude/telegram-digital-sales-bot-jaubw5}"

if [ "$(id -u)" -eq 0 ]; then SUDO=""
elif command -v sudo >/dev/null 2>&1; then SUDO="sudo"
else SUDO=""; fi

say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠️  %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }

git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 || { err "Это не git-папка: $ROOT"; exit 1; }

NOW="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)"
say "Сейчас ветка: $NOW"
say "Нужна ветка:  $BRANCH"

# Незакоммиченные правки в отслеживаемых файлах не трогаем — иначе потеряются.
DIRTY="$(git -C "$ROOT" status --porcelain --untracked-files=no)"
if [ -n "$DIRTY" ]; then
  warn "В папке есть изменённые файлы — обновление их затрёт:"
  echo "$DIRTY" | sed 's/^/   /'
  echo
  echo "Сохранить их:  git stash"
  echo "Выбросить:     git checkout -- ."
  err "Обновление остановлено, чтобы ничего не потерять."
  exit 1
fi

say "Забираю свежую версию..."
for attempt in 1 2 3 4; do
  git -C "$ROOT" fetch origin "$BRANCH" && break
  warn "Сеть не ответила (попытка $attempt). Жду..."
  sleep $((attempt * 2))
done

git -C "$ROOT" rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1 || {
  err "Ветки origin/$BRANCH нет. Проверьте имя ветки."
  exit 1
}

if [ "$NOW" != "$BRANCH" ]; then
  say "Перехожу на ветку $BRANCH..."
  git -C "$ROOT" checkout -B "$BRANCH" --track "origin/$BRANCH" || {
    err "Не удалось переключиться на $BRANCH"; exit 1; }
else
  git -C "$ROOT" merge --ff-only "origin/$BRANCH" || {
    err "Ветка разошлась с origin. Ручное решение: git reset --hard origin/$BRANCH"
    exit 1; }
fi
ok "Код обновлён: $(git -C "$ROOT" log --oneline -1)"

# Зависимости могли поменяться
if [ -d "$ROOT/.venv" ]; then
  say "Проверяю зависимости..."
  "$ROOT/.venv/bin/pip" install -q --upgrade pip
  "$ROOT/.venv/bin/pip" install -q -r "$ROOT/requirements-shop.txt" && ok "Зависимости на месте"
else
  warn "Окружения .venv нет — запустите bash start_shop.sh"
fi

[ -f "$ROOT/.env" ] || { err "Файла .env нет. Сначала: cp .env.shop.example .env && nano .env"; exit 1; }

# Перезапуск
if systemctl list-units --all --type=service 2>/dev/null | grep -q "${SERVICE_NAME}.service"; then
  say "Перезапускаю службу..."
  $SUDO systemctl restart "$SERVICE_NAME"
  sleep 2
  if [ "$($SUDO systemctl is-active "$SERVICE_NAME" 2>/dev/null)" = "active" ]; then
    ok "Бот работает на свежей версии"
    echo "   Логи: journalctl -u $SERVICE_NAME -f"
  else
    err "Служба не поднялась. Смотрите: journalctl -u $SERVICE_NAME -n 40 --no-pager"
    exit 1
  fi
else
  warn "Служба не установлена."
  echo "   Запустить сейчас:        bash start_shop.sh"
  echo "   Поставить на автозапуск: bash start_shop.sh --service"
fi
