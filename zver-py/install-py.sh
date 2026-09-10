#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZVER TAJ — Python-бот на чистый VPS
#
#  Запуск:  bash install-py.sh
#
#  Ставит Python и MariaDB, создаёт базу и таблицы, поднимает сервис.
#  PHP не нужен вообще.
#
#  Ключи: если рядом есть config.php — возьмёт их оттуда и ничего
#  не спросит. Если нет — спросит один раз и запомнит в .env.
#
#  HTTPS, домен, nginx и сертификаты не нужны: long polling.
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

REPO="${REPO:-alijon26062006-bit/AlijonMahmadjonov}"
BRANCH="${BRANCH:-claude/zver-taj-server-deploy-gom4he}"
RAW="${RAW:-https://raw.githubusercontent.com/${REPO}/refs/heads/${BRANCH}/zver-py}"
DIR="${DIR:-/opt/zverbot}"
SVC="${SVC:-zverbot}"
RUN_USER="${RUN_USER:-zverbot}"
DB_NAME="${DB_NAME:-zver}"
DB_USER="${DB_USER:-zver}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo /root)"

red()  { echo -e "\033[31m$*\033[0m"; }
grn()  { echo -e "\033[32m  ✔ $*\033[0m"; }
ylw()  { echo -e "\033[33m$*\033[0m"; }
info() { echo -e "\033[36m▸ $*\033[0m"; }
die()  { red "✘ $*"; exit 1; }

echo
echo -e "\033[1;36m═══ ZVER TAJ — Python-бот ═══\033[0m"
echo

[ "$(id -u)" -eq 0 ] || die "Нужен root: sudo bash install-py.sh"
[ -r /etc/os-release ] || die "Не определяется ОС"
. /etc/os-release
case "$ID" in ubuntu|debian) ;; *) die "Поддерживаются Ubuntu и Debian, у вас $ID" ;; esac
info "ОС: ${PRETTY_NAME:-$ID}"

INTERACTIVE=0
[ -t 0 ] && INTERACTIVE=1

ask() {                        # ask ПЕРЕМЕННАЯ "Вопрос" [обязательно]
    local var="$1" prompt="$2" required="${3:-0}" ans
    [ -n "${!var:-}" ] && return 0
    if [ "$INTERACTIVE" -eq 0 ]; then
        [ "$required" -eq 1 ] && die "Нет значения $var (неинтерактивный режим)"
        return 0
    fi
    while :; do
        read -r -p "  $prompt: " ans || ans=""
        if [ -n "$ans" ]; then printf -v "$var" '%s' "$ans"; return 0; fi
        [ "$required" -eq 0 ] && return 0
        red "  Это поле обязательно."
    done
}

# ---------- 1. пакеты ----------
info "Ставлю Python и MariaDB…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl ca-certificates \
        mariadb-server openssl >/dev/null
grn "$(python3 --version), $(mariadbd --version 2>/dev/null | head -1 || echo MariaDB)"

systemctl enable --now mariadb >/dev/null 2>&1 || systemctl start mariadb || true
for i in $(seq 1 20); do
    mysql -e "SELECT 1" >/dev/null 2>&1 && break
    sleep 1
done
mysql -e "SELECT 1" >/dev/null 2>&1 || die "MariaDB не поднялась: systemctl status mariadb"
grn "MariaDB работает"

# ---------- 2. код ----------
info "Забираю код бота…"
mkdir -p "$DIR/handlers" "$DIR/services"
FILES="bot.py config.py db.py schema.py texts.py keyboards.py middlewares.py
       requirements.txt test_money.py test_features.py test_ops.py"
HFILES="__init__.py common.py user.py shop.py admin.py reviews.py"
SFILES="__init__.py subs.py promo.py referral.py reviews.py maintenance.py"

