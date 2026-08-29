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

# статика отдаётся напрямую, перезагрузка нужна только если менялся конфиг
nginx -t >/dev/null 2>&1 && systemctl reload nginx
echo "Готово."
