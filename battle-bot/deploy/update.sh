#!/usr/bin/env bash
# Обновление бота одной командой: подтянуть код, пересобрать, перезапустить.
# Ставится как /usr/local/bin/battle-update, путь к репозиторию подставляется
# при установке.
set -euo pipefail

REPO_DIR="__REPO_DIR__"
BRANCH="__BRANCH__"

if [ "$(id -u)" -ne 0 ]; then
    echo "Запустите от root: sudo battle-update" >&2
    exit 1
fi

echo "==> Забираю обновления ($BRANCH)"
cd "$REPO_DIR"
git fetch --quiet origin "$BRANCH"

BEFORE="$(git rev-parse HEAD)"
git checkout --quiet "$BRANCH"
git pull --quiet origin "$BRANCH"
AFTER="$(git rev-parse HEAD)"

if [ "$BEFORE" = "$AFTER" ]; then
    echo "Уже последняя версия ($(git log -1 --pretty=%s))"
else
    git --no-pager log --oneline "$BEFORE..$AFTER" | sed 's/^/   /'
fi

bash "$REPO_DIR/battle-bot/deploy/install.sh"
