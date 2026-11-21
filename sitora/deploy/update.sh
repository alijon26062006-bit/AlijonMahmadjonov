#!/usr/bin/env bash
# Обновить Sitora (Donatix не трогает):  sudo bash /home/sitora/app/sitora/deploy/update.sh
set -euo pipefail
APP_DIR=/home/sitora/app
BRANCH="${SITORA_BRANCH:-claude/website-api-sales-96wxcs}"
sudo -u sitora git -C "$APP_DIR" fetch -q origin "$BRANCH"
sudo -u sitora git -C "$APP_DIR" reset -q --hard FETCH_HEAD
sudo -u sitora "$APP_DIR/sitora/.venv/bin/pip" install -q -r "$APP_DIR/sitora/requirements.txt"
systemctl restart sitora
sleep 2
systemctl is-active --quiet sitora && echo "✅ Sitora обновлена: $(git -C $APP_DIR log -1 --format='%h %s')" \
  || { journalctl -u sitora -n 30 --no-pager; exit 1; }
