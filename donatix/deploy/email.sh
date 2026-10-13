#!/usr/bin/env bash
# Отправка писем с сайта (подтверждение почты для конкурса рефералов) — бесплатно через Gmail или Brevo.
#
#   Gmail:  sudo bash /home/donatix/app/donatix/deploy/email.sh gmail 'вы@gmail.com' 'пароль приложения (16 букв)'
#   Brevo:  sudo bash /home/donatix/app/donatix/deploy/email.sh brevo 'логин SMTP Brevo' 'SMTP-ключ' 'от кого@вашдомен'
#
# Gmail: «Пароль приложения» — myaccount.google.com → Безопасность → двухэтапная проверка (включить) →
#   «Пароли приложений» → создать → 16 букв. Обычный пароль Gmail НЕ подойдёт. До 500 писем в день.
# Brevo: brevo.com → бесплатный аккаунт → SMTP & API → SMTP → логин и «Generate SMTP key». 300 писем в день.
# Скрипт сначала отправляет пробное письмо на тот же адрес и только если всё ок — пишет настройки в .env.
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"; BRANCH="${DONATIX_BRANCH:-claude/website-api-sales-96wxcs}"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
ok() { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден ($ENV_FILE)."

KIND="${1:-}"; USER_="${2:-}"; PASS="${3:-}"; FROM="${4:-}"
case "$KIND" in
  gmail) HOST="smtp.gmail.com"; PASS="${PASS// /}"; FROM="${FROM:-$USER_}"
         [[ "$USER_" == *@* ]] || die "Второй — ваш адрес Gmail."
         [[ "$PASS" =~ ^[a-zA-Z]{16}$ ]] || die "Третий — пароль приложения Google: 16 латинских букв (пробелы можно)." ;;
  brevo) HOST="smtp-relay.brevo.com"
         [ -n "$USER_" ] && [ -n "$PASS" ] || die "Нужны логин SMTP и SMTP-ключ из Brevo."
         [[ "$FROM" == *@* ]] || die "Четвёртый — адрес отправителя, подтверждённый в Brevo (Senders)." ;;
  *) die "Первый — gmail или brevo. Пример: sudo bash $0 gmail 'вы@gmail.com' 'abcd efgh ijkl mnop'" ;;
esac

H="$HOST" U="$USER_" P="$PASS" F="$FROM" python3 - <<'PY' || die "Письмо не ушло — проверьте логин и пароль (для Gmail нужен именно пароль приложения)."
import os, smtplib
from email.message import EmailMessage
m = EmailMessage(); m["Subject"] = "Donatix: почта подключена ✅"; m["From"] = os.environ["F"]; m["To"] = os.environ["F"]
m.set_content("Это пробное письмо: сайт теперь умеет отправлять письма (подтверждение почты для конкурса рефералов).")
with smtplib.SMTP(os.environ["H"], 587, timeout=20) as s:
    s.starttls(); s.login(os.environ["U"], os.environ["P"]); s.send_message(m)
PY
ok "Пробное письмо отправлено на $FROM — проверьте ящик"

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true
cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
H="$HOST" U="$USER_" P="$PASS" F="$FROM" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
for key, val in (("DONATIX_SMTP_HOST", os.environ["H"]), ("DONATIX_SMTP_PORT", "587"),
                 ("DONATIX_SMTP_USER", os.environ["U"]), ("DONATIX_SMTP_PASSWORD", os.environ["P"]),
                 ("DONATIX_SMTP_FROM", os.environ["F"])):
    line = f"{key}={val}"
    s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"
ok "Настройки почты записаны в .env"
systemctl restart donatix
sleep 4
[ "$(systemctl is-active donatix)" = "active" ] || die "Сайт не запустился: journalctl -u donatix -n 40 --no-pager"
ok "Готово. Новые клиенты получат письмо «Подтвердите почту»."