if [ -f "$SRC/bot.py" ] && [ -d "$SRC/handlers" ]; then
    cp "$SRC"/*.py "$SRC/requirements.txt" "$DIR/" 2>/dev/null || true
    cp "$SRC/handlers"/*.py "$DIR/handlers/"
    cp "$SRC/services"/*.py "$DIR/services/" 2>/dev/null || true
    grn "код взят из $SRC"
else
    # Сначала пробуем без авторизации: для публичного файла лишний заголовок
    # Authorization заставляет GitHub ответить 404. Токен подключаем только
    # если без него не получилось — тогда репозиторий закрытый.
    fetch() {                       # fetch <относительный путь> <куда>
        curl -fsSL "${RAW}/$1" -o "$2" 2>/dev/null && return 0
        if [ -n "${GH_TOKEN:-}" ]; then
            curl -fsSL -H "Authorization: Bearer ${GH_TOKEN}" \
                 "${RAW}/$1" -o "$2" 2>/dev/null && return 0
        fi
        return 1
    }

    for f in $FILES; do
        fetch "$f" "$DIR/${f}" || die "не скачался ${f} (проверьте ${RAW}/${f})"
    done
    for f in $HFILES; do
        fetch "handlers/${f}" "$DIR/handlers/${f}" || die "не скачался handlers/${f}"
    done
    for f in $SFILES; do
        fetch "services/${f}" "$DIR/services/${f}" || die "не скачался services/${f}"
    done
    grn "код скачан из github.com/$REPO"
fi

python3 -c "import ast; ast.parse(open('$DIR/bot.py',encoding='utf-8').read())" \
    || die "bot.py повреждён при скачивании"

# ---------- 3. база ----------
info "Создаю базу данных…"
if [ -f "$DIR/.env" ]; then
    DB_PASS="$(grep -m1 '^DB_PASS=' "$DIR/.env" | cut -d= -f2- || true)"
fi
[ -n "${DB_PASS:-}" ] || DB_PASS="$(openssl rand -hex 20)"

mysql -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`
          CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Анонимные учётки, которые остаются после установки MariaDB, перехватывают
# подключения с localhost и не дают войти обычному пользователю. Убираем их —
# то же самое делает mysql_secure_installation.
mysql -e "DELETE FROM mysql.global_priv WHERE User=''; FLUSH PRIVILEGES;" 2>/dev/null \
  || mysql -e "DELETE FROM mysql.user WHERE User=''; FLUSH PRIVILEGES;" 2>/dev/null || true

# Пользователя заводим и для localhost, и для 127.0.0.1: в зависимости от
# настроек MariaDB соединение может опознаться и так, и так.
for H in 'localhost' '127.0.0.1'; do
    mysql -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'$H' IDENTIFIED BY '${DB_PASS}';"
    mysql -e "ALTER USER '${DB_USER}'@'$H' IDENTIFIED BY '${DB_PASS}';"
    mysql -e "GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'$H';"
done
mysql -e "FLUSH PRIVILEGES;"
grn "база «${DB_NAME}» и пользователь «${DB_USER}» готовы"

# ---------- 4. ключи ----------
CFG=""
for c in "$SRC/config.php" /root/config.php /var/www/zver/config.php; do
    [ -f "$c" ] && { CFG="$c"; break; }
done

if [ -n "$CFG" ]; then
    info "Нашёл $CFG — беру ключи оттуда, спрашивать не буду"
else
    if [ -f "$DIR/.env" ] && grep -q '^BOT_TOKEN=.\+' "$DIR/.env"; then
        info "Ключи уже сохранены в $DIR/.env — оставляю как есть"
        CFG="__ENV__"
    else
        echo
        info "config.php не найден — заполним ключи один раз"
        ylw "  Токен бота: @BotFather → /mybots → API Token"
        ylw "  Ваш Telegram ID: напишите @userinfobot"
        echo
        ask BOT_TOKEN "Токен бота" 1
        ask ADMINS    "Ваш Telegram ID (через запятую, если админов несколько)" 1
        ask SUPPORT   "Контакт поддержки, например @nick (Enter — пропустить)"
        ask FZ_KEY    "Ключ FazerCards fc_… (Enter — пропустить)"
        ask FZ_HOOK   "Webhook-секрет FazerCards whsec_… (Enter — пропустить)"
        ask GS_KEY    "Ключ gameskinbo для ников (Enter — пропустить)"
        ask FT_ID     "FlashTopup ID (Enter — пропустить)"
        ask FT_KEY    "FlashTopup ключ (Enter — пропустить)"
        echo
    fi
fi

info "Собираю .env (значения на экран не выводятся)…"
if [ "$CFG" = "__ENV__" ]; then
    # обновляем только доступы к базе, ключи не трогаем
    python3 - "$DIR/.env" "$DB_NAME" "$DB_USER" "$DB_PASS" "$DB_HOST" "$DB_PORT" <<'PY'
import pathlib, sys
env, name, user, pw, host, port = sys.argv[1:7]
p = pathlib.Path(env)
lines, seen = [], set()
for line in p.read_text(encoding="utf-8").splitlines():
    key = line.split("=", 1)[0].strip()
    repl = {"DB_NAME": name, "DB_USER": user, "DB_PASS": pw,
        "DB_HOST": host, "DB_PORT": port}
    if key in repl:
        lines.append(f"{key}={repl[key]}"); seen.add(key)
    else:
        lines.append(line)
for k, v in (("DB_HOST", host), ("DB_PORT", port), ("DB_NAME", name),
             ("DB_USER", user), ("DB_PASS", pw)):
    if k not in seen:
        lines.append(f"{k}={v}")
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("  доступы к базе обновлены, ключи сохранены")
PY
elif [ -n "$CFG" ]; then
    python3 - "$CFG" "$DIR/.env" "$DB_NAME" "$DB_USER" "$DB_PASS" "$DB_HOST" "$DB_PORT" <<'PY'
import re, sys, pathlib

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
db_name, db_user, db_pass, db_host, db_port = sys.argv[3:8]
text = src.read_text(encoding="utf-8", errors="replace")

def unescape(s: str) -> str:
    return s.replace("\\\\", "\x00").replace("\\'", "'").replace("\x00", "\\")

def val(key: str) -> str:
    m = re.search(r"['\"]" + key + r"['\"]\s*=>\s*'((?:[^'\\]|\\.)*)'", text)
    if m:
        return unescape(m.group(1))
    m = re.search(r"['\"]" + key + r"['\"]\s*=>\s*\"((?:[^\"\\]|\\.)*)\"", text)
    return unescape(m.group(1)) if m else ""

def admins() -> str:
    m = re.search(r"['\"]admins['\"]\s*=>\s*\[([^\]]*)\]", text)
    return ",".join(re.findall(r"-?\d+", m.group(1))) if m else ""

pairs = [
    ("BOT_TOKEN", val("bot_token")),
    ("ADMINS",    admins()),
    ("DB_HOST",   db_host),
    ("DB_PORT",   db_port),
    ("DB_NAME",   db_name),
    ("DB_USER",   db_user),
    ("DB_PASS",   db_pass),
    ("CURRENCY",  val("cur") or "TJS"),
    ("SUPPORT",   val("support")),
    ("FZ_KEY",    val("fz_key")),
    ("FZ_HOOK",   val("fz_hook")),
    ("FZ_BASE",   val("fz_base") or "https://api.fzr.cards/api/v2"),
    ("GS_KEY",    val("gs_key")),
    ("FT_ID",     val("ft_id")),
    ("FT_KEY",    val("ft_key")),
    ("DEBUG",     "0"),
]
missing = [k for k, v in pairs if k in ("BOT_TOKEN", "ADMINS") and not v]
if missing:
    sys.exit("В config.php не нашлись: " + ", ".join(missing))

dst.write_text("# Создан автоматически. В git не класть.\n"
               + "".join(f"{k}={v}\n" for k, v in pairs), encoding="utf-8")
print("  перенесено ключей: " + str(sum(1 for _, v in pairs if v)))
PY
else
    cat > "$DIR/.env" <<ENVEOF
# Создан установщиком. В git не класть.
BOT_TOKEN=${BOT_TOKEN}
ADMINS=$(printf '%s' "${ADMINS}" | tr -cd '0-9,-')
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASS=${DB_PASS}
CURRENCY=${CURRENCY:-TJS}
SUPPORT=${SUPPORT:-}
FZ_KEY=${FZ_KEY:-}
FZ_HOOK=${FZ_HOOK:-}
FZ_BASE=https://api.fzr.cards/api/v2
GS_KEY=${GS_KEY:-}
FT_ID=${FT_ID:-}
FT_KEY=${FT_KEY:-}
DEBUG=0
ENVEOF
    echo "  ключи записаны"
fi

chmod 600 "$DIR/.env"
grep -q '^BOT_TOKEN=.\+' "$DIR/.env" || die "в .env нет токена бота"
grep -q '^ADMINS=[0-9]' "$DIR/.env"  || die "в .env нет ни одного Telegram ID админа"
grn ".env готов, права 600"

# ---------- 5. виртуальное окружение ----------
info "Ставлю библиотеки (aiogram, aiomysql)…"
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
"$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt" >/dev/null
grn "библиотеки установлены"

# ---------- 6. таблицы ----------
info "Создаю таблицы…"
( cd "$DIR" && "$DIR/.venv/bin/python" schema.py ) | sed 's/^/  /' \
    || die "не удалось создать таблицы — проверьте $DIR/.env"
grn "структура базы готова"

# ---------- 7. пользователь и права ----------
if ! id -u "$RUN_USER" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$RUN_USER"
fi
chown -R "$RUN_USER:$RUN_USER" "$DIR"
chmod 600 "$DIR/.env"
grn "бот работает под пользователем $RUN_USER, не под root"

# ---------- 8. systemd ----------
info "Настраиваю автозапуск…"
cat > "/etc/systemd/system/${SVC}.service" <<UNIT
[Unit]
Description=ZVER TAJ Telegram bot (Python)
After=network-online.target mariadb.service
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${DIR}
ExecStart=${DIR}/.venv/bin/python ${DIR}/bot.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${DIR}

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable "$SVC" >/dev/null 2>&1
systemctl restart "$SVC"
sleep 5

if systemctl is-active --quiet "$SVC"; then
    grn "бот запущен и добавлен в автозапуск"
else
    red "  Бот не запустился. Последние строки журнала:"
    journalctl -u "$SVC" -n 25 --no-pager | sed 's/^/    /'
    die "разберитесь по журналу и запустите скрипт снова"
fi

echo
echo -e "\033[1;32m═══ ГОТОВО ═══\033[0m"
echo
echo "  Папка:     $DIR"
echo "  Сервис:    $SVC"
echo "  Журнал:    journalctl -u $SVC -f"
echo "  Рестарт:   systemctl restart $SVC"
echo
journalctl -u "$SVC" -n 8 --no-pager | sed 's/^/    /'
echo
ylw "  ДАЛЬШЕ: напишите боту /start, а затем /admin —"
ylw "  через админку добавьте игры, пакеты и реквизиты для пополнения."
echo
ylw "  У одного токена бывает только один приёмник обновлений."
ylw "  Если этот же токен используется где-то ещё, там бот замолчит."
echo
