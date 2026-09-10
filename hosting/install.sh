#!/usr/bin/env bash
# Установщик AlijonHost — shared-хостинг для PHP на одном VPS.
#
# Использование: sudo bash hosting/install.sh
#
# Идемпотентен: повторный запуск не разрушает существующие данные — каждый шаг
# сначала проверяет, нужно ли вообще что-то делать. Домен пока не настоящий —
# используется myhost.tj как placeholder (см. .env, переменная HOSTING_ROOT_DOMAIN),
# после получения реального домена достаточно поменять одну эту переменную и
# перезапустить install.sh.

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
ENV_FILE="${REPO_ROOT}/.env"
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
  log ".env уже существует — не трогаю"
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

HOSTING_ROOT_DOMAIN="${HOSTING_ROOT_DOMAIN:-myhost.tj}"
HOSTING_ROOT="${HOSTING_ROOT:-/opt/hosting}"
HOSTING_USERS_ROOT="${HOSTING_USERS_ROOT:-/home/hosting}"
PHP_VERSION="${PHP_VERSIONS:-8.3}"
PHP_VERSION="${PHP_VERSION%%,*}"
SSH_PORT="${HOSTING_SSH_PORT:-22}"
LOG_DIR="${LOG_DIR:-/var/log/hosting}"

log "Базовый домен: ${HOSTING_ROOT_DOMAIN} (placeholder, если ещё не сменили)"

# ── 3. зависимости ───────────────────────────────────────────────────────
log "Устанавливаю пакеты (может занять несколько минут)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -qq -y \
  nginx \
  "php${PHP_VERSION}-fpm" "php${PHP_VERSION}-mysql" "php${PHP_VERSION}-mbstring" \
  "php${PHP_VERSION}-xml" "php${PHP_VERSION}-curl" "php${PHP_VERSION}-zip" \
  "php${PHP_VERSION}-gd" "php${PHP_VERSION}-opcache" "php${PHP_VERSION}-cli" \
  mariadb-server mariadb-client \
  certbot python3-certbot-nginx \
  fail2ban nftables \
  curl unzip zip tar openssl \
  quota \
  >/dev/null || die "apt-get install не прошёл — смотрите вывод выше"
log "Пакеты установлены"

# ── 4. системные пользователи/группы ────────────────────────────────────
log "Создаю служебные группы и пользователей панели"
getent group hosting-sftp   >/dev/null || groupadd hosting-sftp
getent group hosting-admins >/dev/null || groupadd hosting-admins
id -u hosting-panel >/dev/null 2>&1 || \
  useradd --system --home-dir "${HOSTING_ROOT}" --shell /usr/sbin/nologin hosting-panel
id -u phpmyadmin    >/dev/null 2>&1 || \
  useradd --system --home-dir /var/www/phpmyadmin --shell /usr/sbin/nologin phpmyadmin

# ── 5. каталоги ──────────────────────────────────────────────────────────
log "Создаю каталоги"
mkdir -p "$HOSTING_USERS_ROOT" "$LOG_DIR" "${HOSTING_ROOT}/backups" "${HOSTING_ROOT}/var" \
  /etc/hosting /run/php
chmod 0755 "$HOSTING_USERS_ROOT"
chmod 0755 "$LOG_DIR"

# Сам репозиторий должен физически лежать в HOSTING_ROOT (или быть на него
# симлинкнут) — так все *.tpl/scripts/panel пути из .env совпадают с реальностью.
if [[ ! -e "$HOSTING_ROOT" || "$(readlink -f "$HOSTING_ROOT" 2>/dev/null)" != "$(readlink -f "$REPO_ROOT")" ]]; then
  if [[ -e "$HOSTING_ROOT" && ! -L "$HOSTING_ROOT" ]]; then
    warn "${HOSTING_ROOT} уже существует и не является симлинком на репозиторий — оставляю как есть, проверьте вручную"
  else
    ln -sfn "$REPO_ROOT" "$HOSTING_ROOT"
    log "Симлинк ${HOSTING_ROOT} -> ${REPO_ROOT} создан"
  fi
fi

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
install -m 0644 "${HOSTING_DIR}/etc/mariadb/hosting.cnf" /etc/mysql/mariadb.conf.d/60-hosting.cnf
systemctl enable --now mariadb >/dev/null
systemctl restart mariadb

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
CREATE USER IF NOT EXISTS '${DB_USERNAME}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_DATABASE}\`.* TO '${DB_USERNAME}'@'localhost';
FLUSH PRIVILEGES;
SQL
log "БД панели готова (${DB_DATABASE})"

# ── 8. миграции ──────────────────────────────────────────────────────────
log "Применяю миграции панели"
php "${HOSTING_DIR}/panel/bin/migrate.php"

