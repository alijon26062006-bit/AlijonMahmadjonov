#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZVER TAJ — Python-бот на VPS
#
#  Запуск:  sudo bash install-py.sh
#
#  Ключи НЕ спрашиваются: берутся из вашего config.php.
#  Ищет его в /var/www/zver/config.php, потом рядом со скриптом, потом /root.
#
#  HTTPS, домен, nginx и сертификаты не нужны — бот работает
#  через long polling.
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

REPO="${REPO:-alijon26062006-bit/AlijonMahmadjonov}"
BRANCH="${BRANCH:-claude/zver-taj-server-deploy-gom4he}"
RAW="${RAW:-https://raw.githubusercontent.com/${REPO}/refs/heads/${BRANCH}/zver-py}"
DIR="${DIR:-/opt/zverbot}"
SVC="${SVC:-zverbot}"
RUN_USER="${RUN_USER:-zverbot}"

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

# ---------- 1. пакеты ----------
info "Ставлю Python и зависимости…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl ca-certificates >/dev/null
grn "$(python3 --version)"

# ---------- 2. код ----------
info "Забираю код бота…"
mkdir -p "$DIR/handlers"
FILES="bot.py config.py db.py texts.py keyboards.py requirements.txt test_money.py"
HFILES="__init__.py common.py user.py shop.py admin.py"

if [ -f "$SRC/bot.py" ] && [ -d "$SRC/handlers" ]; then
    cp "$SRC"/*.py "$SRC/requirements.txt" "$DIR/" 2>/dev/null || true
    cp "$SRC/handlers"/*.py "$DIR/handlers/"
    grn "код взят из $SRC"
else
    HDR=(); [ -n "${GH_TOKEN:-}" ] && HDR=(-H "Authorization: Bearer ${GH_TOKEN}")
    for f in $FILES; do
        curl -fsSL "${HDR[@]}" "${RAW}/${f}" -o "$DIR/${f}" \
            || die "не скачался ${f} (проверьте ${RAW}/${f})"
    done
    for f in $HFILES; do
        curl -fsSL "${HDR[@]}" "${RAW}/handlers/${f}" -o "$DIR/handlers/${f}" \
            || die "не скачался handlers/${f}"
    done
    grn "код скачан из github.com/$REPO"
fi

python3 -c "import ast,sys; ast.parse(open('$DIR/bot.py',encoding='utf-8').read())" \
    || die "bot.py повреждён при скачивании"

# ---------- 3. ключи из config.php ----------
info "Ищу config.php, чтобы перенести ключи…"
CFG=""
for c in /var/www/zver/config.php "$SRC/config.php" /root/config.php; do
    [ -f "$c" ] && { CFG="$c"; break; }
done
[ -n "$CFG" ] || die "config.php не найден.
  Положите его в /root/config.php и запустите снова:
    scp config.php root@СЕРВЕР:/root/"
grn "нашёл: $CFG"

info "Собираю .env (значения на экран не выводятся)…"
python3 - "$CFG" "$DIR/.env" <<'PY'
import re, sys, pathlib

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
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
    ("DB_HOST",   val("db_host") or "localhost"),
    ("DB_NAME",   val("db_name") or "zver"),
    ("DB_USER",   val("db_user") or "zver"),
    ("DB_PASS",   val("db_pass")),
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

missing = [k for k, v in pairs if k in ("BOT_TOKEN", "ADMINS", "DB_NAME", "DB_USER") and not v]
if missing:
    sys.exit("В config.php не нашлись: " + ", ".join(missing))

dst.write_text(
    "# Создан автоматически из config.php. В git не класть.\n"
    + "".join(f"{k}={v}\n" for k, v in pairs),
    encoding="utf-8",
)
print("  перенесено ключей: " + str(sum(1 for _, v in pairs if v)))
PY

chmod 600 "$DIR/.env"
grn ".env создан, права 600 — вводить ключи вручную не пришлось"

# ---------- 4. виртуальное окружение ----------
info "Ставлю библиотеки (aiogram, aiomysql)…"
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
"$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt" >/dev/null
grn "библиотеки установлены"

# ---------- 5. пользователь и права ----------
if ! id -u "$RUN_USER" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$RUN_USER"
fi
chown -R "$RUN_USER:$RUN_USER" "$DIR"
chmod 600 "$DIR/.env"
grn "бот работает под пользователем $RUN_USER, не под root"

# ---------- 6. проверка базы ----------
info "Проверяю связь с базой…"
if sudo -u "$RUN_USER" "$DIR/.venv/bin/python" - <<PY
import sys; sys.path.insert(0, "$DIR")
import asyncio, db
async def m():
    await db.init()
    r = await db.one("SELECT COUNT(*) c FROM z_users")
    print(f"  пользователей в базе: {r['c']}")
    print(f"  игр в каталоге: {len(await db.games())}")
    await db.close()
asyncio.run(m())
PY
then
    grn "база отвечает"
else
    red "  База не отвечает. Проверьте DB_* в $DIR/.env"
    red "  Если таблиц ещё нет — сначала разверните PHP-версию (install.sh)"
    die "останавливаюсь, чтобы не запускать бота вслепую"
fi

# ---------- 7. systemd ----------
info "Настраиваю автозапуск…"
cat > "/etc/systemd/system/${SVC}.service" <<UNIT
[Unit]
Description=ZVER TAJ Telegram bot (Python)
After=network-online.target mariadb.service mysql.service
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
sleep 4

if systemctl is-active --quiet "$SVC"; then
    grn "бот запущен и добавлен в автозапуск"
else
    red "  Бот не запустился. Последние строки журнала:"
    journalctl -u "$SVC" -n 20 --no-pager | sed 's/^/    /'
    die "разберитесь по журналу и запустите снова"
fi

echo
echo -e "\033[1;32m═══ ГОТОВО ═══\033[0m"
echo
echo "  Папка:     $DIR"
echo "  Сервис:    $SVC"
echo "  Журнал:    journalctl -u $SVC -f"
echo "  Стоп:      systemctl stop $SVC"
echo "  Рестарт:   systemctl restart $SVC"
echo
journalctl -u "$SVC" -n 6 --no-pager | sed 's/^/    /'
echo
ylw "  ВАЖНО: у одного токена бывает только один приёмник обновлений."
ylw "  Python-бот снял webhook, поэтому PHP-версия на этом токене"
ylw "  больше сообщений не получает. Чтобы гонять обе сразу —"
ylw "  заведите отдельного тестового бота у @BotFather и впишите"
ylw "  его токен в $DIR/.env, затем: systemctl restart $SVC"
echo
