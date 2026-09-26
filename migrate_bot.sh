#!/usr/bin/env bash
# Переезд на другой сервер одной командой.
#   bash migrate_bot.sh 144.31.234.103
#   bash migrate_bot.sh root@144.31.234.103
#
# Порядок важен: сначала БОТ ОСТАНАВЛИВАЕТСЯ, и только потом снимается копия.
# Иначе покупки и пополнения, сделанные между копией и переездом, потерялись бы.
set -uo pipefail

cd "$(dirname "$(readlink -f "$0")")"
ROOT="$(pwd)"
SERVICE="almaz-shop"
PIDFILE="$ROOT/data/bot.pid"
TARGET_RAW="${1:-}"

if [ "$(id -u)" -eq 0 ]; then SUDO=""
elif command -v sudo >/dev/null 2>&1; then SUDO="sudo"
else SUDO=""; fi

ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
bad()  { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }
say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠️  %s\033[0m\n' "$*"; }

if [ -z "$TARGET_RAW" ]; then
  bad "Укажите адрес нового сервера:  bash migrate_bot.sh 144.31.234.103"
  exit 1
fi
case "$TARGET_RAW" in
  *@*) TARGET="$TARGET_RAW" ;;
  *)   TARGET="root@$TARGET_RAW" ;;
esac
HOST="${TARGET#*@}"

has_systemd() {
  command -v systemctl >/dev/null 2>&1 && systemctl list-units >/dev/null 2>&1
}

start_bot() {
  if has_systemd; then
    $SUDO systemctl start "$SERVICE" >/dev/null 2>&1
  elif [ -x "$ROOT/.venv/bin/python" ]; then
    mkdir -p "$ROOT/data"
    nohup "$ROOT/.venv/bin/python" -m shop.main >>"$ROOT/data/bot.log" 2>&1 &
    echo $! > "$PIDFILE"
  fi
}

stop_bot() {
  if has_systemd; then
    $SUDO systemctl stop "$SERVICE" >/dev/null 2>&1
  elif [ -f "$PIDFILE" ]; then
    OLD_PID="$(cat "$PIDFILE")"
    kill "$OLD_PID" 2>/dev/null
    # Копию снимаем только когда процесс точно вышел — иначе он успел бы
    # записать в базу покупку уже после копии, и она потерялась бы.
    for _ in $(seq 1 15); do
      kill -0 "$OLD_PID" 2>/dev/null || break
      sleep 1
    done
    rm -f "$PIDFILE"
  fi
}

