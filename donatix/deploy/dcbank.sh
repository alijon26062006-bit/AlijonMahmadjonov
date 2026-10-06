#!/usr/bin/env bash
# Автоплатёж «Душанбе Сити» на сайте: одна команда.
#
#   sudo bash /home/donatix/app/donatix/deploy/dcbank.sh API_ID API_HASH BANK_BOT
#
# 1. обновляет сайт и ставит telethon;
# 2. пишет ключи в donatix/.env (не в репозиторий);
# 3. спрашивает номер карты для приёма и добавляет способ «Душанбе Сити · авто» (если его ещё нет);
# 4. входит в Telegram, куда приходят уведомления банка (номер и код вводите здесь);
# 5. запускает службу donatix-bankbot — работает 24/7 и сама поднимается после перезагрузки.
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"; BRANCH="${DONATIX_BRANCH:-claude/website-api-sales-96wxcs}"
UNIT=/etc/systemd/system/donatix-bankbot.service
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
ok() { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден ($ENV_FILE)."

API_ID="${1:-}"; API_HASH="${2:-}"; BANK="${3:-}"; BANK="${BANK#@}"
echo "$API_ID" | grep -qE '^[0-9]{5,12}$' || die "API_ID — число с my.telegram.org, например 12345678."
echo "$API_HASH" | grep -qiE '^[a-f0-9]{32}$' || die "API_HASH — 32 знака (цифры и a-f) с my.telegram.org."
echo "$BANK" | grep -qE '^[A-Za-z0-9_]{4,32}$' || die "BANK_BOT — юзернейм бота банка без @ (dc_next_bot) или его id."

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true
sudo -u donatix "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/donatix/requirements.txt"
ok "Сайт обновлён, telethon установлен"

cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
API_ID="$API_ID" API_HASH="$API_HASH" BANK="$BANK" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
for key, env in (("DONATIX_TG_API_ID", "API_ID"), ("DONATIX_TG_API_HASH", "API_HASH"), ("DONATIX_BANK_BOT", "BANK")):
    line = f"{key}={os.environ[env].strip()}"
    s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"
ok "Ключи Telegram записаны в .env"

# Способ оплаты «Душанбе Сити · авто»
HAS=$(cd "$APP_DIR" && sudo -u donatix .venv/bin/python -c "
from donatix import db, payments; from donatix.config import Config
c = Config.from_env(); db.init(c.db_path); conn = db.connect(c.db_path)
print(1 if any(m.get('auto') == 'dcbank' for m in payments.settings(conn, c)['all_methods']) else 0)")
if [ "$HAS" = 0 ]; then
    printf 'Номер карты «Душанбе Сити», на которую клиенты переводят (видят его): '; read -r CARD < /dev/tty
    printf 'Имя получателя (Enter — пропустить): '; read -r HOLDER < /dev/tty
    (cd "$APP_DIR" && CARD="$CARD" HOLDER="$HOLDER" sudo -E -u donatix .venv/bin/python -c "
import os
from donatix import db, payments; from donatix.config import Config
c = Config.from_env(); conn = db.connect(c.db_path)
ms = payments.settings(conn, c)['all_methods']
details = 'Карта ' + os.environ['CARD'].strip() + ((', ' + os.environ['HOLDER'].strip()) if os.environ['HOLDER'].strip() else '')
ms.insert(0, {'code': 'dcauto', 'title': 'Душанбе Сити · авто', 'currency': 'TJS', 'details': details,
              'enabled': True, 'auto': 'dcbank'})
payments.save_methods(conn, ms)
print('✔ Способ «Душанбе Сити · авто» добавлен первым в списке')") || die "Номер карты не подошёл — нужно 10+ цифр."
    # Уведомления по другим картам (например, карте бота-магазина) сайт не трогает
    TAIL=$(echo "$CARD" | tr -cd '0-9' | tail -c 4)
    sed -i '/^DONATIX_BANK_CARD=/d' "$ENV_FILE"; echo "DONATIX_BANK_CARD=$TAIL" >> "$ENV_FILE"
    ok "Сайт слушает только карту *$TAIL"
else
    ok "Способ с автозачислением «Душанбе Сити» уже есть"
fi

systemctl restart donatix
ok "Сайт перезапущен"

cat > "$UNIT" <<UNIT
[Unit]
Description=Donatix — автоплатёж «Душанбе Сити» (уведомления банка)
After=network-online.target donatix.service
Wants=network-online.target

[Service]
User=donatix
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python -m donatix bank-listen
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload

# Вход: на время входа служба остановлена — два процесса на одном сеансе мешают друг другу.
systemctl stop donatix-bankbot 2>/dev/null || true
echo ""
echo "═══ Вход в Telegram, куда приходят уведомления «Zachislenie» от банка ═══"
echo "Код берите САМЫЙ ПОСЛЕДНИЙ и набирайте руками — пересланный или вставленный в чат код сгорает."
if (cd "$APP_DIR" && sudo -u donatix .venv/bin/python -m donatix bank-login) < /dev/tty; then
    systemctl enable -q --now donatix-bankbot
    sleep 6
    journalctl -u donatix-bankbot -n 8 --no-pager | grep -E 'Слушаю|Подключён|сорвалось' || true
    ok "Готово: автоплатёж «Душанбе Сити» работает 24/7. Смотреть живьём: journalctl -u donatix-bankbot -f"
else
    die "Вход не завершён. Сайт работает, «Душанбе Сити» пока подтверждается по чеку. Повторите эту же команду."
fi
