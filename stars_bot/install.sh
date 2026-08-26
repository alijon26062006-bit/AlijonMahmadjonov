#!/usr/bin/env bash
#
# Установка бота на сервер одной командой.
#
#   bash <(curl -sSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/claude/telegram-stars-sales-bot-caqst0/stars_bot/install.sh)
#
# Повторный запуск обновляет бота до последней версии, настройки не трогает.

set -euo pipefail

# Всё переопределяется переменными окружения:
#   DIR=/srv/bot bash install.sh
REPO="${REPO:-https://github.com/alijon26062006-bit/AlijonMahmadjonov.git}"
BRANCH="${BRANCH:-claude/telegram-stars-sales-bot-caqst0}"
DIR="${DIR:-/opt/stars-bot}"
SERVICE="${SERVICE:-stars-bot}"
RUN_USER="${RUN_USER:-starsbot}"
RAW_INSTALLER="${RAW_INSTALLER:-https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/claude/telegram-stars-sales-bot-caqst0/stars_bot/install.sh}"

# Ввод читаем из терминала, а не из stdin: скрипт мог прийти по конвейеру
# из curl, и тогда stdin занят самим скриптом. Если терминала нет
# (запуск из другого скрипта), остаёмся на обычном stdin.
if [ -r /dev/tty ] && exec 3</dev/tty 2>/dev/null; then
    exec 3<&-
    HAS_TTY=true
else
    HAS_TTY=false
fi

