#!/usr/bin/env bash
# Установщик AlijonHost — shared-хостинг для PHP на одном VPS.
#
# Использование: sudo bash hosting/install.sh
#
# Идемпотентен: повторный запуск не разрушает существующие данные — каждый шаг
# сначала проверяет, нужно ли вообще что-то делать. Домен задаётся одной
# переменной HOSTING_ROOT_DOMAIN в .env — сменить его можно в любой момент,
# перезапустив install.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOSTING_DIR="${SCRIPT_DIR}"

log()  { echo -e "\033[1;32m==>\033[0m $*"; }
warn() { echo -e "\033[1;33m!!\033[0m $*" >&2; }
die()  { echo -e "\033[1;31mОШИБКА:\033[0m $*" >&2; exit 1; }

STATUS_LINES=()
note_status() { STATUS_LINES+=("$1"); }

# ── 1. root и ОС ─────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Запустите от root (sudo bash install.sh)"

# Весь вывод дублируется в файл: если установка оборвётся, лог останется, и не
# придётся вспоминать, что было на экране.
INSTALL_LOG="/var/log/hosting-install.log"
exec > >(tee -a "$INSTALL_LOG") 2>&1
echo "=== установка запущена $(date -u +%FT%TZ) ==="

# Из-за set -e любая неудачная команда обрывает скрипт молча, оставляя систему
# в половинчатом состоянии и без объяснений. Ловим это и говорим прямо, на чём
# именно споткнулись, — иначе потом гадать по симптомам.
trap 'code=$?; echo -e "\033[1;31mОБОРВАЛОСЬ\033[0m на строке ${LINENO}, код ${code}: ${BASH_COMMAND}" >&2;
      echo "Полный лог: ${INSTALL_LOG}" >&2;
      echo "Установка идемпотентна — после исправления запустите её заново." >&2' ERR

if [[ ! -f /etc/os-release ]]; then
  die "Не удалось определить ОС (/etc/os-release не найден)"
fi
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
  ubuntu|debian) log "ОС: ${PRETTY_NAME:-$ID}" ;;
  *) die "Поддерживаются только Ubuntu/Debian, обнаружено: ${ID:-неизвестно}" ;;
esac

# ── 2. .env ──────────────────────────────────────────────────────────────
#
# У хостинга СВОЙ файл настроек — hosting/.env. Раньше использовался .env в
# корне репозитория, но оттуда же читает Telegram-бот учёта денег (bot/), и обе
# программы берут переменную с одним именем — TELEGRAM_BOT_TOKEN. В итоге
# хостинг работал с токеном чужого бота, а два процесса одновременно опрашивали
# getUpdates одного и того же бота и перехватывали сообщения друг у друга:
# на /start пользователь то получал ответ, то нет.
ENV_FILE="${REPO_ROOT}/hosting/.env"
LEGACY_ENV="${REPO_ROOT}/.env"

