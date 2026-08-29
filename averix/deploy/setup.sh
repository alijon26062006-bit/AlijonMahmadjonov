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
# Ветку можно задать явно: BRANCH=... bash setup.sh averix.dev
# Если не задана — берём main, а когда сайта там ещё нет, ветку разработки.
BRANCH="${BRANCH:-}"
FALLBACK_BRANCH="claude/ui-ux-pro-max-landing-n9y2jh"
CLONE_DIR="/var/www/averix-repo"
SITE_DIR="$CLONE_DIR/averix"      # сайт лежит в подпапке репозитория
# База и загрузки — вне репозитория. Внутри клона они попадали бы под
# git clean, засоряли git status и рисковали уехать в коммит.
DATA_DIR="/var/www/averix-data"
VENV_DIR="/var/www/averix-venv"

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
apt-get install -y -qq nginx git curl certbot python3-certbot-nginx ufw \
  python3 python3-venv python3-pip

say "Забираю сайт из репозитория"
# git отказывается работать с репозиторием, который принадлежит другому
# пользователю. Служебная папка .git остаётся у root — веб-серверу она
# не нужна, ему отдаём только сам сайт.
if [ -d "$CLONE_DIR/.git" ]; then
  chown -R root:root "$CLONE_DIR/.git"
fi
git config --global --get-all safe.directory 2>/dev/null | grep -qx "$CLONE_DIR" \
  || git config --global --add safe.directory "$CLONE_DIR"

if [ ! -d "$CLONE_DIR/.git" ]; then
  mkdir -p "$(dirname "$CLONE_DIR")"
  git clone --quiet "$REPO" "$CLONE_DIR"
fi
git -C "$CLONE_DIR" fetch --quiet --all --prune

pick_branch() {
  local b="$1"
  git -C "$CLONE_DIR" rev-parse --verify --quiet "origin/$b" >/dev/null || return 1
  git -C "$CLONE_DIR" ls-tree --name-only "origin/$b" averix/ 2>/dev/null | grep -q . || return 1
}

if [ -z "$BRANCH" ]; then
  if pick_branch main; then BRANCH="main"
  elif pick_branch "$FALLBACK_BRANCH"; then BRANCH="$FALLBACK_BRANCH"
  else die "не нашёл папку averix/ ни в main, ни в $FALLBACK_BRANCH"; fi
  echo "    ветка: $BRANCH"
fi

git -C "$CLONE_DIR" checkout --quiet -B "$BRANCH" "origin/$BRANCH"
git -C "$CLONE_DIR" reset --hard --quiet "origin/$BRANCH"
[ -f "$SITE_DIR/app/main.py" ] || die "не нашёл $SITE_DIR/app/main.py в ветке $BRANCH"

# Код принадлежит root, www-data только читает: приложение работает
# от www-data и не должно иметь права переписывать собственные исходники.
chown -R root:root "$SITE_DIR"
chmod -R a+rX "$SITE_DIR"
chmod 755 "$CLONE_DIR"

say "Готовлю папку данных"
mkdir -p "$DATA_DIR/uploads"
chown -R www-data:www-data "$DATA_DIR"
chmod 750 "$DATA_DIR"
echo "    $DATA_DIR — единственное место, куда приложение пишет"

say "Ставлю приложение"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SITE_DIR/requirements.txt"
chown -R root:root "$VENV_DIR"
chmod -R a+rX "$VENV_DIR"

sed -e "s|__SITE_DIR__|$SITE_DIR|g" \
    -e "s|__DATA_DIR__|$DATA_DIR|g" \
    -e "s|__VENV__|$VENV_DIR|g" \
    -e "s|__SITE_URL__|https://$DOMAIN|g" \
    "$SITE_DIR/deploy/averix.service" > /etc/systemd/system/averix.service
systemctl daemon-reload
systemctl enable --quiet averix
systemctl restart averix

sleep 2
if systemctl is-active --quiet averix; then
  echo "    приложение запущено на 127.0.0.1:8001"
else
  echo "    !! приложение не поднялось. Журнал: journalctl -u averix -n 40"
fi

say "Настраиваю сайт в nginx"
NGINX_SITE=/etc/nginx/sites-available/averix
NGINX_BAK=/etc/nginx/sites-available/averix.bak

# Шаблон не содержит блока HTTPS — его дописывает certbot. Поэтому
# повторный запуск скрипта временно снимает шифрование, и если certbot
# затем упадёт, сайт останется на голом http. Сохраняем рабочий конфиг,
# чтобы было куда вернуться.
HAD_SSL=0
if [ -f "$NGINX_SITE" ] && grep -q "ssl_certificate" "$NGINX_SITE"; then
  cp -f "$NGINX_SITE" "$NGINX_BAK"
  HAD_SSL=1
  echo "    прежний конфиг с HTTPS сохранён в $NGINX_BAK"
fi

sed -e "s|__DOMAIN__|$DOMAIN|g" -e "s|__ROOT__|$SITE_DIR|g" \
    -e "s|__DATA_DIR__|$DATA_DIR|g" \
    "$SITE_DIR/deploy/nginx.conf" > "$NGINX_SITE"
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
# www берём в сертификат только если он резолвится: certbot падает
# целиком, если хотя бы одно из имён не проходит проверку.
CERT_ARGS=(-d "$DOMAIN")
if getent hosts "www.$DOMAIN" >/dev/null 2>&1; then
  CERT_ARGS+=(-d "www.$DOMAIN")
else
  echo "    www.$DOMAIN не резолвится — сертификат только на $DOMAIN"
fi

# keep-until-expiring: если сертификат ещё жив, certbot просто
# вставит его в конфиг, а не выпустит новый и не потратит лимит
if certbot --nginx "${CERT_ARGS[@]}" \
     --non-interactive --agree-tos --redirect --keep-until-expiring \
     -m "alijon26.06.2006@gmail.com"; then
  echo "    HTTPS включён, продление настроено автоматически"
else
  echo
  echo "    !! Сертификат выпустить не удалось."
  case "$DOMAIN" in
    *.dev)
      echo "    Зона .dev целиком в списке HSTS preload: браузеры не дают"
      echo "    открыть её по http вообще. Без сертификата сайт не откроется."
      ;;
    *)
      echo "    Пока сайт доступен только по http://$DOMAIN"
      ;;
  esac
  echo "    Обычно причина — A-запись ещё не разошлась. Проверьте и повторите:"
  echo "      getent hosts $DOMAIN"
  echo "      certbot --nginx ${CERT_ARGS[*]}"

  if [ "$HAD_SSL" = "1" ]; then
    cp -f "$NGINX_BAK" "$NGINX_SITE"
    nginx -t >/dev/null 2>&1 && systemctl reload nginx
    echo
    echo "    Прежний конфиг с HTTPS возвращён — сайт продолжает работать"
    echo "    на старом домене. Без этого он остался бы на голом http."
  fi
  exit 1
fi

say "Готово"
echo "    Сайт:        https://$DOMAIN"
echo "    Файлы:       $SITE_DIR"
echo "    Обновление:  bash $SITE_DIR/deploy/update.sh"
echo
echo "    Админка ещё без пользователя. Создайте его:"
echo "      cd $SITE_DIR && sudo -u www-data AVERIX_DATA_DIR=$DATA_DIR \\"
echo "        $VENV_DIR/bin/python -m app.cli create-admin <логин>"
echo "    Затем откройте https://$DOMAIN/admin"