say()  { printf "\n\033[1;36m▸ %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m  ✅ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m  ⚠️  %s\033[0m\n" "$*"; }
die()  { printf "\n\033[1;31m❌ %s\033[0m\n\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------- проверки

[ "$(id -u)" -eq 0 ] || SUDO="sudo"
SUDO="${SUDO:-}"
if [ -n "$SUDO" ] && ! command -v sudo >/dev/null; then
    die "Нужны права root. Зайдите как root или установите sudo."
fi

command -v systemctl >/dev/null || die "На сервере нет systemd — этот установщик рассчитан на него."

say "Ставлю системные пакеты"
if command -v apt-get >/dev/null; then
    $SUDO apt-get update -qq
    # env нужен явно: если $SUDO пустой, bash разберёт VAR=... как имя команды.
    $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        python3 python3-venv python3-pip git ca-certificates >/dev/null
elif command -v dnf >/dev/null; then
    $SUDO dnf install -y -q python3 python3-pip git ca-certificates
elif command -v yum >/dev/null; then
    $SUDO yum install -y -q python3 python3-pip git ca-certificates
else
    warn "Неизвестный менеджер пакетов — проверьте, что стоят python3, venv и git."
fi
ok "python $(python3 --version 2>&1 | cut -d' ' -f2), git $(git --version | cut -d' ' -f3)"

# ------------------------------------------------------- пользователь и код

if ! id "$RUN_USER" >/dev/null 2>&1; then
    say "Создаю системного пользователя $RUN_USER"
    $SUDO useradd --system --create-home --shell /usr/sbin/nologin "$RUN_USER" 2>/dev/null \
        || $SUDO useradd --system --create-home --shell /sbin/nologin "$RUN_USER"
    ok "Бот будет работать не от root — так безопаснее"
fi

UPDATING=false
if [ -d "$DIR/.git" ]; then
    UPDATING=true
    say "Обновляю код"
    $SUDO git -C "$DIR" fetch --quiet origin "$BRANCH"
    $SUDO git -C "$DIR" checkout --quiet "$BRANCH"
    $SUDO git -C "$DIR" reset --hard --quiet "origin/$BRANCH"
else
    say "Скачиваю бота"
    $SUDO rm -rf "$DIR"
    $SUDO git clone --quiet --branch "$BRANCH" --depth 1 "$REPO" "$DIR"
fi
ok "Код в $DIR"

APP="$DIR/stars_bot"
[ -d "$APP" ] || die "В репозитории нет папки stars_bot — что-то пошло не так."

say "Ставлю зависимости"
$SUDO python3 -m venv "$APP/.venv" \
    || die "Не удалось создать окружение. Поставьте пакет python3-venv."
$SUDO "$APP/.venv/bin/pip" install -q --upgrade pip
$SUDO "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
ok "Библиотеки установлены"

# ------------------------------------------------------------- настройка

if [ ! -f "$APP/.env" ]; then
    say "Настройка бота"
    echo "  Понадобятся: токен от @BotFather и ваш ID от @userinfobot."
    echo ""
    if $HAS_TTY; then
        $SUDO "$APP/.venv/bin/python" "$APP/setup.py" < /dev/tty
    else
        $SUDO "$APP/.venv/bin/python" "$APP/setup.py"
    fi
else
    ok "Настройки уже есть, не трогаю ($APP/.env)"
    echo "     Поменять: sudo $APP/.venv/bin/python $APP/setup.py"
fi

[ -f "$APP/.env" ] || die "Настройка не завершена — .env не создан."

$SUDO mkdir -p "$APP/data"
$SUDO chown -R "$RUN_USER:$RUN_USER" "$APP"
$SUDO chmod 600 "$APP/.env"

# --------------------------------------------------------------- systemd

say "Настраиваю автозапуск"
$SUDO tee "/etc/systemd/system/$SERVICE.service" >/dev/null <<UNIT
[Unit]
Description=Telegram Stars Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APP
ExecStart=$APP/.venv/bin/python -m app.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Бот работает с деньгами — ограничиваем ему доступ к системе.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP/data
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
UNIT

# Короткая команда управления, чтобы не помнить длинные пути.
$SUDO tee /usr/local/bin/stars-bot >/dev/null <<HELPER
#!/usr/bin/env bash
# Управление ботом. Создан установщиком, правится там же.
set -euo pipefail
APP="$APP"
SERVICE="$SERVICE"
RUN_USER="$RUN_USER"
INSTALLER="\$APP/install.sh"
RAW_URL="$RAW_INSTALLER"

case "\${1:-help}" in
    update)
        echo "Обновляю бота…"
        # Берём установщик из репозитория: он мог измениться вместе с ботом,
        # а локальная копия — это версия с прошлого обновления.
        FRESH=\$(mktemp)
        if curl -sSL "\$RAW_URL" -o "\$FRESH" 2>/dev/null && [ -s "\$FRESH" ]; then
            exec bash "\$FRESH"
        fi
        echo "Не скачался свежий установщик, беру локальный."
        rm -f "\$FRESH"
        exec bash "\$INSTALLER"
        ;;
    restart) systemctl restart "\$SERVICE" && echo "✅ Перезапущен" ;;
    stop)    systemctl stop "\$SERVICE"    && echo "⏹  Остановлен"  ;;
    start)   systemctl start "\$SERVICE"   && echo "▶️  Запущен"     ;;
    status)  systemctl status "\$SERVICE" --no-pager ;;
    logs)    journalctl -u "\$SERVICE" -f ;;
    errors)  journalctl -u "\$SERVICE" -p err -n 50 --no-pager ;;
    setup)
        sudo -u "\$RUN_USER" "\$APP/.venv/bin/python" "\$APP/setup.py"
        systemctl restart "\$SERVICE" && echo "✅ Настройки применены"
        ;;
    mystars)
        if [ -z "\${2:-}" ]; then
            echo "Использование: stars-bot mystars ВАШ_КЛЮЧ"
            echo "Ключ берётся в @my_stars_tg_bot -> API access"
            exit 1
        fi
        sudo -u "\$RUN_USER" "\$APP/.venv/bin/python" "\$APP/setup.py" --set \
            FRAGMENT_MODE=mystars \
            MYSTARS_API_KEY="\$2" \
            MYSTARS_BASE_URL=https://api.mystars.tg/v1 \
            MYSTARS_CURRENCY="\${3:-ton}"
        systemctl restart "\$SERVICE"
        echo "✅ MyStars подключён, бот перезапущен"
        echo "   Проверьте: /panel -> Проверить связь"
        ;;
    apifragment)
        if [ -z "\${2:-}" ]; then
            echo "Использование: stars-bot apifragment ВАШ_ТОКЕН"
            exit 1
        fi
        sudo -u "\$RUN_USER" "\$APP/.venv/bin/python" "\$APP/setup.py" --set \
            FRAGMENT_MODE=api FRAGMENT_API_KEY="\$2"
        systemctl restart "\$SERVICE"
        echo "✅ ApiFragment подключён (сид-фразу задайте через stars-bot setup)"
        ;;
    mock)
        sudo -u "\$RUN_USER" "\$APP/.venv/bin/python" "\$APP/setup.py" --set FRAGMENT_MODE=mock
        systemctl restart "\$SERVICE" && echo "✅ Режим проверки: звёзды не отправляются"
        ;;
    backup)
        DEST="/root/stars-bot-backup-\$(date +%Y%m%d-%H%M%S).sqlite3"
        cp "\$APP/data/bot.sqlite3" "\$DEST"
        echo "✅ Копия базы: \$DEST"
        ;;
    *)
        cat <<TXT