# ── 9. nginx: базовый сниппет + панель ───────────────────────────────────
log "Настраиваю nginx"
mkdir -p /etc/nginx/conf.d /etc/nginx/sites-available /etc/nginx/sites-enabled
sed "s/{{PANEL_NAME}}/${PANEL_NAME:-AlijonHost}/g" \
  "${HOSTING_DIR}/templates/nginx-global-hosting.conf.tpl" > /etc/nginx/conf.d/hosting-global.conf

PANEL_DOMAIN="panel.${HOSTING_ROOT_DOMAIN}"
sed \
  -e "s#{{PANEL_NAME}}#${PANEL_NAME:-AlijonHost}#g" \
  -e "s#{{PANEL_DOMAIN}}#${PANEL_DOMAIN}#g" \
  -e "s#{{PANEL_ROOT}}#${HOSTING_ROOT}/hosting/panel/public#g" \
  -e "s#{{LOG_DIR}}#${LOG_DIR}#g" \
  -e "s#{{UPLOAD_MAX_MB}}#${UPLOAD_MAX_MB:-64}#g" \
  "${HOSTING_DIR}/templates/nginx-panel.conf.tpl" > /etc/nginx/sites-available/panel.conf
ln -sfn /etc/nginx/sites-available/panel.conf /etc/nginx/sites-enabled/panel.conf
rm -f /etc/nginx/sites-enabled/default

if nginx -t >/dev/null 2>&1; then
  systemctl enable --now nginx >/dev/null
  systemctl reload nginx
  log "nginx настроен и перезагружен"
else
  warn "nginx -t не прошёл — проверьте /etc/nginx/sites-available/panel.conf вручную"
fi

# ── 10. php-fpm: пул панели ──────────────────────────────────────────────
log "Настраиваю php-fpm пул панели"
sed \
  -e "s#{{HOSTING_ROOT}}#${HOSTING_ROOT}#g" \
  -e "s#{{UPLOAD_MAX_MB}}#${UPLOAD_MAX_MB:-64}#g" \
  "${HOSTING_DIR}/templates/php-fpm-panel.conf.tpl" > "/etc/php/${PHP_VERSION}/fpm/pool.d/hosting-panel.conf"

if php-fpm"${PHP_VERSION}" -t >/dev/null 2>&1; then
  systemctl enable --now "php${PHP_VERSION}-fpm" >/dev/null
  systemctl reload "php${PHP_VERSION}-fpm"
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

systemctl daemon-reload
systemctl enable --now hosting-worker >/dev/null 2>&1 || warn "Не удалось запустить hosting-worker.service — проверьте journalctl -u hosting-worker"

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
sed "s/define ssh_port = 22/define ssh_port = ${SSH_PORT}/" \
  "${HOSTING_DIR}/etc/nftables/hosting.nft" > /etc/nftables-hosting.conf
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
if visudo -cf "${HOSTING_DIR}/etc/sudoers/hosting-admin" >/dev/null 2>&1; then
  install -m 0440 "${HOSTING_DIR}/etc/sudoers/hosting-admin" /etc/sudoers.d/hosting-admin
else
  die "etc/sudoers/hosting-admin не прошёл visudo -cf — установка остановлена (это критично)"
fi

# ── 16. SSH/SFTP ──────────────────────────────────────────────────────────
log "Настраиваю SFTP для клиентов"
install -m 0644 "${HOSTING_DIR}/etc/ssh/sshd-hosting.conf" /etc/ssh/sshd_config.d/hosting.conf
sshd -t 2>/dev/null && systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || \
  warn "Не удалось перезагрузить sshd — проверьте конфиг вручную (sshd -t)"

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
for svc in nginx "php${PHP_VERSION}-fpm" mariadb hosting-worker fail2ban; do
  state=$(systemctl is-active "$svc" 2>/dev/null || echo "неизвестно")
  printf "  %-20s %s\n" "$svc" "$state"
done

echo
log "Дальнейшие шаги:"
echo "  1. Направьте DNS: A ${HOSTING_ROOT_DOMAIN} -> IP сервера, A *.${HOSTING_ROOT_DOMAIN} -> IP сервера"
echo "  2. Впишите реальный HOSTING_ROOT_DOMAIN и HOSTING_SERVER_IP в ${ENV_FILE}"
echo "  3. Впишите TELEGRAM_BOT_TOKEN в ${ENV_FILE} для входа через Mini App"
echo "  4. Выпустите wildcard-сертификат: certbot certonly --manual --preferred-challenges dns \\"
echo "       -d ${HOSTING_ROOT_DOMAIN} -d *.${HOSTING_ROOT_DOMAIN} (см. README — DNS-01 через Cloudflare)"
echo "  5. Зарегистрируйтесь через панель, затем сделайте себя админом:"
echo "       mysql -uroot -p -e \"UPDATE ${DB_DATABASE}.users SET role='admin' WHERE email='ваш@email'\""
if [[ ${#STATUS_LINES[@]} -gt 0 ]]; then
  echo
  warn "Требует вашего внимания:"
  for line in "${STATUS_LINES[@]}"; do echo "  - $line"; done
fi
