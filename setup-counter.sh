#!/usr/bin/env bash
# Установка счётчика товаров одной командой:
#
#   bash setup-counter.sh
#
# Ставит библиотеки, качает голосовую модель, спрашивает токен и запускает бота.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

BOLD=$'\033[1m'; DIM=$'\033[90m'; GREEN=$'\033[32m'; RED=$'\033[31m'; OFF=$'\033[0m'

say()  { printf '%s\n' "$*"; }
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$OFF" "$*"; }
bad()  { printf '  %s✗%s %s\n' "$RED" "$OFF" "$*" >&2; }
hint() { printf '  %s%s%s\n' "$DIM" "$*" "$OFF"; }
step() { printf '\n%s[%s/6] %s%s\n' "$BOLD" "$1" "$2" "$OFF"; }
die()  { bad "$*"; exit 1; }

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 && SUDO="sudo"
fi

say ""
say "${BOLD}Счётчик товаров — установка${OFF}"
hint "Голосом называешь числа, бот считает каждому. Без платных ключей."

# ── 1. Системные пакеты ────────────────────────────────────────────────────
step 1 "Системные пакеты"
command -v python3 >/dev/null 2>&1 || die "Не найден python3. Установи его: apt install python3"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Нужен Python 3.10 или новее."
ok "Python $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

NEEDED=()
python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || NEEDED+=("python3-venv")
command -v unzip >/dev/null 2>&1 || NEEDED+=("unzip")
command -v curl  >/dev/null 2>&1 || NEEDED+=("curl")
# Шрифт с кириллицей: без него в PDF будет латиница.
ls /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf >/dev/null 2>&1 \
  || ls /usr/share/fonts/dejavu/DejaVuSans.ttf >/dev/null 2>&1 \
  || NEEDED+=("fonts-dejavu-core")

if [ ${#NEEDED[@]} -gt 0 ]; then
  hint "Доставляю: ${NEEDED[*]}"
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update -qq && $SUDO apt-get install -y -qq "${NEEDED[@]}" >/dev/null
  elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y -q python3-venv unzip curl dejavu-sans-fonts >/dev/null || true
  elif command -v brew >/dev/null 2>&1; then
    brew install unzip curl >/dev/null || true
  else
    hint "Не знаю твой пакетный менеджер — поставь вручную: ${NEEDED[*]}"
  fi
fi
ok "Пакеты на месте"

# ── 2. Виртуальное окружение ───────────────────────────────────────────────
step 2 "Виртуальное окружение"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv || die "Не удалось создать .venv. Поставь пакет python3-venv."
  ok "Создано .venv"
else
  ok "Уже есть .venv"
fi
PY=.venv/bin/python

# ── 3. Библиотеки ──────────────────────────────────────────────────────────
step 3 "Библиотеки"
hint "Качаю, это самая долгая часть…"
$PY -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
if ! $PY -m pip install --quiet -r requirements-counter.txt; then
  hint "Обычная установка не прошла, пробую обходной путь…"
  $PY -m pip install --quiet aiogram openpyxl reportlab av \
    || die "Не ставятся библиотеки. Проверь интернет."
  # У vosk есть зависимость srt, которая иногда не собирается на новых setuptools.
  $PY -m pip install --quiet --no-deps vosk \
    && $PY -m pip install --quiet cffi requests tqdm websockets srt \
    || hint "vosk поставить не вышло — бот запустится, но голос слушать не сможет."
fi
$PY -c 'import counter.main' >/dev/null 2>&1 || die "Код не импортируется — что-то не так с установкой."
ok "Библиотеки готовы"

# ── 4. Голосовая модель ────────────────────────────────────────────────────
step 4 "Голосовая модель (скачивается один раз, ~45 МБ)"
MODEL_DIR="models/vosk-ru"
if [ -d "$MODEL_DIR" ] && [ -n "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
  ok "Модель уже скачана: $MODEL_DIR"
else
  LANG_CHOICE="${COUNTER_LANG:-}"
  if [ -z "$LANG_CHOICE" ] && [ -t 0 ]; then
    say ""
    say "  На каком языке будешь диктовать числа?"
    say "    1) русский   (семь тысяч шестьсот)"
    say "    2) узбекский (yetti ming olti yuz)"
    printf "  Выбор [1]: "
    read -r LANG_CHOICE || true
  fi
  case "${LANG_CHOICE:-1}" in
    2|uz) URL="https://alphacephei.com/vosk/models/vosk-model-small-uz-0.22.zip" ;;
    *)    URL="https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip" ;;
  esac

  mkdir -p models
  hint "Качаю $URL"
  if curl -fSL --retry 3 -o models/model.zip "$URL"; then
    rm -rf "$MODEL_DIR" && mkdir -p "$MODEL_DIR"
    unzip -q models/model.zip -d models/unpacked
    INNER="$(find models/unpacked -maxdepth 2 -name 'am' -o -maxdepth 2 -name 'conf' | head -1)"
    INNER="$(dirname "${INNER:-models/unpacked}")"
    mv "$INNER"/* "$MODEL_DIR"/ 2>/dev/null || true
    rm -rf models/unpacked models/model.zip
    ok "Модель распакована в $MODEL_DIR"
  else
    bad "Не скачалось. Скачай вручную с https://alphacephei.com/vosk/models"
    hint "и распакуй так, чтобы получилось $MODEL_DIR/am и $MODEL_DIR/conf"
  fi
fi

# ── 5. Токен и запуск ──────────────────────────────────────────────────────
step 5 "Токен бота"
touch .env
if grep -q '^COUNTER_BOT_TOKEN=.\+' .env 2>/dev/null; then
  ok "Токен уже записан в .env"
else
  say ""
  say "  Открой в Телеграме @BotFather → /newbot → придумай имя."
  say "  Он пришлёт строку вида 123456789:AAH..."
  printf "  Вставь её сюда: "
  read -r TOKEN || true
  [ -n "${TOKEN:-}" ] || die "Пустой токен. Запусти скрипт ещё раз."
  printf 'COUNTER_BOT_TOKEN=%s\n' "$TOKEN" >> .env
  ok "Токен сохранён в .env"
fi

# ── 6. Как запускать ───────────────────────────────────────────────────────
step 6 "Запуск"

MODE="${COUNTER_RUN_MODE:-}"
if [ -z "$MODE" ] && [ -t 0 ]; then
  say ""
  say "  Как запускать бота?"
  say "    1) круглосуточно — работает всегда, сам поднимается после"
  say "       перезагрузки сервера и после сбоев ${DIM}(так лучше)${OFF}"
  say "    2) прямо здесь, в этом окне — закроешь SSH, бот остановится"
  printf "  Выбор [1]: "
  read -r MODE || true
fi

case "${MODE:-1}" in
  2|now|foreground)
    say ""
    say "${BOLD}Запускаю.${OFF} Открой бота в Телеграме и напиши /start"
    hint "Остановить: Ctrl+C. Запустить снова: .venv/bin/python -m counter"
    hint "Передумаешь — включить круглосуточную работу: bash service-counter.sh"
    say ""
    exec $PY -m counter
    ;;
  *)
    exec bash service-counter.sh
    ;;
esac
