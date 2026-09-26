#!/usr/bin/env bash
# Ставит короткую команду `bot`, чтобы больше не помнить длинных команд.
#   bash install_bot_command.sh
set -euo pipefail

ROOT="$(dirname "$(readlink -f "$0")")"
BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
TARGET="/usr/local/bin/bot"
# --no-run: танҳо худи фармонро нав мекунад ва иҷро намешавад.
# Худи `bot` онро ҳангоми навсозӣ даъват мекунад.
QUIET=0
[ "${1:-}" = "--no-run" ] && QUIET=1

# Повторный запуск безопасен: команда просто перезаписывается свежей.
if [ -e "$TARGET" ] && [ "$QUIET" -eq 0 ]; then
  echo "ℹ️  Команда bot уже есть — обновляю её."
fi

if [ "$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then
  echo "❌ Нужны права root." >&2
  exit 1
fi
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

# Файли муваққатӣ: `install` якбора иваз мекунад, бинобар ин `bot`-и корӣ
# ҳангоми навсозии худаш канда намешавад.
STAGED="$(mktemp)"
trap 'rm -f "$STAGED"' EXIT

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
  if bot_alive; then
    OLD_PID="$(cat "$PIDFILE")"
    kill "$OLD_PID" 2>/dev/null
    # Ждём, пока старый процесс выйдет: два бота с одним токеном мешают друг другу.
    for _ in $(seq 1 10); do
      kill -0 "$OLD_PID" 2>/dev/null || break
      sleep 1
    done
  fi
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
  nick)      shift; exec bash "$ROOT/start_nickapi.sh" "$@" ;;
  donatix)   shift; exec bash "$ROOT/setup_donatix.sh" "$@" ;;
  backup)    shift; exec bash "$ROOT/backup_bot.sh" "$@" ;;
  migrate)   shift; exec bash "$ROOT/migrate_bot.sh" "$@" ;;
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
    echo "  bot nick       API проверки ника (--service, --test, --log, --stop)"
    echo "  bot donatix    подключить Donatix для Stars и Premium (off — отключить)"
    echo "  bot backup     собрать архив со всеми данными"
    echo "  bot migrate IP переезд на другой сервер"
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

# Худи фармони `bot` берун аз репозиторий зиндагӣ мекунад, бинобар ин
# онро низ нав мекунем — вагарна фармонҳои нав пайдо намешаванд.
if [ -f "$ROOT/install_bot_command.sh" ]; then
  bash "$ROOT/install_bot_command.sh" --no-run 2>/dev/null \
    && echo "     команда bot обновлена"
fi

echo "2/4  Обновляю зависимости..."
if [ ! -x .venv/bin/pip ]; then
  # На чистом Debian пакета python3-venv нет, и окружение не создаётся.
  if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
    echo "     ставлю python3-venv..."
    PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)"
    $SUDO apt-get update -qq >/dev/null 2>&1
    $SUDO apt-get install -y -qq "python${PYVER}-venv" >/dev/null 2>&1 \
      || $SUDO apt-get install -y -qq python3-venv >/dev/null 2>&1
  fi
  python3 -m venv .venv >/dev/null 2>&1 || {
    echo "❌ Окружение не создалось. Выполните:  apt install -y python3-venv"
    exit 1
  }
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements-shop.txt || { echo "❌ Зависимости не встали"; exit 1; }

echo "3/4  Перезапускаю бота..."
# Запоминаем момент перезапуска: «Бот омода» от ПРЕЖНЕГО запуска не должен
# засчитываться, иначе упавший бот показал бы «✅ ГОТОВО».
SINCE="$(date '+%Y-%m-%d %H:%M:%S')"
LOG_START=0
[ -f "$LOGFILE" ] && LOG_START="$(wc -l < "$LOGFILE")"
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

echo "4/4  Проверяю, что бот действительно поднялся..."

# Бот пишет «Бот омода: @имя», когда связался с Telegram. Ждём именно этого,
# а не просто «процесс ещё жив» — упасть он может и через пару секунд.
ready_marker() {
  if has_systemd; then
    $SUDO journalctl -u "$SERVICE" --since "$SINCE" --no-pager 2>/dev/null \
      | grep -q "Бот омода"
  else
    tail -n "+$((LOG_START + 1))" "$LOGFILE" 2>/dev/null | grep -q "Бот омода"
  fi
}

still_running() {
  if has_systemd; then
    [ "$($SUDO systemctl is-active "$SERVICE" 2>/dev/null)" = "active" ]
  else
    bot_alive
  fi
}

READY=0
for _ in $(seq 1 12); do          # до 24 секунд
  sleep 2
  if ready_marker; then READY=1; break; fi
  still_running || break
done

if [ "$READY" = "1" ]; then
  echo
  echo "✅ ГОТОВО. Бот работает на свежей версии."
  echo "   Логи: bot log"
else
  echo
  echo "❌ Бот НЕ запустился. Последние строки журнала:"
  echo
  if has_systemd; then $SUDO journalctl -u "$SERVICE" -n 25 --no-pager
  else tail -n 25 "$LOGFILE" 2>/dev/null; fi
  exit 1
fi
BODY
} > "$STAGED"

$SUDO install -m 755 "$STAGED" "$TARGET"
rm -f "$STAGED"

if [ "$QUIET" -eq 1 ]; then
  exit 0
fi

echo "✅ Команда установлена: $TARGET"
echo
echo "Теперь из любой папки достаточно набрать:  bot"
echo
exec "$TARGET"
