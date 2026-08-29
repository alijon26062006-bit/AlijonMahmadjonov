#!/usr/bin/env bash
# ============================================================
# AVERIX — обновление сайта. Запускать после каждого push.
#
#   bash /var/www/averix-repo/averix/deploy/update.sh
# ============================================================
set -euo pipefail

CLONE_DIR="${CLONE_DIR:-/var/www/averix-repo}"

[ -d "$CLONE_DIR/.git" ] || { echo "Не нашёл репозиторий в $CLONE_DIR" >&2; exit 1; }

# Берём ту ветку, что уже развёрнута, — не нужно помнить её название
BRANCH="${BRANCH:-$(git -C "$CLONE_DIR" rev-parse --abbrev-ref HEAD)}"

BEFORE="$(git -C "$CLONE_DIR" rev-parse --short HEAD)"
git -C "$CLONE_DIR" fetch --quiet origin "$BRANCH"
git -C "$CLONE_DIR" reset --hard --quiet "origin/$BRANCH"
AFTER="$(git -C "$CLONE_DIR" rev-parse --short HEAD)"

chown -R www-data:www-data "$CLONE_DIR"
chmod -R a+rX "$CLONE_DIR"

if [ "$BEFORE" = "$AFTER" ]; then
  echo "Обновлений нет, версия $AFTER"
else
  echo "Обновлено: $BEFORE → $AFTER"
  git -C "$CLONE_DIR" log --oneline "$BEFORE..$AFTER" | sed 's/^/  /'
fi

# статика отдаётся напрямую, перезагрузка нужна только если менялся конфиг
nginx -t >/dev/null 2>&1 && systemctl reload nginx
echo "Готово."
