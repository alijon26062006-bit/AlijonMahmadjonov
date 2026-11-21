#!/usr/bin/env bash
# Вписать / сменить ключи Sitora (на экране не видно) и перезапустить бота. Donatix не трогает.
#   sudo bash /home/sitora/app/sitora/deploy/set-key.sh            — ключ поставщика
#   sudo bash /home/sitora/app/sitora/deploy/set-key.sh openai     — ключ OpenAI (проверка чеков)
#   sudo bash /home/sitora/app/sitora/deploy/set-key.sh token      — новый токен бота
#   sudo bash /home/sitora/app/sitora/deploy/set-key.sh support    — контакт поддержки (@username)
set -euo pipefail
ENV_FILE=/home/sitora/app/sitora/.env
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo (под root)."; exit 1; }
[ -f "$ENV_FILE" ] || { echo "Sitora ещё не установлена."; exit 1; }
case "${1:-supplier}" in
  supplier) KEY=SITORA_FAZER_KEY;  read -rsp "API-ключ поставщика: " VAL; echo ;;
  openai)   KEY=SITORA_OPENAI_KEY; read -rsp "Ключ OpenAI: " VAL; echo ;;
  token)    KEY=SITORA_BOT_TOKEN;  read -rsp "Токен бота от @BotFather: " VAL; echo ;;
  support)  KEY=SITORA_SUPPORT;    read -rp  "Контакт поддержки (например @my_support): " VAL ;;
  *) echo "Неизвестно: $1 (можно: supplier, openai, token, support)"; exit 1 ;;
esac
VAL=$(printf '%s' "$VAL" | tr -d '[:space:]')
[ -n "$VAL" ] || { echo "Пусто — ничего не изменил."; exit 1; }
KEY="$KEY" VAL="$VAL" python3 - "$ENV_FILE" <<'PY'
import os, sys
p, k, v = sys.argv[1], os.environ["KEY"], os.environ["VAL"]
lines = open(p, encoding="utf-8").read().splitlines()
lines = [l for l in lines if not l.startswith(k + "=")] + [f"{k}={v}"]
open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
unset VAL
systemctl restart sitora; sleep 2
sudo -u sitora bash -c "cd /home/sitora/app/sitora && .venv/bin/python -m sitora check" || true
systemctl is-active --quiet sitora && echo "✅ Сохранено, бот перезапущен." || journalctl -u sitora -n 20 --no-pager