# Перенос со старой схемы: значения настроек хостинга копируем к себе, чужой
# файл не трогаем — он принадлежит другому проекту.
if [[ ! -f "$ENV_FILE" && -f "$LEGACY_ENV" ]]; then
  log "Переношу настройки хостинга из ${LEGACY_ENV} в ${ENV_FILE}"
  cp "${HOSTING_DIR}/.env.example" "$ENV_FILE"
  MOVED=()
  while IFS= read -r line; do
    [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)= ]] || continue
    key="${BASH_REMATCH[1]}"
    old_value=$(grep -E "^${key}=" "$LEGACY_ENV" 2>/dev/null | head -1 | cut -d= -f2-)
    [[ -n "$old_value" ]] || continue
    escaped=$(printf '%s' "$old_value" | sed -e 's/[\&|]/\\&/g')
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$ENV_FILE"
    MOVED+=("$key")
  done < "${HOSTING_DIR}/.env.example"
  [[ ${#MOVED[@]} -gt 0 ]] && log "Перенесено настроек: ${#MOVED[@]}"

  # Токен бота НЕ переносим: в старом общем файле почти наверняка лежит токен
  # другого бота, и молча его унаследовать — значит повторить ту же путаницу.
  if grep -qE '^TELEGRAM_BOT_TOKEN=.+' "$ENV_FILE"; then
    sed -i 's|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=|' "$ENV_FILE"
    sed -i 's|^TELEGRAM_BOT_USERNAME=.*|TELEGRAM_BOT_USERNAME=|' "$ENV_FILE"
    note_status "Токен Telegram НЕ перенесён из общего .env — он мог принадлежать другому боту. Задайте токен хостинга: sudo bash ${HOSTING_DIR}/scripts/telegram.sh"
    warn "Токен Telegram не перенесён — задайте его отдельно (см. итог установки)"
  fi
fi

if [[ ! -f "$ENV_FILE" ]]; then
  log "Создаю .env из hosting/.env.example (секреты генерируются автоматически)"
  # Не путать с корневым .env.example — тот принадлежит отдельному проекту
  # (Telegram-бот учёта денег) в этом же репозитории и его не трогаем.
  cp "${HOSTING_DIR}/.env.example" "$ENV_FILE"
  DB_PASS=$(openssl rand -base64 24 | tr -d '=+/')
  SESSION_SECRET=$(openssl rand -hex 32)
  sed -i "s#^DB_PASSWORD=.*#DB_PASSWORD=${DB_PASS}#" "$ENV_FILE"
  sed -i "s#^SESSION_SECRET=.*#SESSION_SECRET=${SESSION_SECRET}#" "$ENV_FILE"
  chown root:root "$ENV_FILE"
  chmod 0640 "$ENV_FILE"
  note_status "Создан .env — ЗАПОЛНИТЕ HOSTING_ROOT_DOMAIN, HOSTING_SERVER_IP, TELEGRAM_BOT_TOKEN вручную"
else
  log ".env уже существует — дополняю недостающим"
fi

# Существующий .env чиним, а не пропускаем.
#
# «Файл есть — не трогаю» ломалось двумя способами. Во-первых, в корне репозитория
# может лежать .env совсем другого проекта (Telegram-бот учёта денег) — тогда в нём
# нет ни одной настройки хостинга. Во-вторых, прерванный прошлый запуск оставлял
# .env без сгенерированных секретов. И то и другое всплывало гораздо позже —
# строкой «DB_PASSWORD не задан в .env» посреди настройки MariaDB.
ENV_ADDED=()
while IFS= read -r line; do
  [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || continue
  key="${line%%=*}"
  grep -qE "^${key}=" "$ENV_FILE" && continue
  if [[ ${#ENV_ADDED[@]} -eq 0 ]]; then
    printf '\n# Добавлено install.sh: настройки хостинга, которых не хватало.\n' >> "$ENV_FILE"
  fi
  printf '%s\n' "$line" >> "$ENV_FILE"
  ENV_ADDED+=("$key")
done < "${HOSTING_DIR}/.env.example"
[[ ${#ENV_ADDED[@]} -gt 0 ]] && log "В .env добавлены недостающие настройки: ${ENV_ADDED[*]}"

env_value() { grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-; }

# Секреты генерируем, если их нет ИЛИ они пустые — без этого установка
# доходила до MariaDB и падала там.
if [[ -z "$(env_value DB_PASSWORD)" ]]; then
  sed -i "s#^DB_PASSWORD=.*#DB_PASSWORD=$(openssl rand -base64 24 | tr -d '=+/')#" "$ENV_FILE"
  log "Сгенерирован пароль панельной базы"
fi
if [[ -z "$(env_value SESSION_SECRET)" ]]; then
  sed -i "s#^SESSION_SECRET=.*#SESSION_SECRET=$(openssl rand -hex 32)#" "$ENV_FILE"
  log "Сгенерирован SESSION_SECRET"
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

HOSTING_ROOT_DOMAIN="${HOSTING_ROOT_DOMAIN:-diyorhost.com}"
HOSTING_ROOT="${HOSTING_ROOT:-/opt/hosting}"
HOSTING_USERS_ROOT="${HOSTING_USERS_ROOT:-/home/hosting}"
PHP_REQUESTED="${PHP_VERSIONS:-8.3}"
PHP_REQUESTED="${PHP_REQUESTED%%,*}"
SSH_PORT="${HOSTING_SSH_PORT:-22}"
LOG_DIR="${LOG_DIR:-/var/log/hosting}"

log "Базовый домен: ${HOSTING_ROOT_DOMAIN}"

# ── 3. зависимости ───────────────────────────────────────────────────────
log "Устанавливаю пакеты (может занять несколько минут)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

# Версия PHP не зашита в код: на разных выпусках Ubuntu/Debian в репозиториях
# лежат разные версии (24.04 — 8.3, 26.04 — уже новее). Берём запрошенную, если
# она есть, иначе самую свежую доступную php*-fpm.
detect_php_version() {
  local requested="$1"
  if apt-cache policy "php${requested}-fpm" 2>/dev/null | grep -qE 'Candidate: [0-9]'; then
    echo "$requested"
    return 0
  fi
  apt-cache search --names-only '^php[0-9]+\.[0-9]+-fpm$' 2>/dev/null \
    | grep -oE 'php[0-9]+\.[0-9]+' | sed 's/^php//' | sort -V | tail -1
}

PHP_VERSION="$(detect_php_version "$PHP_REQUESTED")"
[[ -n "$PHP_VERSION" ]] || die "В репозиториях нет ни одного пакета php*-fpm — проверьте apt sources"

if [[ "$PHP_VERSION" != "$PHP_REQUESTED" ]]; then
  warn "PHP ${PHP_REQUESTED} в репозиториях нет — ставлю PHP ${PHP_VERSION} и правлю .env под него"
  note_status "PHP: вместо ${PHP_REQUESTED} используется ${PHP_VERSION} (что есть в репозиториях этой ОС)"
fi
log "Версия PHP: ${PHP_VERSION}"

# Панель и воркер должны знать ту же версию, что реально установлена, —
# иначе пулы будут писаться не в тот каталог, а reload дёргать несуществующий юнит.
sed -i "s#^PHP_VERSIONS=.*#PHP_VERSIONS=${PHP_VERSION}#" "$ENV_FILE"
sed -i "s#^FPM_POOL_DIR=.*#FPM_POOL_DIR=/etc/php/${PHP_VERSION}/fpm/pool.d#" "$ENV_FILE"
export PHP_VERSIONS="$PHP_VERSION"
export FPM_POOL_DIR="/etc/php/${PHP_VERSION}/fpm/pool.d"
# Ставит только те пакеты из списка, которые реально есть в репозиториях.
# Нужно, потому что набор пакетов PHP отличается между выпусками: например,
# в Ubuntu 26.04 отдельного php8.5-opcache нет — opcache вшит в основной пакет.
apt_install_available() {
  local available=() missing=() pkg
  for pkg in "$@"; do
    if apt-cache show "$pkg" >/dev/null 2>&1; then
      available+=("$pkg")
    else
      missing+=("$pkg")
    fi
  done
  [[ ${#missing[@]} -eq 0 ]] || log "Нет в репозиториях (пропускаю): ${missing[*]}"
  [[ ${#available[@]} -eq 0 ]] && return 0
  apt-get install -qq -y "${available[@]}" >/dev/null
}

apt_install_available \
  nginx mariadb-server mariadb-client \
  certbot python3-certbot-nginx \
  fail2ban nftables \
  curl unzip zip tar openssl quota \
  || die "Не удалось установить базовые пакеты — смотрите вывод выше"

apt_install_available \
  "php${PHP_VERSION}-fpm" "php${PHP_VERSION}-cli" "php${PHP_VERSION}-mysql" \
  "php${PHP_VERSION}-mbstring" "php${PHP_VERSION}-xml" "php${PHP_VERSION}-curl" \
  "php${PHP_VERSION}-zip" "php${PHP_VERSION}-gd" "php${PHP_VERSION}-opcache" \
  || die "Не удалось установить пакеты PHP — смотрите вывод выше"

# Проверяем не имена пакетов, а что расширения реально доступны PHP: имена
# пакетов от версии к версии меняются, а вот без pdo_mysql и zip панель работать
# не сможет в принципе, поэтому на них останавливаемся.
PHP_MODULES="$(php -m 2>/dev/null || true)"
for ext in pdo_mysql zip mbstring; do
  grep -qi "^${ext}$" <<<"$PHP_MODULES" \
    || die "PHP-расширение ${ext} не установлено и не встроено — панель без него не запустится"
done
for ext in curl gd simplexml; do
  grep -qi "^${ext}$" <<<"$PHP_MODULES" \
    || warn "Нет PHP-расширения ${ext} — панели оно не нужно, но сайтам клиентов (WordPress) пригодится"
done
grep -qi "opcache" <<<"$PHP_MODULES" \
  || warn "OPcache не активен — сайты будут работать заметно медленнее"

log "Пакеты установлены (PHP ${PHP_VERSION})"

# ── 4. системные пользователи/группы ────────────────────────────────────
log "Создаю служебные группы и пользователей панели"
getent group hosting-sftp   >/dev/null || groupadd hosting-sftp
getent group hosting-admins >/dev/null || groupadd hosting-admins
# Общая группа веб-слоя: каталоги клиентов принадлежат ей, и через неё файлы
# видят и панель (файловый менеджер), и nginx (проверка существования файла и
# отдача статики). Без неё nginx отвечает 404 на любой сайт клиента.
getent group hosting-web    >/dev/null || groupadd hosting-web
id -u hosting-panel >/dev/null 2>&1 || \
  useradd --system --home-dir "${HOSTING_ROOT}" --shell /usr/sbin/nologin hosting-panel
id -u phpmyadmin    >/dev/null 2>&1 || \
  useradd --system --home-dir /var/www/phpmyadmin --shell /usr/sbin/nologin phpmyadmin

# Членство в группе процесс получает только при запуске, поэтому ниже (шаг 9/10)
# nginx и php-fpm перезапускаются, а не перечитывают конфиг.
usermod -aG hosting-web hosting-panel
id -u www-data >/dev/null 2>&1 && usermod -aG hosting-web www-data

# ── 4b. каталог проекта должен быть доступен веб-процессу ────────────────
#
# nginx и php-fpm панели читают её файлы прямо с диска под пользователем
# hosting-panel. Клон в /root (права 0700) означает 404 на каждой странице
# панели и «Could not open input file» у бота — сколько бы всё остальное ни
# было настроено правильно.
#
# Проверяем не биты прав, а ФАКТ: пусть сам hosting-panel попробует открыть
# index.php панели. Любая арифметика по правам каталогов — это предсказание,
# которое может разойтись с реальностью (ACL, монтирование, неожиданный режим
# промежуточного каталога), а su -c даёт ровно тот ответ, который получит
# php-fpm. Первая версия этой проверки считала биты — и на боевом сервере
# разошлась с тем, что видел doctor.sh.
HOSTING_PANEL_HOME="/opt/hosting-panel"
PANEL_INDEX_REL="hosting/panel/public/index.php"

panel_user_can_read() {
  su -s /bin/sh hosting-panel -c "test -r '$1/${PANEL_INDEX_REL}'" 2>/dev/null
}

if [[ -z "${HOSTING_RELOCATED:-}" ]] && ! panel_user_can_read "$REPO_ROOT"; then
  warn "Пользователь hosting-panel не может прочитать ${REPO_ROOT}/${PANEL_INDEX_REL}"
  warn "Панель в таком расположении отдавала бы 404 на каждой странице"

  if [[ -e "$HOSTING_PANEL_HOME" && "$(readlink -f "$HOSTING_PANEL_HOME")" != "$(readlink -f "$REPO_ROOT")" ]]; then
    die "Нужно перенести проект в ${HOSTING_PANEL_HOME}, но там уже что-то есть.
     Уберите или переименуйте ${HOSTING_PANEL_HOME} и запустите установку заново."
  fi

  log "Переношу проект в ${HOSTING_PANEL_HOME}"
  mv "$REPO_ROOT" "$HOSTING_PANEL_HOME" || die "Не удалось перенести проект в ${HOSTING_PANEL_HOME}"
  chmod 0755 "$HOSTING_PANEL_HOME"
  # Симлинк на старом месте: `cd ~/<проект> && git pull` продолжает работать.
  ln -sfn "$HOSTING_PANEL_HOME" "$REPO_ROOT"

  if ! panel_user_can_read "$HOSTING_PANEL_HOME"; then
    die "Даже после переноса в ${HOSTING_PANEL_HOME} пользователь hosting-panel не читает файлы панели.
     Проверьте права: ls -ld ${HOSTING_PANEL_HOME} ${HOSTING_PANEL_HOME}/hosting/panel/public"
  fi

  log "Проект перенесён, панель теперь читается веб-процессом"
  note_status "Проект перенесён в ${HOSTING_PANEL_HOME} (на старом месте оставлен симлинк, git pull работает как раньше)"
  export HOSTING_RELOCATED=1
  exec bash "${HOSTING_PANEL_HOME}/hosting/install.sh" "$@"
fi

# .env читают трое: root-воркер (root), веб-процесс панели и бот (оба —
# hosting-panel). С владельцем root:root и правами 0640 панель свой же конфиг
# прочитать НЕ МОЖЕТ: молча получает пустой пароль от базы и не поднимается.
# Поэтому группа — hosting-panel, и выставляем это при каждом запуске, а не
# только при создании файла (пользователь появляется позже самого .env).
chown root:hosting-panel "$ENV_FILE"
chmod 0640 "$ENV_FILE"

# ── 4c. права на уже существующих клиентов ───────────────────────────────
#
# Каталоги, созданные прошлыми версиями, имеют права client:client 0750: панель
# под ними не может ни прочитать, ни изменить файлы, а nginx отдаёт 404 на сайт.
# Новые каталоги создаются правильно, но уже существующие надо починить здесь —
# иначе у тех, кто обновляется, файловый менеджер и сайты останутся сломанными.
if [[ -d "$HOSTING_USERS_ROOT" ]]; then
  FIXED=0
  for home in "${HOSTING_USERS_ROOT}"/client*; do
    [[ -d "$home" ]] || continue
    client=$(basename "$home")
    id -u "$client" >/dev/null 2>&1 || continue

    for sub in sites logs tmp backups; do
      [[ -d "${home}/${sub}" ]] || continue
      chown -R "${client}:hosting-web" "${home}/${sub}" 2>/dev/null || continue
      find "${home}/${sub}" -type d -exec chmod 2770 {} \; -o -type f -exec chmod 0664 {} \; 2>/dev/null
    done

    # Корень домашнего каталога обязан оставаться root:root 0755 — это требование
    # OpenSSH к ChrootDirectory для SFTP (см. UnixProvisioner::createUser).
    chown root:root "$home" && chmod 0755 "$home"
    FIXED=$((FIXED+1))
  done
  [[ $FIXED -gt 0 ]] && log "Права приведены в порядок у клиентов: ${FIXED}"
fi
chmod 0755 "$HOSTING_USERS_ROOT" 2>/dev/null || true

# ── 5. каталоги ──────────────────────────────────────────────────────────
#
# HOSTING_ROOT приводим в порядок ПЕРВЫМ делом, до создания подкаталогов.
# Раньше было наоборот: mkdir -p "${HOSTING_ROOT}/backups" сам создавал
# /opt/hosting обычным каталогом, после чего проверка ниже находила там не
# симлинк и просто предупреждала. В результате на каждой чистой установке
# HOSTING_ROOT оставался пустым каталогом, а все systemd-юниты ссылались на
# ${HOSTING_ROOT}/hosting/worker/bin/... — файла по этому пути не существовало,
# служба падала с 203/EXEC и навсегда висела в состоянии activating.
log "Проверяю ${HOSTING_ROOT}"
REPO_REAL="$(readlink -f "$REPO_ROOT")"

# Сравниваем НЕПОСРЕДСТВЕННУЮ цель симлинка, а не конечную. После переноса
# проекта получалась цепочка /opt/hosting -> /root/<проект> -> /opt/hosting-panel:
# readlink -f разрешает её в правильный путь, но www-data, проходя по ней,
# упирается в /root с правами 0700 и получает отказ. Цепочку через /root надо
# спрямлять, а не считать исправной.
if [[ -L "$HOSTING_ROOT" && "$(readlink "$HOSTING_ROOT")" == "$REPO_ROOT" ]]; then
  log "${HOSTING_ROOT} уже указывает на репозиторий"
elif [[ ! -e "$HOSTING_ROOT" ]] || [[ -L "$HOSTING_ROOT" ]]; then
  ln -sfn "$REPO_ROOT" "$HOSTING_ROOT"
  log "Симлинк ${HOSTING_ROOT} -> ${REPO_ROOT} создан"
elif [[ -d "$HOSTING_ROOT" ]]; then
  # Обычный каталог на месте HOSTING_ROOT — почти всегда наш же мусор от
  # прошлых запусков (пустые backups/var). Пустой убираем молча; непустой
  # НЕ удаляем, а отодвигаем: там могут лежать резервные копии клиентов.
  if [[ -z "$(find "$HOSTING_ROOT" -mindepth 1 -not -path "*/backups" -not -path "*/var" -print -quit 2>/dev/null)" ]] \
     && [[ -z "$(find "${HOSTING_ROOT}/backups" "${HOSTING_ROOT}/var" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
    rm -rf "${HOSTING_ROOT:?}"
    ln -sfn "$REPO_ROOT" "$HOSTING_ROOT"
    log "Пустой каталог ${HOSTING_ROOT} заменён симлинком на репозиторий"
  else
    HOSTING_ROOT_OLD="${HOSTING_ROOT}.old-$(date -u +%Y%m%d-%H%M%S)"
    mv "$HOSTING_ROOT" "$HOSTING_ROOT_OLD"
    ln -sfn "$REPO_ROOT" "$HOSTING_ROOT"
    warn "${HOSTING_ROOT} был обычным каталогом с данными — перенесён в ${HOSTING_ROOT_OLD}"
    note_status "Старое содержимое ${HOSTING_ROOT} лежит в ${HOSTING_ROOT_OLD} (ничего не удалено) — проверьте, нет ли там резервных копий"
  fi
else
  die "${HOSTING_ROOT} существует и это не каталог и не симлинк — уберите его вручную"
fi

log "Создаю каталоги"
mkdir -p "$HOSTING_USERS_ROOT" "$LOG_DIR" "${HOSTING_ROOT}/backups" "${HOSTING_ROOT}/var" \
  /etc/hosting /run/php /var/lib/hosting
# Единственное, что пишет бот, — offset обработанных сообщений Telegram.
chown hosting-panel:hosting-panel /var/lib/hosting
chmod 0750 /var/lib/hosting
chmod 0755 "$HOSTING_USERS_ROOT"
chmod 0755 "$LOG_DIR"

# ── 6. worker.env (секреты, доступные ТОЛЬКО root-воркеру) ──────────────
WORKER_ENV="/etc/hosting/worker.env"
if [[ ! -f "$WORKER_ENV" ]]; then
  log "Создаю ${WORKER_ENV} (MYSQL_ADMIN_PASSWORD и т.п. — панель их не видит)"
  MYSQL_ROOT_PASS=$(openssl rand -base64 24 | tr -d '=+/')
  cat > "$WORKER_ENV" <<EOF
# Секреты root-воркера. НЕ читается веб-процессом панели (см. Config.php).
MYSQL_ADMIN_USER=root
MYSQL_ADMIN_PASSWORD=${MYSQL_ROOT_PASS}
EOF
  chown root:root "$WORKER_ENV"
  chmod 0600 "$WORKER_ENV"
  note_status "Пароль root MariaDB сгенерирован в ${WORKER_ENV} — установите его в MariaDB (см. шаг ниже) или впишите свой"
else
  log "${WORKER_ENV} уже существует — не трогаю"
fi
set -a
# shellcheck disable=SC1090
. "$WORKER_ENV"
set +a

# ── 7. MariaDB ───────────────────────────────────────────────────────────
log "Настраиваю MariaDB"

# Каталог для conf.d у разных сборок называется по-разному, а у MySQL он вообще
# другой. Берём первый существующий, а не предполагаем один жёстко зашитый путь.
MYSQL_CONF_DIR=""
for dir in /etc/mysql/mariadb.conf.d /etc/mysql/conf.d /etc/my.cnf.d; do
  [[ -d "$dir" ]] && { MYSQL_CONF_DIR="$dir"; break; }
done
[[ -n "$MYSQL_CONF_DIR" ]] || die "Не нашёл каталог конфигов MariaDB (проверял mariadb.conf.d, conf.d, my.cnf.d)"

# Конфиг пишет slow/error log в /var/log/mysql — если каталога нет или он чужой,
# MariaDB просто не поднимется после рестарта.
mkdir -p /var/log/mysql
chown mysql:mysql /var/log/mysql 2>/dev/null || warn "Не удалось выставить владельца /var/log/mysql"

install -m 0644 "${HOSTING_DIR}/etc/mariadb/hosting.cnf" "${MYSQL_CONF_DIR}/60-hosting.cnf"
log "Конфиг MariaDB: ${MYSQL_CONF_DIR}/60-hosting.cnf"
systemctl enable --now mariadb >/dev/null

# Если MariaDB не переживёт наш конфиг — убираем его и поднимаем сервер обратно,
# а не оставляем клиента с лежащей базой.
if ! systemctl restart mariadb; then
  rm -f "${MYSQL_CONF_DIR}/60-hosting.cnf"
  systemctl restart mariadb || true
  journalctl -u mariadb -n 20 --no-pager >&2 || true
  die "MariaDB не стартовала с нашим конфигом — конфиг удалён, сервер поднят обратно (лог выше)"
fi

# Свежий apt-пакет mariadb-server пускает root без пароля через unix_socket (мы и есть
# root, раз дошли до этой строки). Если так — ставим пароль из worker.env и на этом
# unix_socket-доступ для root заменяется на обычный пароль. Повторный запуск install.sh
# увидит, что "mysql -uroot" без пароля уже не работает, и просто пропустит этот блок —
# идемпотентно.
if mysql -uroot -e "SELECT 1" >/dev/null 2>&1; then
  mysql -uroot -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ADMIN_PASSWORD}'; FLUSH PRIVILEGES;" \
    2>/dev/null || warn "Не удалось автоматически установить пароль root MariaDB — сделайте это вручную и обновите ${WORKER_ENV}"
fi

# Панельная БД + её собственный (непривилегированный) пользователь
DB_DATABASE="${DB_DATABASE:-hosting_panel}"
DB_USERNAME="${DB_USERNAME:-hosting_panel}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD не задан в .env}"
mysql -uroot -p"${MYSQL_ADMIN_PASSWORD}" <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_DATABASE}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- 'user'@'localhost' и 'user'@'127.0.0.1' — для MariaDB это РАЗНЫЕ учётки:
-- первая пускает через unix-сокет, вторая по TCP. Панель ходит по TCP
-- (DB_HOST=127.0.0.1), поэтому заводим обе, иначе получаем ошибку 1130.
CREATE USER IF NOT EXISTS '${DB_USERNAME}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
CREATE USER IF NOT EXISTS '${DB_USERNAME}'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWORD}';
-- CREATE USER IF NOT EXISTS для СУЩЕСТВУЮЩЕЙ учётки не делает ничего: пароль
-- остаётся прежним, и никакой ошибки при этом нет. После перегенерации
-- DB_PASSWORD в .env получалось расхождение и «Access denied ... (using
-- password: YES)» уже на миграциях. Поэтому пароль выставляем явно.
ALTER USER '${DB_USERNAME}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USERNAME}'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_DATABASE}\`.* TO '${DB_USERNAME}'@'localhost';
GRANT ALL PRIVILEGES ON \`${DB_DATABASE}\`.* TO '${DB_USERNAME}'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
log "БД панели готова (${DB_DATABASE})"

# Проверяем учётку ровно так, как ею пользуется панель: по TCP, с паролем из
# .env. Если тут отказ — дальше падать будет на миграциях, где сообщение
# ничего не объясняет.
DB_HOST_CHECK="${DB_HOST:-127.0.0.1}"
DB_PORT_CHECK="${DB_PORT:-3306}"
if mysql -h "$DB_HOST_CHECK" -P "$DB_PORT_CHECK" -u"${DB_USERNAME}" -p"${DB_PASSWORD}" \
     -e "USE \`${DB_DATABASE}\`" >/dev/null 2>&1; then
  log "Панель может войти в свою базу (${DB_USERNAME}@${DB_HOST_CHECK})"
else
  die "Пользователь ${DB_USERNAME}@${DB_HOST_CHECK} не может войти в базу ${DB_DATABASE} с паролем из ${ENV_FILE}.
     Проверьте вручную:
       mysql -h ${DB_HOST_CHECK} -u${DB_USERNAME} -p'<пароль из .env>' -e 'SELECT 1'"
fi

# ── 8. миграции ──────────────────────────────────────────────────────────
log "Применяю миграции панели"
php "${HOSTING_DIR}/panel/bin/migrate.php"

# ── 9. nginx: базовый сниппет + панель ───────────────────────────────────
log "Настраиваю nginx"

# На машине без IPv6 nginx не просто игнорирует `listen [::]…`, а валится на
# проверке конфига целиком: «socket() [::]:80 failed (97: Address family not
# supported by protocol)». Не применяется НИ ОДИН сайт, включая панель.
# Отсутствие /proc/net/if_inet6 — стандартный признак выключенного IPv6.
strip_ipv6_if_unavailable() {
  [[ -e /proc/net/if_inet6 ]] && return 0
  sed -i -E '/^[[:space:]]*listen[[:space:]]+\[::\]/d' "$@"
}
if [[ ! -e /proc/net/if_inet6 ]]; then
  warn "IPv6 в системе выключен — убираю строки listen [::] из конфигов nginx"
fi
mkdir -p /etc/nginx/conf.d /etc/nginx/sites-available /etc/nginx/sites-enabled
sed "s/{{PANEL_NAME}}/${PANEL_NAME:-AlijonHost}/g" \
  "${HOSTING_DIR}/templates/nginx-global-hosting.conf.tpl" > /etc/nginx/conf.d/hosting-global.conf

# Один vhost на панель и на публичную витрину: маршрут «/» сам решает, что показать.
strip_ipv6_if_unavailable /etc/nginx/conf.d/hosting-global.conf

# nginx считает повтор server_tokens в пределах http{} ошибкой, а не
# переопределением: «server_tokens directive is duplicate». Валится при этом
# ВЕСЬ конфиг, то есть панель не включается вообще. В nginx.conf разных
# выпусков эта директива то закомментирована (Ubuntu 24.04), то активна
# (Ubuntu 26.04) — поэтому смотрим на факт, а не на версию. Значение у нас и
# у дистрибутива одинаковое (off), так что убрать нашу строку ничего не меняет.
if grep -qE '^[[:space:]]*server_tokens' /etc/nginx/nginx.conf 2>/dev/null; then
  sed -i -E '/^[[:space:]]*server_tokens/d' /etc/nginx/conf.d/hosting-global.conf
  log "server_tokens уже задан в nginx.conf — не дублирую"
fi
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/www/html   # сюда certbot кладёт файл проверки HTTP-01

# Сам vhost собирает отдельный скрипт: он же вызывается из setup.sh сразу после
# выпуска сертификата, чтобы панель переехала на HTTPS без ручной правки конфига.
systemctl enable nginx >/dev/null 2>&1 || true
systemctl start nginx >/dev/null 2>&1 || true
if bash "${HOSTING_DIR}/scripts/apply-panel-vhost.sh"; then
  log "nginx настроен и перезагружен"
else
  die "vhost панели не применился (вывод выше) — панель не заработает, пока это не исправлено"
fi

# ── 10. php-fpm: пул панели ──────────────────────────────────────────────
log "Настраиваю php-fpm пул панели"
sed \
  -e "s#{{HOSTING_ROOT}}#${HOSTING_ROOT}#g" \
  -e "s#{{HOSTING_USERS_ROOT}}#${HOSTING_USERS_ROOT}#g" \
  -e "s#{{UPLOAD_MAX_MB}}#${UPLOAD_MAX_MB:-64}#g" \
  "${HOSTING_DIR}/templates/php-fpm-panel.conf.tpl" > "/etc/php/${PHP_VERSION}/fpm/pool.d/hosting-panel.conf"

if php-fpm"${PHP_VERSION}" -t >/dev/null 2>&1; then
  systemctl enable --now "php${PHP_VERSION}-fpm" >/dev/null
  # Именно restart: reload не перечитывает членство процесса в группах, и панель
  # осталась бы без доступа к каталогам клиентов до первой перезагрузки сервера.
  systemctl restart "php${PHP_VERSION}-fpm"
  log "php-fpm настроен"
else
  warn "php-fpm -t не прошёл — проверьте /etc/php/${PHP_VERSION}/fpm/pool.d/hosting-panel.conf"
fi

# ── 11. root-воркер (systemd) ────────────────────────────────────────────
log "Устанавливаю systemd-юнит воркера"
sed \
  -e "s#{{PANEL_NAME}}#${PANEL_NAME:-AlijonHost}#g" \
  -e "s#{{HOSTING_ROOT}}#${HOSTING_ROOT}#g" \
  -e "s#{{ENV_FILE}}#${WORKER_ENV}#g" \
  "${HOSTING_DIR}/templates/systemd-worker.service.tpl" > /etc/systemd/system/hosting-worker.service

# Бот отвечает на /start и открывает Mini App. Без него бот выглядел бы
# сломанным: кнопка меню есть, а на сообщения никто не отвечает.
sed \
  -e "s#{{PANEL_NAME}}#${PANEL_NAME:-AlijonHost}#g" \
  -e "s#{{HOSTING_ROOT}}#${HOSTING_ROOT}#g" \
  -e "s#{{ENV_FILE}}#${ENV_FILE}#g" \
  "${HOSTING_DIR}/templates/systemd-bot.service.tpl" > /etc/systemd/system/hosting-bot.service

systemctl daemon-reload
systemctl enable --now hosting-worker >/dev/null 2>&1 || warn "Не удалось запустить hosting-worker.service — проверьте journalctl -u hosting-worker"
systemctl enable --now hosting-bot >/dev/null 2>&1 || warn "Не удалось запустить hosting-bot.service — проверьте journalctl -u hosting-bot"

# ── 12. таймеры: monitor / backup / ssl-renew ────────────────────────────
log "Устанавливаю systemd-таймеры (monitor, backup, ssl-renew)"
for name in monitor backup ssl-renew; do
  svc_tpl="${HOSTING_DIR}/templates/systemd-${name}.service.tpl"
  timer_tpl="${HOSTING_DIR}/templates/systemd-${name}.timer.tpl"
  [[ -f "$svc_tpl" ]] || continue
  sed -e "s#{{PANEL_NAME}}#${PANEL_NAME:-AlijonHost}#g" -e "s#{{HOSTING_ROOT}}#${HOSTING_ROOT}#g" \
    -e "s#{{ENV_FILE}}#${ENV_FILE}#g" "$svc_tpl" > "/etc/systemd/system/hosting-${name}.service"
  [[ -f "$timer_tpl" ]] && install -m 0644 "$timer_tpl" "/etc/systemd/system/hosting-${name}.timer"
done
systemctl daemon-reload
systemctl enable --now hosting-monitor.timer hosting-backup.timer hosting-ssl-renew.timer >/dev/null 2>&1 \
  || warn "Не все таймеры включились — проверьте systemctl list-timers"

# ── 13. firewall (nftables) ───────────────────────────────────────────────
log "Настраиваю firewall (nftables)"

# Firewall не должен отрезать то, что на сервере уже работало до нас. Собираем
# порты, опубликованные контейнерами Docker наружу (0.0.0.0:PORT), и порты,
# перечисленные вручную в HOSTING_EXTRA_TCP_PORTS, и оставляем их открытыми.
EXTRA_PORTS="${HOSTING_EXTRA_TCP_PORTS:-}"
DOCKER_RUNNING=0
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  DOCKER_RUNNING=1
  DOCKER_PORTS=$(docker ps --format '{{.Ports}}' 2>/dev/null \
    | grep -oE '0\.0\.0\.0:[0-9]+' | cut -d: -f2 | sort -un | tr '\n' ',' | sed 's/,$//')
  if [[ -n "$DOCKER_PORTS" ]]; then
    EXTRA_PORTS="${EXTRA_PORTS:+${EXTRA_PORTS},}${DOCKER_PORTS}"
    log "Найдены опубликованные наружу порты Docker: ${DOCKER_PORTS} — оставляю открытыми"
    note_status "В firewall открыты порты работавших до установки контейнеров Docker: ${DOCKER_PORTS}. Если какой-то из них наружу не нужен — уберите его из HOSTING_EXTRA_TCP_PORTS и перезапустите install.sh"
  fi
fi

sed "s/define ssh_port = 22/define ssh_port = ${SSH_PORT}/" \
  "${HOSTING_DIR}/etc/nftables/hosting.nft" > /etc/nftables-hosting.conf

if [[ -n "$EXTRA_PORTS" ]]; then
  sed -i "s|# HOSTING_EXTRA_PORTS.*|tcp dport { ${EXTRA_PORTS} } accept|" /etc/nftables-hosting.conf
fi

if [[ $DOCKER_RUNNING -eq 1 ]]; then
  # См. пояснение в самом hosting.nft: policy drop в forward убивает сеть Docker.
  sed -i 's|.*# HOSTING_FORWARD_POLICY|        type filter hook forward priority 0; policy accept;|' \
    /etc/nftables-hosting.conf
  warn "Обнаружен Docker — forward оставлен в policy accept, иначе сеть контейнеров ляжет"
  note_status "Из-за Docker цепочка forward не фильтруется хостингом (иначе контейнеры теряют сеть) — фильтрацией forward управляет сам Docker"
fi
if nft -c -f /etc/nftables-hosting.conf; then
  nft -f /etc/nftables-hosting.conf
  if ! grep -q 'include "/etc/nftables-hosting.conf"' /etc/nftables.conf 2>/dev/null; then
    echo 'include "/etc/nftables-hosting.conf"' >> /etc/nftables.conf
  fi
  systemctl enable --now nftables >/dev/null 2>&1
  log "nftables применены (SSH на порту ${SSH_PORT}, 80/443 открыты)"
else
  warn "nft -c не прошёл проверку синтаксиса — firewall НЕ применён, старые правила (если были) не тронуты"
fi

# ── 14. Fail2ban ─────────────────────────────────────────────────────────
log "Настраиваю Fail2ban"
install -m 0644 "${HOSTING_DIR}/etc/fail2ban/jail.d/hosting.conf" /etc/fail2ban/jail.d/hosting.conf
install -m 0644 "${HOSTING_DIR}/etc/fail2ban/filter.d/hosting-panel-login.conf" /etc/fail2ban/filter.d/hosting-panel-login.conf
systemctl enable --now fail2ban >/dev/null 2>&1
systemctl restart fail2ban || warn "fail2ban не перезапустился — проверьте jail.d/hosting.conf"

# ── 15. hostingctl + sudoers ──────────────────────────────────────────────
log "Устанавливаю hostingctl"
install -m 0755 "${HOSTING_DIR}/scripts/hostingctl" /usr/local/sbin/hostingctl
# Битый файл в /etc/sudoers.d ломает sudo для ВСЕХ, поэтому сначала проверка,
# и только потом установка. Вывод visudo показываем целиком — без него непонятно,
# какая именно строка не понравилась этой версии sudo.
if VISUDO_OUT="$(visudo -cf "${HOSTING_DIR}/etc/sudoers/hosting-admin" 2>&1)"; then
  install -m 0440 "${HOSTING_DIR}/etc/sudoers/hosting-admin" /etc/sudoers.d/hosting-admin
  log "hostingctl установлен, sudoers-правило добавлено"
else
  echo "$VISUDO_OUT" >&2
  die "etc/sudoers/hosting-admin не прошёл visudo -cf (вывод выше) — установка остановлена: битый sudoers сломал бы sudo целиком"
fi

# ── 16. SSH/SFTP ──────────────────────────────────────────────────────────
log "Настраиваю SFTP для клиентов"
# Каталога sshd_config.d может не быть (минимальный образ, свежая установка
# openssh-server). Без mkdir установка обрывалась здесь с «cannot create regular
# file» — на шаге, который к тому же не критичен для запуска хостинга.
if [[ -d /etc/ssh ]]; then
  mkdir -p /etc/ssh/sshd_config.d
  install -m 0644 "${HOSTING_DIR}/etc/ssh/sshd-hosting.conf" /etc/ssh/sshd_config.d/hosting.conf
  if sshd -t 2>/dev/null; then
    systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || \
      warn "Не удалось перезагрузить sshd — проверьте вручную (sshd -t)"
  else
    warn "sshd -t не прошёл — конфиг SFTP записан, но sshd не перезагружен"
    note_status "SFTP для клиентов не активирован: проверьте sshd -t"
  fi
else
  warn "openssh-server не установлен — SFTP для клиентов не настроен"
  note_status "SFTP не настроен: нет /etc/ssh (установите openssh-server и повторите install.sh)"
fi

# ── 17. cloudflare firewall allowlist (если сайты проксируются через Cloudflare) ──
if [[ "${HOSTING_BEHIND_CLOUDFLARE:-false}" == "true" ]]; then
  log "Обновляю allowlist Cloudflare в firewall (публичные IP-диапазоны, токен не нужен)"
  bash "${HOSTING_DIR}/scripts/update-cloudflare-firewall.sh" || warn "update-cloudflare-firewall.sh не удался — проверьте вручную"
else
  log "HOSTING_BEHIND_CLOUDFLARE=false — пропускаю (сайты доступны напрямую по IP сервера)"
fi

# ── 18. тесты ──────────────────────────────────────────────────────────────
log "Прогоняю тесты"
if php "${HOSTING_DIR}/tests/run.php"; then
  log "Все тесты прошли"
else
  warn "Есть проваленные тесты — установка продолжена, но ПРОВЕРЬТЕ вывод выше"
fi

# ── 19. итоговый статус ────────────────────────────────────────────────────
echo
log "Установка завершена. Проверка сервисов:"

SERVICES_OK=1
for svc in nginx "php${PHP_VERSION}-fpm" mariadb hosting-worker hosting-bot fail2ban; do
  # is-active выходит с ненулевым кодом на любом состоянии кроме active, но
  # состояние всё равно печатает. Поэтому подстановка и код возврата берутся
  # раздельно: иначе в вывод попадали бы сразу и "activating", и "неизвестно".
  state=$(systemctl is-active "$svc" 2>/dev/null) || true
  [[ -n "$state" ]] || state="неизвестно"
  printf "  %-20s %s\n" "$svc" "$state"

  if [[ "$state" != "active" ]]; then
    SERVICES_OK=0
    # Показываем причину сразу. Строка "activating" сама по себе не говорит
    # ничего: за ней стоит либо перезапуск по кругу, либо неудачный старт,
    # и разницу видно только в journal.
    echo "    ── почему ${svc} не в состоянии active ──"
    systemctl status "$svc" --no-pager -l 2>&1 | sed -n '1,10p' | sed 's/^/    /'
    journalctl -u "$svc" -n 15 --no-pager 2>&1 | sed 's/^/    /'
    echo
  fi
done

echo
if [[ $SERVICES_OK -eq 1 ]]; then
  log "Все службы работают. Остался один шаг — мастер настройки:"
else
  warn "Часть служб не поднялась (причины напечатаны выше)."
  log "Мастер настройки всё равно можно запускать — он проверит всё ещё раз:"
fi
echo
echo "    sudo bash ${HOSTING_DIR}/setup.sh"
echo
echo "  Он спросит домен, токен бота от @BotFather и пароль администратора,"
echo "  сам впишет всё в ${ENV_FILE}, выпустит SSL и проверит, что панель отвечает."
echo "  Полная диагностика в любой момент: sudo bash ${HOSTING_DIR}/scripts/doctor.sh"
if [[ ${#STATUS_LINES[@]} -gt 0 ]]; then
  echo
  warn "Требует вашего внимания:"
  for line in "${STATUS_LINES[@]}"; do echo "  - $line"; done
fi
