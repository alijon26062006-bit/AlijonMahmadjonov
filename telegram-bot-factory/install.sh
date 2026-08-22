#!/usr/bin/env bash
# Установка и запуск фабрики одной командой.
# Скрипт можно запускать сколько угодно раз — он доделывает то, чего не хватает.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HERE/.env"
VENV="$HERE/.venv"
PY="$VENV/bin/python"
SERVICE_NAME="botfactory"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\n\033[31mОшибка: %s\033[0m\n' "$*" >&2; exit 1; }
have_tty() { { : < /dev/tty; } 2>/dev/null; }

# --- 1. Python -----------------------------------------------------------

say "1. Проверяю Python"

command -v python3 >/dev/null 2>&1 || die "python3 не установлен. Установите: apt install -y python3 python3-venv"

python3 - << 'PYEOF' || die "Нужен Python 3.11 или новее. Установите свежий python3."
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PYEOF

info "$(python3 --version)"

# --- 2. Виртуальное окружение --------------------------------------------

say "2. Устанавливаю зависимости"

if [ ! -x "$PY" ]; then
    python3 -m venv "$VENV" || die "не удалось создать окружение. Установите: apt install -y python3-venv"
fi

"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r "$HERE/requirements.txt"
info "готово"

# --- 3. Файл настроек ------------------------------------------------------

say "3. Настройки"

[ -f "$ENV_FILE" ] || cp "$HERE/.env.example" "$ENV_FILE"
chmod 600 "$ENV_FILE"

get_env() {
    grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true
}

set_env() {
    KEY="$1" VALUE="$2" "$PY" - "$ENV_FILE" << 'PYEOF'
import os
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
key = os.environ["KEY"]
# срезаем невидимые символы, которые попадают при копировании из телефона
value = "".join(ch for ch in os.environ["VALUE"] if ch.isprintable()).strip()

lines = path.read_text().splitlines()
replaced = False
for index, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[index] = f"{key}={value}"
        replaced = True
        break
if not replaced:
    lines.append(f"{key}={value}")

path.write_text("\n".join(lines) + "\n")
PYEOF
}

ask_secret() {  # имя_переменной подсказка
    local name="$1" hint="$2" value=""
    while [ -z "$value" ]; do
        printf '  %s\n  > ' "$hint"
        have_tty || die "нет доступа к терминалу. Запустите скрипт напрямую: bash install.sh"
        read -rs value < /dev/tty
        printf '\n'
        value="$(printf '%s' "$value" | tr -d '[:space:]')"
        [ -z "$value" ] && info "пусто, попробуйте ещё раз"
    done
    set_env "$name" "$value"
}

if [ -z "$(get_env MOTHER_BOT_TOKEN)" ]; then
    info "Токен главного бота. Получить: @BotFather -> /newbot"
    info "Ввод не отображается — это нормально. Вставьте и нажмите Enter."
    ask_secret MOTHER_BOT_TOKEN "Вставьте токен бота:"
else
    info "токен бота уже записан"
fi

if [ -z "$(get_env ANTHROPIC_API_KEY)" ]; then
    info "Ключ Anthropic. Получить: platform.claude.com -> API Keys"
    ask_secret ANTHROPIC_API_KEY "Вставьте ключ Anthropic:"
else
    info "ключ Anthropic уже записан"
fi

if [ -z "$(get_env FERNET_KEY)" ]; then
    set_env FERNET_KEY "$("$PY" -m botfactory.crypto)"
    info "ключ шифрования создан"
else
    info "ключ шифрования уже есть"
fi

if [ -z "$(get_env ADMIN_IDS)" ] && have_tty; then
    printf '  Ваш Telegram ID для команды /stats (можно пропустить, Enter)\n  > '
    read -r admin_ids < /dev/tty || admin_ids=""
    if [ -n "$admin_ids" ]; then
        set_env ADMIN_IDS "$(printf '%s' "$admin_ids" | tr -d '[:space:]')"
    fi
fi

# --- 4. Проверка токена -------------------------------------------------------

say "4. Проверяю токен в Telegram"

BOT_USERNAME="$(cd "$HERE" && "$PY" - << 'PYEOF'
import json
import os
import sys
import urllib.request

from dotenv import load_dotenv

load_dotenv(".env")
token = os.getenv("MOTHER_BOT_TOKEN", "").strip()
try:
    with urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/getMe", timeout=20
    ) as response:
        data = json.load(response)
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", "replace")
    try:
        print(f"BADTOKEN:{json.loads(body).get('description', exc)}")
    except ValueError:
        print(f"NET:{exc}")
    sys.exit(0)
except Exception as exc:  # noqa: BLE001 — сеть, DNS, прокси
    print(f"NET:{exc}")
    sys.exit(0)

if data.get("ok"):
    print(data["result"]["username"])
else:
    print(f"BADTOKEN:{data.get('description', 'токен не принят')}")
PYEOF
)"

case "$BOT_USERNAME" in
    BADTOKEN:*)
        printf '\n\033[31mTelegram не принял токен: %s\033[0m\n' "${BOT_USERNAME#BADTOKEN:}"
        info "Скорее всего токен скопирован не полностью или сброшен в @BotFather."
        info "Исправьте строку MOTHER_BOT_TOKEN в файле $ENV_FILE и запустите скрипт снова."
        exit 1
        ;;
    NET:*)
        printf '\n\033[31mНе получилось связаться с Telegram: %s\033[0m\n' "${BOT_USERNAME#NET:}"
        info "Это похоже на проблему сети или блокировку, а не на токен."
        info "Проверьте связь:  curl -s https://api.telegram.org"
        exit 1
        ;;
    "")
        die "не удалось проверить токен"
        ;;
esac

info "бот найден: @$BOT_USERNAME"

# --- 5. Автозапуск --------------------------------------------------------------

say "5. Запускаю"

if command -v systemctl >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Bot Factory
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$HERE
ExecStart=$PY -m botfactory
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable --quiet "$SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        say "Готово"
        info "Фабрика работает: https://t.me/$BOT_USERNAME"
        info "Откройте бота в Telegram и напишите /start"
        printf '\n'
        info "Смотреть, что происходит:  journalctl -u $SERVICE_NAME -f"
        info "Остановить:                systemctl stop $SERVICE_NAME"
        info "Запустить снова:           systemctl start $SERVICE_NAME"
    else
        printf '\n\033[31mСлужба не поднялась. Последние строки журнала:\033[0m\n\n'
        journalctl -u "$SERVICE_NAME" -n 30 --no-pager
        exit 1
    fi
else
    info "systemd недоступен, запускаю прямо здесь. Закроете терминал — фабрика остановится."
    info "Бот: https://t.me/$BOT_USERNAME"
    printf '\n'
    cd "$HERE"
    exec "$PY" -m botfactory
fi
