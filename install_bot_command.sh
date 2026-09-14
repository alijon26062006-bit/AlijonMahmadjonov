#!/usr/bin/env bash
# Ставит короткую команду `bot`, чтобы больше не помнить длинных команд.
#   bash install_bot_command.sh
set -euo pipefail

ROOT="$(dirname "$(readlink -f "$0")")"
BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
TARGET="/usr/local/bin/bot"

if [ "$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then
  echo "❌ Нужны права root." >&2
  exit 1
fi
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

{
  echo '#!/usr/bin/env bash'
  echo "# Управление ботом. Создано install_bot_command.sh — вручную не правьте."
  echo "ROOT=\"$ROOT\""
  echo "BRANCH=\"$BRANCH\""
  cat <<'BODY'
SERVICE="almaz-shop"
PIDFILE="$ROOT/data/bot.pid"
LOGFILE="$ROOT/data/bot.log"
set -uo pipefail

if [ "$(id -u)" -eq 0 ]; then SUDO=""
elif command -v sudo >/dev/null 2>&1; then SUDO="sudo"
else SUDO=""; fi

cd "$ROOT" 2>/dev/null || { echo "❌ Папка $ROOT пропала"; exit 1; }

# На части серверов systemd нет — тогда запускаем бота обычным процессом.
has_systemd() {
  command -v systemctl >/dev/null 2>&1 && systemctl list-units >/dev/null 2>&1
}

bot_alive() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
}

plain_stop() {
  bot_alive && kill "$(cat "$PIDFILE")" 2>/dev/null
  rm -f "$PIDFILE"
}

plain_start() {
  mkdir -p "$ROOT/data"
  nohup "$ROOT/.venv/bin/python" -m shop.main >>"$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
}

case "${1:-update}" in
  log|logs)
    if has_systemd; then exec $SUDO journalctl -u "$SERVICE" -f
    else exec tail -n 50 -f "$LOGFILE"; fi ;;
  stop)
    if has_systemd; then $SUDO systemctl stop "$SERVICE"; else plain_stop; fi
    echo "⏹  Бот остановлен"; exit ;;
  start)
    if has_systemd; then $SUDO systemctl start "$SERVICE"; else plain_start; fi
    echo "▶️  Бот запущен"; exit ;;
  check)     exec bash "$ROOT/check_shop.sh" ;;
  admin)     shift; exec bash "$ROOT/add_admin.sh" "$@" ;;
  api)       shift; exec bash "$ROOT/check_api.sh" "$@" ;;
  force)     FORCE=1 ;;
  update|"") FORCE=0 ;;
  *)
    echo "Команды:"
    echo "  bot            обновить код и перезапустить"
    echo "  bot log        смотреть логи (выход — Ctrl+C)"
    echo "  bot stop       остановить"
    echo "  bot start      запустить"
    echo "  bot check      диагностика"
    echo "  bot admin ID   сделать админом"
    echo "  bot api        проверить поставщика"
    echo "  bot force      обновить, стерев свои правки в коде"
    exit 0 ;;
esac

echo "1/4  Забираю свежий код..."
git fetch origin "$BRANCH" || { echo "❌ Нет связи с GitHub"; exit 1; }
if [ "${FORCE:-0}" = "1" ]; then
  git checkout -B "$BRANCH" >/dev/null 2>&1
  git reset --hard FETCH_HEAD >/dev/null || exit 1
elif ! git checkout -B "$BRANCH" FETCH_HEAD >/dev/null 2>&1; then
  echo "❌ Мешают ваши правки в файлах кода."
  git status --porcelain --untracked-files=no | sed 's/^/     /'
  echo "   Стереть их и обновиться:  bot force"
  exit 1
fi
echo "     $(git log --oneline -1)"

echo "2/4  Обновляю зависимости..."
[ -x .venv/bin/pip ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements-shop.txt || { echo "❌ Зависимости не встали"; exit 1; }

echo "3/4  Перезапускаю бота..."
if has_systemd; then
  if systemctl list-units --all --type=service 2>/dev/null | grep -q "${SERVICE}.service"; then
    $SUDO systemctl restart "$SERVICE"
  else
    bash "$ROOT/start_shop.sh" --service >/dev/null || { echo "❌ Не удалось поставить службу"; exit 1; }
  fi
else
  plain_stop
  plain_start
fi
sleep 3

echo "4/4  Проверяю..."
if has_systemd; then
  RUNNING=$([ "$($SUDO systemctl is-active "$SERVICE" 2>/dev/null)" = "active" ] && echo 1 || echo 0)
else
  RUNNING=$(bot_alive && echo 1 || echo 0)
fi

if [ "$RUNNING" = "1" ]; then
  echo
  echo "✅ ГОТОВО. Бот работает на свежей версии."
  echo "   Логи: bot log"
else
  echo
  echo "❌ Бот не запустился. Причина:"
  if has_systemd; then $SUDO journalctl -u "$SERVICE" -n 25 --no-pager
  else tail -n 25 "$LOGFILE" 2>/dev/null; fi
  exit 1
fi
BODY
} | $SUDO tee "$TARGET" >/dev/null

$SUDO chmod +x "$TARGET"
echo "✅ Команда установлена: $TARGET"
echo
echo "Теперь из любой папки достаточно набрать:  bot"
echo
exec "$TARGET"
