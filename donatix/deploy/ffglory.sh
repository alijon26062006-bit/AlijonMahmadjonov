#!/usr/bin/env bash
# Glory клана Free Fire (ffglory.pro) на сайте: одна команда — ключи в .env, обновление, перезапуск, проверка.
#
#   sudo bash /home/donatix/app/donatix/deploy/ffglory.sh 'API_KEY' 'MASTER_KEY' [наценка_%]
#
# API_KEY — ваш ключ из кабинета FFGlory → Reseller API (начинается с ak_).
# MASTER_KEY — x-api-key из их документации (32 символа). Оба пишутся только в donatix/.env (не в репозиторий).
# Наценка по умолчанию 25 %. Повторный запуск с новыми ключами — заменит старые.
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"; BRANCH="${DONATIX_BRANCH:-claude/website-api-sales-96wxcs}"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
ok() { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден ($ENV_FILE)."

KEY="${1:-}"; MASTER="${2:-}"; MARKUP="${3:-25}"
[[ "$KEY" =~ ^ak_[A-Za-z0-9]{20,}$ ]] || die "Первый — ваш API key FFGlory (начинается с ak_)."
[[ "$MASTER" =~ ^[A-Za-z0-9]{16,}$ ]] || die "Второй — MASTER_KEY (x-api-key) из документации FFGlory."
[[ "$MARKUP" =~ ^[0-9]{1,3}(\.[0-9]+)?$ ]] || die "Наценка — число процентов, например 25."

resp=$(curl -s -m 20 -w '\n%{http_code}' -H "x-api-key: $MASTER" "https://ffglory.pro/api/auth/me?api_key=$KEY" || true)
code=$(tail -n1 <<<"$resp")
[ "$code" = "200" ] || die "FFGlory не принял ключи (ответ $code). Проверьте, что скопировали их целиком."
ok "Ключи FFGlory рабочие: $(head -n1 <<<"$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"кредитов: обычных {d.get(\"basic_credits\")}, премиум {d.get(\"premium_credits\")}")' 2>/dev/null || echo 'ок')"

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true
ok "Код сайта обновлён"

cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
KEY="$KEY" MASTER="$MASTER" MARKUP="$MARKUP" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
for key, env in (("DONATIX_FFGLORY_KEY", "KEY"), ("DONATIX_FFGLORY_MASTER", "MASTER"), ("DONATIX_FFGLORY_MARKUP", "MARKUP")):
    line = f"{key}={os.environ[env].strip()}"
    s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"
ok "Ключи записаны в .env, наценка $MARKUP %"

systemctl restart donatix
sleep 4
state=$(systemctl is-active donatix)
page=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ || true)
echo "  сайт: $state, главная $page"
[ "$state" = "active" ] || die "Сайт не запустился: journalctl -u donatix -n 40 --no-pager"
ok "Готово: «Glory клана Free Fire» — в «Популярном», страница: /panel/glory"
echo "  Кредиты покупайте в кабинете FFGlory — без них запуск не пройдёт (клиенту деньги вернутся сами)."
