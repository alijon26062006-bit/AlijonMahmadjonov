#!/usr/bin/env bash
# Задать новый пароль клиенту Donatix (если он не может восстановить его сам).
#
#   sudo bash /home/donatix/app/donatix/deploy/password.sh            — спросит логин, email или ID
#   sudo bash /home/donatix/app/donatix/deploy/password.sh amiri      — сразу найдёт клиента
#
# Пароль вводится скрыто — его не видно на экране и в истории команд. В базе хранится только хэш.
# Все старые входы клиента закрываются: на всех устройствах он войдёт уже с новым паролем.
set -euo pipefail
APP_DIR="/home/donatix/app"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -d "$APP_DIR/donatix" ] || die "Donatix не найден ($APP_DIR/donatix)."

WHO="${1:-}"
if [ -z "$WHO" ]; then read -rp "Логин, email или ID клиента: " WHO; fi
WHO="$(printf '%s' "$WHO" | tr -d '[:space:]')"
[ -n "$WHO" ] || die "Пусто."

# переменные (WHO, PASS, UID_) передаём через окружение — не в командной строке, в списке процессов их не видно
run() { (cd "$APP_DIR" && sudo --preserve-env=WHO,PASS,UID_ -u donatix "${PY:-$APP_DIR/.venv/bin/python}" -); }

export WHO
FOUND=$(run <<'PY'
import os, sqlite3
from donatix.config import Config
c = sqlite3.connect(str(Config.from_env().db_path))
w = os.environ["WHO"].lstrip("@")
rows = c.execute("SELECT id, login, email, status FROM users WHERE id = ? OR lower(login) = lower(?) OR lower(email) = lower(?) "
                 "OR lower(login) LIKE lower(?) LIMIT 10", (int(w) if w.isdigit() else -1, w, w, f"%{w}%")).fetchall()
for r in rows:
    print(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}")
PY
)
[ -n "$FOUND" ] || die "Клиент «$WHO» не найден. Попробуйте email или ID."
echo; echo "Найдено:"; printf '%s\n' "$FOUND" | awk -F'\t' '{printf "  ID %s · логин %s · %s · %s\n", $1, $2, $3, $4}'
if [ "$(printf '%s\n' "$FOUND" | wc -l)" -gt 1 ]; then
  read -rp "Несколько совпадений — впишите ID нужного клиента: " UID_
else
  UID_=$(printf '%s' "$FOUND" | cut -f1)
  read -rp "Это он? [y/n]: " OK; [ "$OK" = y ] || [ "$OK" = Y ] || [ "$OK" = д ] || die "Отменено."
fi
[[ "$UID_" =~ ^[0-9]+$ ]] || die "ID — это число."
printf '%s\n' "$FOUND" | cut -f1 | grep -qx "$UID_" || die "ID $UID_ нет в списке выше."

read -rsp "Новый пароль (не меньше 8 символов): " P1; echo
read -rsp "Повторите пароль: " P2; echo
[ "$P1" = "$P2" ] || die "Пароли не совпадают."
[ "${#P1}" -ge 8 ] || die "Пароль — не меньше 8 символов."

export PASS="$P1" UID_
run <<'PY'
import os, sqlite3
from datetime import datetime, timezone
from donatix.config import Config
from donatix.security import hash_password
c = sqlite3.connect(str(Config.from_env().db_path), timeout=15)
uid = int(os.environ["UID_"])
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with c:
    n = c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(os.environ["PASS"]), uid)).rowcount
    cols = [r[1] for r in c.execute("PRAGMA table_info(logins)")]
    if "ended_at" in cols:   # старые входы закрываем
        c.execute("UPDATE logins SET ended_at = ? WHERE user_id = ? AND ended_at IS NULL", (now, uid))
login = c.execute("SELECT login FROM users WHERE id = ?", (uid,)).fetchone()
print(f"✔ Пароль изменён: ID {uid}, логин {login[0]}" if n else "✖ Клиент не найден")
PY
unset P1 P2 PASS
echo "Передайте клиенту логин и новый пароль лично. После входа пусть сменит пароль в кабинете (donatix.tj/panel/password)."
