#!/usr/bin/env bash
# Запуск бота-магазина одной командой.
#   bash start_shop.sh            — запустить сейчас (в терминале)
#   bash start_shop.sh --service  — поставить как службу systemd (автозапуск 24/7)
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
VENV="$ROOT/.venv"
SERVICE_NAME="almaz-shop"

# Под root sudo не нужен, а во многих образах Debian его просто нет.
if [ "$(id -u)" -eq 0 ]; then SUDO=""
elif command -v sudo >/dev/null 2>&1; then SUDO="sudo"
else SUDO=""; fi

say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }

# ── 1. Python ─────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  err "python3 не найден. Установите: $SUDO apt update && $SUDO apt install -y python3 python3-venv"
  exit 1
fi

# Пакет называется по версии (python3.11-venv), общего имени может не быть.
if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
  say "Ставлю python3-venv..."
  PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)"
  $SUDO apt-get update -qq >/dev/null 2>&1
  $SUDO apt-get install -y -qq "python${PYVER}-venv" >/dev/null 2>&1 \
    || $SUDO apt-get install -y -qq python3-venv >/dev/null 2>&1
fi

# ── 2. Окружение и зависимости ────────────────────────────────────────
if [ ! -d "$VENV" ]; then
  say "Создаю окружение..."
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
say "Проверяю зависимости..."
pip install -q --upgrade pip
pip install -q -r "$ROOT/requirements-shop.txt"
ok "Зависимости на месте"

# ── 3. Настройки ──────────────────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
  err "Файла .env нет."
  echo "Создайте его: cp .env.shop.example .env && nano .env"
  exit 1
fi
if ! grep -Eq '^SHOP_BOT_TOKEN=[^[:space:]]+' "$ROOT/.env"; then
  err "В .env не заполнен SHOP_BOT_TOKEN."
  exit 1
fi
if ! grep -Eq '^SHOP_ADMIN_IDS=[0-9]' "$ROOT/.env"; then
  err "В .env не заполнен SHOP_ADMIN_IDS (ваш Telegram ID)."
  exit 1
fi
ok "Настройки прочитаны"

# ── 4. Служба systemd (опционально) ───────────────────────────────────
if [ "${1:-}" = "--service" ]; then
  if [ "$(id -u)" -ne 0 ] && [ -z "$SUDO" ]; then
    err "Для установки службы нужны права root, а sudo в системе нет."
    exit 1
  fi
  say "Ставлю службу $SERVICE_NAME..."
  $SUDO tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<UNIT
[Unit]
Description=ALMAZ TJ shop bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$ROOT
ExecStart=$VENV/bin/python -m shop.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable "$SERVICE_NAME" >/dev/null 2>&1
  # Именно restart, а не enable --now: уже запущенная служба иначе
  # продолжила бы крутить старый код.
  $SUDO systemctl restart "$SERVICE_NAME"
  sleep 2
  if [ "$($SUDO systemctl is-active "$SERVICE_NAME" 2>/dev/null)" != "active" ]; then
    err "Служба не поднялась. Причина:"
    $SUDO journalctl -u "$SERVICE_NAME" -n 25 --no-pager || true
    exit 1
  fi
  ok "Бот работает как служба и переживёт перезагрузку"
  echo
  echo "  Логи:      journalctl -u $SERVICE_NAME -f"
  echo "  Стоп:      ${SUDO:+$SUDO }systemctl stop $SERVICE_NAME"
  echo "  Рестарт:   ${SUDO:+$SUDO }systemctl restart $SERVICE_NAME"
  echo
  $SUDO systemctl --no-pager --lines=15 status "$SERVICE_NAME" || true
  exit 0
fi

# ── 5. Обычный запуск ─────────────────────────────────────────────────
say "Запускаю бота... (остановить — Ctrl+C)"
exec python -m shop.main
