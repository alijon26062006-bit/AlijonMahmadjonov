#!/usr/bin/env bash
# API проверки ника — отдельная служба, боту не мешает.
#   bash start_nickapi.sh            запустить сейчас (в терминале)
#   bash start_nickapi.sh --service  поставить службой systemd (24/7)
#   bash start_nickapi.sh --stop     остановить службу
#   bash start_nickapi.sh --log      смотреть логи
#   bash start_nickapi.sh --test     проверить, что отвечает
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
SERVICE="nick-api"
PORT="$(grep -E '^NICK_API_PORT=' "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2 | tr -d ' ')"
PORT="${PORT:-8081}"

if [ "$(id -u)" -eq 0 ]; then SUDO=""
elif command -v sudo >/dev/null 2>&1; then SUDO="sudo"
else SUDO=""; fi

say() { printf '\033[1;36m%s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
err() { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }

# Зависимостей нет вообще — хватит системного python3.
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3 || true)"
[ -n "$PY" ] || { err "python3 не найден"; exit 1; }

has_systemd() { command -v systemctl >/dev/null 2>&1 && systemctl list-units >/dev/null 2>&1; }

case "${1:-}" in
  --stop)
    has_systemd && $SUDO systemctl stop "$SERVICE" 2>/dev/null || true
    pkill -f "nickapi.server" 2>/dev/null || true
    ok "Остановлен"; exit 0 ;;
  --log)
    if has_systemd; then exec $SUDO journalctl -u "$SERVICE" -f
    else exec tail -n 50 -f "$ROOT/data/nickapi.log"; fi ;;
  --test)
    say "Проверяю http://127.0.0.1:$PORT ..."
    KEY="$(grep -E '^NICK_API_TOKEN=' "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2)"
    curl -fsS "http://127.0.0.1:$PORT/health" && echo && ok "Сервис отвечает"
    echo "Список игр:"
    curl -fsS -H "X-Api-Key: $KEY" "http://127.0.0.1:$PORT/games"; echo
    exit 0 ;;
esac

# ── Ключ поставщика ───────────────────────────────────────────────────
if [ -f "$ROOT/.env" ] && ! grep -Eq '^(NICK_API_KEY|SHOP_SUPPLIER_KEY|FIRELOOT_KEY)=[^[:space:]]+' "$ROOT/.env"; then
  err "В .env нет ключа поставщика (NICK_API_KEY или SHOP_SUPPLIER_KEY)."
  exit 1
fi

# Свой ключ доступа: без него API открыт всем, кто знает адрес.
if [ -f "$ROOT/.env" ] && ! grep -q '^NICK_API_TOKEN=' "$ROOT/.env"; then
  TOKEN="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"
  printf '\n# Ключ доступа к API проверки ника (заголовок X-Api-Key)\nNICK_API_TOKEN=%s\n' "$TOKEN" >> "$ROOT/.env"
  ok "Создал ключ доступа NICK_API_TOKEN — он записан в .env"
fi

if [ "${1:-}" = "--service" ]; then
  if ! has_systemd; then
    err "systemd нет — запускайте без --service."
    exit 1
  fi
  say "Ставлю службу $SERVICE..."
  $SUDO tee "/etc/systemd/system/$SERVICE.service" >/dev/null <<UNIT
[Unit]
Description=API проверки игрового ника (FireLoot)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$PY -m nickapi.server
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now "$SERVICE" >/dev/null 2>&1
  sleep 2
  if $SUDO systemctl is-active --quiet "$SERVICE"; then
    ok "Служба работает и переживёт перезагрузку сервера"
    echo
    echo "   Адрес:  http://$(hostname -I 2>/dev/null | awk '{print $1}'):$PORT"
    echo "   Ключ:   $(grep -E '^NICK_API_TOKEN=' "$ROOT/.env" | tail -1 | cut -d= -f2)"
    echo "   Логи:   bash start_nickapi.sh --log"
  else
    err "Служба не поднялась. Логи: journalctl -u $SERVICE -n 30"
    exit 1
  fi
  exit 0
fi

say "Запускаю API проверки ника (Ctrl+C — выход)..."
exec "$PY" -m nickapi.server
