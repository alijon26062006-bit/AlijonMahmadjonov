#!/usr/bin/env bash
# One-shot VPS deploy for the EasySIM Django app.
#
# Usage (as root on a fresh Ubuntu VPS):
#   sudo bash deploy.sh your-domain.tj
#
# What it does: installs system packages, fetches the project (git clone if
# not already present), sets up a venv, creates .env with a random secret key
# (you still must fill in Zadarma/Airalo keys yourself afterwards), runs
# migrations, prompts for an admin superuser, and wires up gunicorn (systemd)
# + nginx as a reverse proxy.
#
# Safe to re-run: it skips steps that were already done (existing .env,
# existing superuser, existing venv gets its deps re-installed/updated).

set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/esim-store-django}"
REPO_URL="${REPO_URL:-https://github.com/alijon26062006-bit/AlijonMahmadjonov.git}"
REPO_BRANCH="${REPO_BRANCH:-claude/esim-purchase-website-dcpuy3}"
SERVICE_NAME="${SERVICE_NAME:-esim-store}"
RUN_USER="${RUN_USER:-www-data}"
DOMAIN="${1:-}"

if [[ $EUID -ne 0 ]]; then
    echo "Запускайте под root: sudo bash deploy.sh your-domain.tj" >&2
    exit 1
fi

if [[ -z "$DOMAIN" ]]; then
    echo "Использование: sudo bash deploy.sh your-domain.tj" >&2
    exit 1
fi

echo "==> [1/8] Системные пакеты (python3, venv, nginx, git)"
apt-get update -y
apt-get install -y python3-venv python3-pip nginx git

echo "==> [2/8] Код проекта в $APP_DIR"
if [[ -f "$APP_DIR/manage.py" ]]; then
    echo "    Проект уже развёрнут — обновляю (git pull)"
    git -C "$APP_DIR" pull --ff-only
elif [[ -f "./manage.py" && -f "./deploy/deploy.sh" ]]; then
    echo "    Скрипт запущен внутри уже загруженного проекта — использую текущую папку"
    APP_DIR="$(pwd)"
else
    echo "    Клонирую $REPO_URL (ветка $REPO_BRANCH)"
    rm -rf /tmp/esim-repo-clone
    git clone --branch "$REPO_BRANCH" --single-branch --depth 1 "$REPO_URL" /tmp/esim-repo-clone
    mkdir -p "$APP_DIR"
    cp -r /tmp/esim-repo-clone/esim-store-django/. "$APP_DIR"/
    rm -rf /tmp/esim-repo-clone
fi
cd "$APP_DIR"

echo "==> [3/8] Виртуальное окружение и зависимости"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
deactivate

echo "==> [4/8] .env"
if [[ ! -f .env ]]; then
    cp .env.example .env
    SECRET="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(50))')"
    sed -i "s#^DJANGO_SECRET_KEY=.*#DJANGO_SECRET_KEY=${SECRET}#" .env
    sed -i "s#^DJANGO_DEBUG=.*#DJANGO_DEBUG=false#" .env
    sed -i "s#^DJANGO_ALLOWED_HOSTS=.*#DJANGO_ALLOWED_HOSTS=${DOMAIN}#" .env
    echo "    Создан .env со случайным SECRET_KEY и DEBUG=false."
    echo "    !!! Откройте $APP_DIR/.env и впишите ZADARMA_*/AIRALO_* ключи, реквизиты оплаты и т.д."
else
    echo "    .env уже существует — не трогаю"
fi

echo "==> [5/8] Миграции и статика"
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput

echo "==> [6/8] Администратор"
HAS_SUPERUSER="$(.venv/bin/python manage.py shell -c "
from django.contrib.auth import get_user_model
print(get_user_model().objects.filter(is_superuser=True).exists())
" 2>/dev/null | tail -1)"
if [[ "$HAS_SUPERUSER" != "True" ]]; then
    echo "    Суперпользователь ещё не создан — введите данные для входа в /admin/:"
    .venv/bin/python manage.py createsuperuser
else
    echo "    Суперпользователь уже есть — пропускаю"
fi

echo "==> [7/8] systemd-сервис ($SERVICE_NAME)"
sed \
    -e "s#/var/www/esim-store-django#${APP_DIR}#g" \
    -e "s#^User=www-data#User=${RUN_USER}#" \
    -e "s#^Group=www-data#Group=${RUN_USER}#" \
    "$APP_DIR/deploy/gunicorn.service" > "/etc/systemd/system/${SERVICE_NAME}.service"

chown -R "${RUN_USER}:${RUN_USER}" "$APP_DIR"
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "==> [8/8] nginx"
sed \
    -e "s#your-domain\.tj#${DOMAIN}#g" \
    -e "s#/var/www/esim-store-django#${APP_DIR}#g" \
    "$APP_DIR/deploy/nginx.conf.example" > "/etc/nginx/sites-available/${SERVICE_NAME}"
ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
nginx -t
systemctl reload nginx

cat <<EOF

✅ Готово. Сайт должен открыться на http://${DOMAIN}
   Админка: http://${DOMAIN}/admin/

Дальше вручную:
  1) Заполните реальные ключи в ${APP_DIR}/.env (Zadarma, Airalo, реквизиты оплаты),
     затем: systemctl restart ${SERVICE_NAME}
  2) HTTPS-сертификат:
     apt install -y certbot python3-certbot-nginx
     certbot --nginx -d ${DOMAIN}

Полезные команды:
  systemctl status ${SERVICE_NAME}     — статус приложения
  journalctl -u ${SERVICE_NAME} -f     — логи приложения
  nginx -t && systemctl reload nginx   — после правки конфига nginx
EOF
