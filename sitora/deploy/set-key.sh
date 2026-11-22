#!/usr/bin/env bash
# Вписать / сменить ключи Sitora (на экране не видно) и перезапустить бота. Donatix не трогает.
#   sudo bash /home/sitora/app/sitora/deploy/set-key.sh            — ключ поставщика
#   sudo bash /home/sitora/app/sitora/deploy/set-key.sh openai     — ключ OpenAI (проверка чеков)
#   sudo bash /home/sitora/app/sitora/deploy/set-key.sh token      — новый токен бота
#   sudo bash /home/sitora/app/sitora/deploy/set-key.sh support    — контакт поддержки (@username)
#   sudo bash /home/sitora/app/sitora/deploy/set-key.sh hetzner    — API-токен Hetzner Cloud (продажа VPS), нужен Read & Write
set -euo pipefail
ENV_FILE=/home/sitora/app/sitora/.env
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo (под root)."; exit 1; }
[ -f "$ENV_FILE" ] || { echo "Sitora ещё не установлена."; exit 1; }
case "${1:-supplier}" in
  supplier) KEY=SITORA_FAZER_KEY;  read -rsp "API-ключ поставщика: " VAL; echo ;;
  openai)   KEY=SITORA_OPENAI_KEY; read -rsp "Ключ OpenAI: " VAL; echo ;;
  token)    KEY=SITORA_BOT_TOKEN;  read -rsp "Токен бота от @BotFather: " VAL; echo ;;
  support)  KEY=SITORA_SUPPORT;    read -rp  "Контакт поддержки (например @my_support): " VAL ;;
  hetzner)  KEY=SITORA_HETZNER_TOKEN; read -rsp "API-токен Hetzner Cloud (Read & Write): " VAL; echo ;;
  *) echo "Неизвестно: $1 (можно: supplier, openai, token, support, hetzner)"; exit 1 ;;
esac
VAL=$(printf '%s' "$VAL" | tr -d '[:space:]')
[ -n "$VAL" ] || { echo "Пусто — ничего не изменил."; exit 1; }
if [ "$KEY" = SITORA_HETZNER_TOKEN ]; then
  # токен — через stdin в заголовок, в списке процессов его не видно
  hz() { printf 'header = "Authorization: Bearer %s"\n' "$VAL" | curl -s -o /dev/null -w '%{http_code}' -K - "$@"; }
  CODE=$(hz https://api.hetzner.cloud/v1/locations)
  [ "$CODE" = 200 ] || { echo "✖ Hetzner не принял токен (код $CODE). Проверьте, что скопировали его целиком."; exit 1; }
  CODE=$(hz -X POST -H 'Content-Type: application/json' -d '{}' https://api.hetzner.cloud/v1/ssh_keys)
  if [ "$CODE" = 403 ]; then
    echo "✖ Токен только для чтения. В Hetzner Console → Security → API tokens создайте токен с правами Read & Write."; exit 1
  fi
  echo "✓ Токен Hetzner рабочий (Read & Write)."
fi
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