# Если дальше что-то сорвётся — бот не должен остаться выключенным.
RESTORE_ON_FAIL=0
bot_running() {
  if has_systemd; then
    [ "$($SUDO systemctl is-active "$SERVICE" 2>/dev/null)" = "active" ]
  else
    [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
  fi
}

cleanup() {
  if [ "$RESTORE_ON_FAIL" = "1" ]; then
    warn "Переезд не завершён — возвращаю старого бота в работу."
    start_bot
    sleep 3
    if bot_running; then
      ok "Старый бот снова работает. Данные на месте, ничего не потеряно."
    else
      # Молчать нельзя: магазин стоит, а владелец об этом не знает.
      bad "БОТ НЕ ЗАПУСТИЛСЯ САМ! Магазин сейчас не работает."
      echo "   Запустите вручную:  bot start"
      echo "   Если не поможет:    bot log   — покажет причину"
    fi
  fi
}
trap cleanup EXIT

echo
say "════ ПЕРЕЕЗД НА $HOST ════"
echo

# ── 0. Всё проверяем ДО остановки — магазин зря стоять не должен ──────
say "0/5  Проверяю, что переезд возможен..."
for tool in scp ssh sha256sum tar; do
  command -v "$tool" >/dev/null 2>&1 || {
    bad "Нет программы «$tool». Поставьте: apt update && apt install -y openssh-client coreutils tar"
    exit 1
  }
done
[ -f "$ROOT/.env" ] || { bad "Файла .env нет — переносить нечего."; exit 1; }
[ -f "$ROOT/backup_bot.sh" ] || { bad "Нет backup_bot.sh — обновитесь: bot"; exit 1; }
if ! ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o BatchMode=yes \
        "$TARGET" true >/dev/null 2>&1; then
  # Пароль по ssh-ключу не подошёл — это нормально, спросим пароль позже.
  if ! timeout 15 bash -c "</dev/tcp/$HOST/22" 2>/dev/null; then
    bad "Сервер $HOST по ssh не отвечает. Проверьте адрес и что сервер включён."
    exit 1
  fi
fi
ok "Всё на месте, сервер отвечает"
echo

# ── 1. Останавливаем бота ─────────────────────────────────────────────
say "1/5  Останавливаю бота, чтобы данные перестали меняться..."
stop_bot
RESTORE_ON_FAIL=1
sleep 2
ok "Бот остановлен — с этой секунды база неподвижна"

# ── 2. Свежая копия ───────────────────────────────────────────────────
say "2/5  Снимаю копию всех данных..."
BACKUP_OUT="$(bash "$ROOT/backup_bot.sh" "$HOME" 2>&1)"
echo "$BACKUP_OUT" | grep -E "Внутри:|пользователей|заказов|на счетах" | sed 's/^/     /'
ARCHIVE="$(echo "$BACKUP_OUT" | grep -oE '/[^ ]*almaz-backup-[0-9-]*\.tar\.gz' | head -1)"
if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  bad "Копию снять не удалось:"
  echo "$BACKUP_OUT"
  exit 1
fi
ok "Копия готова: $(basename "$ARCHIVE")"

# ── 3. Передаём ───────────────────────────────────────────────────────
echo
say "3/5  Передаю на новый сервер..."
warn "Сейчас спросит пароль от $HOST (пароль не отображается — печатайте вслепую)"
echo
if ! scp -o StrictHostKeyChecking=accept-new "$ARCHIVE" "$TARGET:~/"; then
  bad "Передать не удалось. Проверьте адрес и пароль."
  exit 1
fi
ok "Файл на новом сервере"

# ── 4. Сверяем, что файл доехал целым ─────────────────────────────────
echo
say "4/5  Проверяю, что файл доехал без повреждений..."
LOCAL_SUM="$(sha256sum "$ARCHIVE" | cut -d' ' -f1)"
REMOTE_SUM="$(ssh -o StrictHostKeyChecking=accept-new "$TARGET" \
  "sha256sum ~/$(basename "$ARCHIVE") 2>/dev/null | cut -d' ' -f1" 2>/dev/null)"
if [ -z "$REMOTE_SUM" ]; then
  warn "Проверить не удалось (нет доступа по ssh) — продолжайте, но сверьте цифры вручную."
elif [ "$LOCAL_SUM" != "$REMOTE_SUM" ]; then
  bad "Файл доехал повреждённым! Повторите переезд."
  exit 1
else
  ok "Файл целый, совпадает до байта"
fi

# ── 5. Что делать дальше ──────────────────────────────────────────────
RESTORE_ON_FAIL=0

# Старый бот не должен ожить: ни после перезагрузки, ни от случайного `bot`.
# Две копии с одной базой делят покупателей и шлют поставщику одинаковые номера.
if has_systemd; then
  $SUDO systemctl disable "$SERVICE" >/dev/null 2>&1
fi
echo "$HOST $(date '+%Y-%m-%d %H:%M')" > "$ROOT/data/MOVED_TO"
ok "Старый бот выключен насовсем (автозапуск снят)"

BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
REPO="$(git -C "$ROOT" remote get-url origin 2>/dev/null)"
NAME="$(basename "$ARCHIVE")"

echo
say "5/5  Осталось запустить на новом сервере."
echo
echo "Скопируйте эти две команды по очереди:"
echo
printf '\033[1;33m  ssh %s\033[0m\n' "$TARGET"
echo
# Папка может уже быть (прошлая попытка) — тогда не клонируем, а обновляем.
printf '\033[1;33m  apt-get install -y -qq git python3-venv >/dev/null; cd ~ && { [ -d AlijonMahmadjonov ] || git clone -b %s %s AlijonMahmadjonov; } && cd AlijonMahmadjonov && git fetch origin %s && git checkout -f -B %s FETCH_HEAD && bash restore_bot.sh ~/%s\033[0m\n' \
  "$BRANCH" "$REPO" "$BRANCH" "$BRANCH" "$NAME"
echo
warn "Старый бот ВЫКЛЮЧЕН насовсем — так данные не разойдутся."
echo "   Если переезд не получится, вернуть старый:"
echo "   rm $ROOT/data/MOVED_TO && systemctl enable $SERVICE; bot start"
echo
