#!/usr/bin/env bash
# ============================================================
# AVERIX — обновление сайта. Запускать после каждого push.
#
#   bash /var/www/averix-repo/averix/deploy/update.sh
# ============================================================
set -euo pipefail

CLONE_DIR="${CLONE_DIR:-/var/www/averix-repo}"

[ -d "$CLONE_DIR/.git" ] || { echo "Не нашёл репозиторий в $CLONE_DIR" >&2; exit 1; }

# .git должна принадлежать root, иначе git ругается на чужого владельца
chown -R root:root "$CLONE_DIR/.git"
git config --global --get-all safe.directory 2>/dev/null | grep -qx "$CLONE_DIR" \
  || git config --global --add safe.directory "$CLONE_DIR"

# Берём ту ветку, что уже развёрнута, — не нужно помнить её название
BRANCH="${BRANCH:-$(git -C "$CLONE_DIR" rev-parse --abbrev-ref HEAD)}"

BEFORE="$(git -C "$CLONE_DIR" rev-parse --short HEAD)"
git -C "$CLONE_DIR" fetch --quiet origin "$BRANCH"
git -C "$CLONE_DIR" reset --hard --quiet "origin/$BRANCH"
AFTER="$(git -C "$CLONE_DIR" rev-parse --short HEAD)"

# Код принадлежит root, www-data только читает
chown -R root:root "$CLONE_DIR/averix"
chmod -R a+rX "$CLONE_DIR/averix"

# Зависимости и миграции — только если что-то изменилось
VENV_DIR="${VENV_DIR:-/var/www/averix-venv}"
DATA_DIR="${DATA_DIR:-/var/www/averix-data}"
if [ -x "$VENV_DIR/bin/pip" ] && [ "$BEFORE" != "$AFTER" ]; then
  if git -C "$CLONE_DIR" diff --name-only "$BEFORE" "$AFTER" | grep -q "requirements.txt"; then
    echo "Обновляю зависимости..."
    "$VENV_DIR/bin/pip" install --quiet -r "$CLONE_DIR/averix/requirements.txt"
  fi
fi
if systemctl list-unit-files averix.service >/dev/null 2>&1; then
  systemctl restart averix
  sleep 1
  systemctl is-active --quiet averix \
    && echo "Приложение перезапущено." \
    || echo "!! Приложение не поднялось: journalctl -u averix -n 40"
fi

if [ "$BEFORE" = "$AFTER" ]; then
  echo "Обновлений нет, версия $AFTER"
else
  echo "Обновлено: $BEFORE → $AFTER"
  git -C "$CLONE_DIR" log --oneline "$BEFORE..$AFTER" | sed 's/^/  /'
fi

# ------------------------------------------------------------
# Конфиг nginx лежит в репозитории, а работает его копия в /etc.
# Если в этом обновлении шаблон изменился, копию нужно пересобрать:
# иначе сайт останется на старых правилах и, например, перестанет
# открываться главная.
# ------------------------------------------------------------
NGINX_SITE="/etc/nginx/sites-available/averix"
TEMPLATE="$CLONE_DIR/averix/deploy/nginx.conf"

nginx_needs_update() {
  [ -f "$NGINX_SITE" ] || return 1
  # правила, которых нет в старой версии, — признак устаревшей копии
  grep -q "location @app" "$NGINX_SITE" || return 0
  [ "$BEFORE" != "$AFTER" ] \
    && git -C "$CLONE_DIR" diff --name-only "$BEFORE" "$AFTER" \
       | grep -q "deploy/nginx.conf"
}

if [ -f "$TEMPLATE" ] && nginx_needs_update; then
  DOMAIN="$(awk '/server_name/ {print $2; exit}' "$NGINX_SITE" | tr -d ';')"
  SITE_DIR="$CLONE_DIR/averix"
  BACKUP="/etc/nginx/sites-available/averix.before-update"

  if [ -z "$DOMAIN" ]; then
    echo "!! Не смог определить домен из $NGINX_SITE — конфиг не трогаю."
    echo "   Запустите deploy/setup.sh ваш-домен вручную."
  else
    echo "Обновляю конфиг nginx для $DOMAIN..."
    cp -f "$NGINX_SITE" "$BACKUP"
    sed -e "s|__DOMAIN__|$DOMAIN|g" -e "s|__ROOT__|$SITE_DIR|g" \
        -e "s|__DATA_DIR__|$DATA_DIR|g" "$TEMPLATE" > "$NGINX_SITE"

    # Строки с сертификатом добавляет certbot прямо в этот файл,
    # и пересборка их стирает. Возвращаем их тем же certbot —
    # новый сертификат при этом не выпускается.
    if [ -d "/etc/letsencrypt/live/$DOMAIN" ] && command -v certbot >/dev/null; then
      certbot install --nginx --cert-name "$DOMAIN" --redirect \
        --non-interactive >/dev/null 2>&1 \
        || echo "   !! certbot не вернул HTTPS в конфиг — проверьте вручную"
    fi

    if nginx -t >/dev/null 2>&1; then
      systemctl reload nginx
      echo "   конфиг обновлён, прежний сохранён в $BACKUP"
    else
      cp -f "$BACKUP" "$NGINX_SITE"
      systemctl reload nginx || true
      echo "   !! Новый конфиг не прошёл проверку — вернул прежний."
      nginx -t || true
    fi
  fi
else
  nginx -t >/dev/null 2>&1 && systemctl reload nginx
fi

echo "Готово."
