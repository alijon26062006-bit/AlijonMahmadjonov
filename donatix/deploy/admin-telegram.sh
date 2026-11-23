#!/usr/bin/env bash
# Код входа в админку — в Telegram самого админа (а не владельца).
#
#   sudo bash /home/donatix/app/donatix/deploy/admin-telegram.sh amiri 123456789
#
# amiri — логин, email или ID аккаунта на сайте; 123456789 — его Telegram ID.
# Условие: этот Telegram ID добавлен в админ-боте как кассир с ПОЛНЫМИ правами и нажал там /start.
set -euo pipefail
APP_DIR="/home/donatix/app"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
WHO="${1:-}"; TG="${2:-}"
[ -n "$WHO" ] || read -rp "Логин, email или ID аккаунта на сайте: " WHO
[ -n "$TG" ] || read -rp "Его Telegram ID (число): " TG
[[ "$TG" =~ ^[0-9]{5,15}$ ]] || die "Telegram ID — число, например 123456789."
export WHO TG
cd "$APP_DIR" && sudo --preserve-env=WHO,TG -u donatix "${PY:-$APP_DIR/.venv/bin/python}" - <<'PY'
import os, sqlite3, sys
from donatix.config import Config
c = sqlite3.connect(str(Config.from_env().db_path), timeout=15)
w = os.environ["WHO"].strip().lstrip("@"); tg = int(os.environ["TG"])
u = c.execute("SELECT id, login, role FROM users WHERE id = ? OR lower(login) = lower(?) OR lower(email) = lower(?)",
              (int(w) if w.isdigit() else -1, w, w)).fetchone()
if u is None:
    sys.exit(f"✖ Аккаунт «{w}» не найден.")
if u[2] != "admin":
    print(f"⚠ У {u[1]} нет роли админа на сайте — код входа ему и не нужен, но связь сохраню.")
full = {r[0] for r in c.execute("SELECT tg_id FROM cashiers WHERE active = 1 AND full = 1")}
with c:
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"admin_tg.{u[0]}", str(tg)))
print(f"✔ Код входа для {u[1]} будет приходить в Telegram {tg}.")
if tg not in full:
    print("⚠ Но этот Telegram ID сейчас НЕ кассир с полными правами — пока не добавите его в админ-боте "
          "(Кассиры → полные права), код будет приходить владельцу.")
PY
