#!/usr/bin/env bash
# ============================================================
# AVERIX — первичная установка на VPS. Запускается один раз.
#
#   bash setup.sh averix.tj
#
# Что делает: ставит nginx, git и certbot, клонирует репозиторий,
# настраивает сайт, включает файрвол и выпускает сертификат.
# Скрипт можно запускать повторно — он не ломает уже сделанное.
# ============================================================
set -euo pipefail

DOMAIN="${1:-}"
REPO="${REPO:-https://github.com/alijon26062006-bit/AlijonMahmadjonov.git}"
BRANCH="${BRANCH:-main}"
CLONE_DIR="/var/www/averix-repo"
SITE_DIR="$CLONE_DIR/averix"      # сайт лежит в подпапке репозитория

die() { echo "Ошибка: $*" >&2; exit 1; }
say() { echo; echo "==> $*"; }

[ -n "$DOMAIN" ] || die "укажите домен:  bash setup.sh averix.tj"
[ "$(id -u)" -eq 0 ] || die "запустите от root:  sudo bash setup.sh $DOMAIN"
command -v apt-get >/dev/null || die "скрипт рассчитан на Debian или Ubuntu"

say "Проверяю, что домен указывает на этот сервер"
SERVER_IP="$(curl -fsS --max-time 10 https://api.ipify.org || echo '')"
DOMAIN_IP="$(getent hosts "$DOMAIN" | awk '{print $1; exit}' || echo '')"
if [ -n "$SERVER_IP" ] && [ -n "$DOMAIN_IP" ] && [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
  echo "    Внимание: $DOMAIN сейчас указывает на $DOMAIN_IP,"
  echo "    а этот сервер — $SERVER_IP."
  echo "    Сертификат не выпустится, пока A-запись не обновится."
  read -r -p "    Продолжить всё равно? [y/N] " a
  [ "$a" = "y" ] || exit 1
fi

say "Ставлю пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx git curl certbot python3-certbot-nginx ufw

say "Забираю сайт из репозитория"
if [ -d "$CLONE_DIR/.git" ]; then
  git -C "$CLONE_DIR" fetch --quiet origin "$BRANCH"
  git -C "$CLONE_DIR" checkout --quiet "$BRANCH"
  git -C "$CLONE_DIR" reset --hard --quiet "origin/$BRANCH"
else
  mkdir -p "$(dirname "$CLONE_DIR")"
  git clone --quiet --branch "$BRANCH" "$REPO" "$CLONE_DIR"
fi
[ -f "$SITE_DIR/index.html" ] || die "не нашёл $SITE_DIR/index.html — проверьте ветку BRANCH=$BRANCH"

# nginx читает файлы от имени www-data
chown -R www-data:www-data "$CLONE_DIR"
chmod -R a+rX "$CLONE_DIR"

say "Настраиваю сайт в nginx"
sed -e "s|__DOMAIN__|$DOMAIN|g" -e "s|__ROOT__|$SITE_DIR|g" \
    "$SITE_DIR/deploy/nginx.conf" > /etc/nginx/sites-available/averix
ln -sf /etc/nginx/sites-available/averix /etc/nginx/sites-enabled/averix
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

say "Открываю порты"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null
echo "    22, 80 и 443 открыты, остальное закрыто"

say "Выпускаю сертификат"
if certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
     --non-interactive --agree-tos --redirect \
     -m "alijon26.06.2006@gmail.com"; then
  echo "    HTTPS включён, продление настроено автоматически"
else
  echo "    Сертификат выпустить не удалось — сайт работает по http://"
  echo "    Проверьте A-запись домена и повторите:"
  echo "      certbot --nginx -d $DOMAIN -d www.$DOMAIN"
fi

say "Готово"
echo "    Сайт:        https://$DOMAIN"
echo "    Файлы:       $SITE_DIR"
echo "    Обновление:  bash $SITE_DIR/deploy/update.sh"
