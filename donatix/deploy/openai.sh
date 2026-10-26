#!/usr/bin/env bash
# Ключ OpenAI для сайта: голосовой помощник в админке, чтение чеков, ответы на отзывы.
#
#   sudo bash /home/donatix/app/donatix/deploy/openai.sh
#
# Скрипт сам спросит ключ (sk-…) — он не появится на экране и в истории команд. Пишется только в donatix/.env.
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
ok() { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден ($ENV_FILE)."

printf 'Вставьте ключ OpenAI (sk-…) и нажмите Enter — на экране его не будет видно: '
read -rs KEY; echo
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"
[[ "$KEY" =~ ^sk-[A-Za-z0-9_-]{20,}$ ]] || die "Это не похоже на ключ OpenAI — он начинается с sk-."

code=$(curl -s -m 20 -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $KEY" https://api.openai.com/v1/models || true)
[ "$code" = "200" ] || die "OpenAI не принял ключ (ответ $code). Проверьте ключ и что на счёте OpenAI есть деньги."
ok "Ключ рабочий"

cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
KEY="$KEY" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
line = "DONATIX_OPENAI_API_KEY=" + os.environ["KEY"]
key = "DONATIX_OPENAI_API_KEY"
s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
unset KEY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"
ok "Ключ записан в .env"

systemctl restart donatix
sleep 4
[ "$(systemctl is-active donatix)" = "active" ] || die "Сайт не запустился: journalctl -u donatix -n 40 --no-pager"
ok "Готово: в админке нажмите на фиолетовый шарик в поиске и говорите"
