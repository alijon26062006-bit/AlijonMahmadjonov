#!/usr/bin/env bash
# Запуск бота-магазина одной командой.
#   bash start_shop.sh            — запустить сейчас (в терминале)
#   bash start_shop.sh --service  — поставить как службу systemd (автозапуск 24/7)
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
VENV="$ROOT/.venv"
SERVICE_NAME="almaz-shop"

say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }

# ── 1. Python ─────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  err "python3 не найден. Установите: sudo apt update && sudo apt install -y python3 python3-venv"
  exit 1
fi

if ! python3 -c 'import venv' >/dev/null 2>&1; then
  say "Ставлю python3-venv..."
  sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv
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
  if [ "$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then
    err "Для установки службы нужны права root."
    exit 1
  fi
  SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
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
EnvironmentFile=$ROOT/.env
ExecStart=$VENV/bin/python -m shop.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now "$SERVICE_NAME"
  ok "Бот работает как служба и переживёт перезагрузку"
  echo
  echo "  Логи:      journalctl -u $SERVICE_NAME -f"
  echo "  Стоп:      sudo systemctl stop $SERVICE_NAME"
  echo "  Рестарт:   sudo systemctl restart $SERVICE_NAME"
  echo
  $SUDO systemctl --no-pager --lines=15 status "$SERVICE_NAME" || true
  exit 0
fi

# ── 5. Обычный запуск ─────────────────────────────────────────────────
say "Запускаю бота... (остановить — Ctrl+C)"
exec python -m shop.main
