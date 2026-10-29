#!/usr/bin/env bash
# Установка бота курса одной командой на чистом сервере (Ubuntu/Debian):
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/refs/heads/claude/python-reels/course_bot/install.sh | sudo bash
#
# Скачивает код, ставит всё нужное, спрашивает токен бота, просит нажать «Старт»
# (так бот узнаёт владельца) и включает автозапуск.
set -euo pipefail

REPO="https://github.com/alijon26062006-bit/AlijonMahmadjonov.git"
BRANCH="${COURSEBOT_BRANCH:-claude/python-reels}"
DIR="${COURSEBOT_DIR:-$HOME/coursebot}"

BOLD=$'\033[1m'; DIM=$'\033[90m'; GREEN=$'\033[32m'; RED=$'\033[31m'; OFF=$'\033[0m'
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$OFF" "$*"; }
die()  { printf '  %s✗%s %s\n' "$RED" "$OFF" "$*" >&2; exit 1; }
hint() { printf '  %s%s%s\n' "$DIM" "$*" "$OFF"; }

# Чужой PYTHONPATH (бывает на хостингах) подмешивает в .venv посторонние папки.
unset PYTHONPATH

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 && SUDO="sudo"
fi

printf '\n%sУстановка бота курса «Python с нуля»%s\n' "$BOLD" "$OFF"
hint "Займёт 1–2 минуты. В конце спрошу токен бота."

# ── программы ──────────────────────────────────────────────────────────────
NEEDED=()
command -v git >/dev/null 2>&1 || NEEDED+=("git")
command -v python3 >/dev/null 2>&1 || NEEDED+=("python3")
python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || NEEDED+=("python3-venv")
if [ ${#NEEDED[@]} -gt 0 ]; then
  hint "Ставлю: ${NEEDED[*]}"
  command -v apt-get >/dev/null 2>&1 || die "Поставьте вручную: ${NEEDED[*]}"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq "${NEEDED[@]}" >/dev/null
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Нужен Python 3.10 или новее."
ok "Программы на месте"

# ── код ────────────────────────────────────────────────────────────────────
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch -q --depth 1 origin "$BRANCH"
  git -C "$DIR" checkout -q -B "$BRANCH" FETCH_HEAD
  ok "Код обновлён: $DIR"
else
  git clone -q --depth 1 --branch "$BRANCH" "$REPO" "$DIR"
  ok "Код скачан: $DIR"
fi
cd "$DIR"

# ── библиотеки ─────────────────────────────────────────────────────────────
[ -x .venv/bin/python ] || python3 -m venv .venv || die "Не удалось создать .venv (нужен python3-venv)."
.venv/bin/python -m pip install -q --upgrade pip >/dev/null 2>&1 || true
.venv/bin/python -m pip install -q -r course_bot/requirements.txt \
  || die "Не удалось поставить библиотеки. Проверьте интернет и запустите команду ещё раз."
.venv/bin/python -c 'import course_bot.main' >/dev/null 2>&1 || die "Код бота не запускается."
ok "Библиотеки поставлены"

# ── токен, владелец, автозапуск ────────────────────────────────────────────
# Скрипт пришёл через «curl | bash», поэтому вопросы читаем с клавиатуры, а не из трубы.
exec .venv/bin/python -m course_bot.setup < /dev/tty