Управление ботом:

  stars-bot update    обновить код и перезапустить
  stars-bot restart   перезапустить
  stars-bot stop      остановить
  stars-bot start     запустить
  stars-bot status    работает ли
  stars-bot logs      смотреть логи живьём (Ctrl+C — выйти)
  stars-bot errors    последние ошибки
  stars-bot setup     изменить настройки и перезапустить
  stars-bot backup    сохранить копию базы

Подключение выдачи одной командой:
  stars-bot mystars КЛЮЧ       выдача через MyStars (ключ из @my_stars_tg_bot)
  stars-bot apifragment ТОКЕН  выдача через apifragment.online
  stars-bot mock               режим проверки, звёзды не отправляются

Все команды запускать через sudo.
TXT
        ;;
esac
HELPER
$SUDO chmod +x /usr/local/bin/stars-bot

$SUDO systemctl daemon-reload
$SUDO systemctl enable --quiet "$SERVICE"
$SUDO systemctl restart "$SERVICE"
ok "Бот будет сам подниматься после перезагрузки и падений"

# ---------------------------------------------------------------- проверка

say "Проверяю запуск"
sleep 5

if $SUDO systemctl is-active --quiet "$SERVICE"; then
    printf "\n\033[1;32m═══════════════════════════════════════════\033[0m\n"
    if $UPDATING; then
        printf "\033[1;32m  ✅ Бот обновлён и работает\033[0m\n"
    else
        printf "\033[1;32m  ✅ Бот запущен\033[0m\n"
    fi
    printf "\033[1;32m═══════════════════════════════════════════\033[0m\n\n"
    echo "  Откройте своего бота в Telegram и нажмите /start"
    echo ""
    echo "  Управление — команда stars-bot:"
    echo ""
    echo "    sudo stars-bot update     обновить и перезапустить"
    echo "    sudo stars-bot logs       смотреть логи живьём"
    echo "    sudo stars-bot status     работает ли"
    echo "    sudo stars-bot restart    перезапустить"
    echo "    sudo stars-bot setup      изменить настройки"
    echo "    sudo stars-bot backup     копия базы"
    echo ""
    echo "  Цены, реквизиты и рассылка — прямо в боте: /panel"
    echo ""
else
    printf "\n\033[1;31m❌ Бот не запустился. Последние строки лога:\033[0m\n\n"
    $SUDO journalctl -u "$SERVICE" -n 25 --no-pager | sed 's/^/    /'
    echo ""
    echo "  Чаще всего причина — неверный токен или незаполненные реквизиты."
    echo "  Исправить: sudo -u $RUN_USER $APP/.venv/bin/python $APP/setup.py"
    echo "  Потом:     sudo systemctl restart $SERVICE"
    echo ""
    exit 1
fi
