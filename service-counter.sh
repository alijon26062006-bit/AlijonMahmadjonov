#!/usr/bin/env bash
# Автозапуск счётчика: бот работает круглосуточно и сам поднимается
# после перезагрузки сервера и после любого сбоя.
#
#   bash service-counter.sh            — включить автозапуск
#   bash service-counter.sh status     — работает или нет
#   bash service-counter.sh logs       — смотреть, что происходит
#   bash service-counter.sh restart    — перезапустить
#   bash service-counter.sh stop       — остановить (автозапуск остаётся)
#   bash service-counter.sh remove     — убрать автозапуск совсем
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

BOLD=$'\033[1m'; DIM=$'\033[90m'; GREEN=$'\033[32m'; RED=$'\033[31m'; OFF=$'\033[0m'
say()  { printf '%s\n' "$*"; }
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$OFF" "$*"; }
bad()  { printf '  %s✗%s %s\n' "$RED" "$OFF" "$*" >&2; }
hint() { printf '  %s%s%s\n' "$DIM" "$*" "$OFF"; }
die()  { bad "$*"; exit 1; }

SERVICE="schetchik"
UNIT="/etc/systemd/system/${SERVICE}.service"
PROJECT="$PWD"
PYTHON="$PROJECT/.venv/bin/python"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 && SUDO="sudo"
fi

have_systemd() { command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; }

no_systemd_advice() {
  say ""
  say "${BOLD}На этом сервере нет systemd.${OFF} Тогда запускай так, чтобы бот"
  say "не умирал при выходе из SSH:"
  say ""
  say "    cd $PROJECT"
  say "    nohup .venv/bin/python -m counter > counter.log 2>&1 &"
  say ""
  hint "Посмотреть, что происходит:  tail -f $PROJECT/counter.log"
  hint "Остановить:                  pkill -f 'python -m counter'"
  hint "Минус способа: после перезагрузки сервера надо запустить заново."
}

case "${1:-install}" in
  status)
    have_systemd || { no_systemd_advice; exit 0; }
    $SUDO systemctl status "$SERVICE" --no-pager || true
    exit 0
    ;;
  logs)
    have_systemd || { tail -f "$PROJECT/counter.log"; exit 0; }
    $SUDO journalctl -u "$SERVICE" -n 100 -f
    exit 0
    ;;
  restart)
    have_systemd || die "Нет systemd — перезапусти вручную."
    $SUDO systemctl restart "$SERVICE" && ok "Перезапущен"
    exit 0
    ;;
  stop)
    have_systemd || { pkill -f "python -m counter" || true; ok "Остановлен"; exit 0; }
    $SUDO systemctl stop "$SERVICE" && ok "Остановлен (автозапуск остался)"
    exit 0
    ;;
  remove)
    have_systemd || die "Нет systemd — нечего убирать."
    $SUDO systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
    $SUDO rm -f "$UNIT"
    $SUDO systemctl daemon-reload
    ok "Автозапуск убран. Бот больше сам не стартует."
    exit 0
    ;;
  install) ;;
  *) die "Не знаю команду «$1». Есть: install, status, logs, restart, stop, remove" ;;
esac

# ── Установка автозапуска ──────────────────────────────────────────────────
say ""
say "${BOLD}Автозапуск счётчика товаров${OFF}"
hint "Бот будет работать круглосуточно, даже когда ты закроешь SSH."

[ -x "$PYTHON" ] || die "Нет $PYTHON. Сначала выполни: bash setup-counter.sh"
grep -q '^COUNTER_BOT_TOKEN=.\+' .env 2>/dev/null \
  || die "В .env нет токена бота. Сначала выполни: bash setup-counter.sh"

have_systemd || { no_systemd_advice; exit 0; }

# Один и тот же бот нельзя опрашивать дважды: Телеграм ответит ошибкой 409.
# Поэтому глушим всё, что уже запущено руками.
if pgrep -f "python -m counter" >/dev/null 2>&1; then
  hint "Останавливаю бота, запущенного вручную…"
  pkill -f "python -m counter" || true
  sleep 2
fi

RUN_USER="${SUDO_USER:-$(id -un)}"

$SUDO tee "$UNIT" >/dev/null <<UNITFILE
[Unit]
Description=Счётчик товаров (телеграм-бот)
Documentation=file://$PROJECT/SCHETCHIK.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$PROJECT
ExecStart=$PYTHON -m counter
# Упал, потерялась сеть, перезагрузили сервер — поднимется сам.
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNITFILE

ok "Настройка записана: $UNIT"

$SUDO systemctl daemon-reload
$SUDO systemctl enable "$SERVICE" >/dev/null 2>&1
$SUDO systemctl restart "$SERVICE"
ok "Автозапуск включён"

sleep 3
if $SUDO systemctl is-active --quiet "$SERVICE"; then
  ok "Бот работает"
  say ""
  say "${BOLD}Готово.${OFF} Теперь можно спокойно закрывать SSH."
  hint "Проверить:     bash service-counter.sh status"
  hint "Смотреть логи: bash service-counter.sh logs"
  hint "Перезапустить: bash service-counter.sh restart"
  say ""
else
  bad "Бот не поднялся. Вот последние строки лога:"
  say ""
  $SUDO journalctl -u "$SERVICE" -n 30 --no-pager || true
  say ""
  hint "Чаще всего дело в токене или голосовой модели."
  hint "Проверь: $PYTHON -m counter.selftest"
  exit 1
fi
