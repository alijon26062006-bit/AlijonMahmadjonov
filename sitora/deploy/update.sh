#!/usr/bin/env bash
# Обновить Sitora (Donatix не трогает):  sudo bash /home/sitora/app/sitora/deploy/update.sh
set -euo pipefail
APP_DIR=/home/sitora/app
BRANCH="${SITORA_BRANCH:-claude/website-api-sales-96wxcs}"
# код — через копию Donatix (там доступ к GitHub уже есть); саму Donatix это не меняет
sudo -u donatix git -C /home/donatix/app fetch -q origin "$BRANCH"
sudo -u donatix git -C /home/donatix/app archive FETCH_HEAD sitora | tar -x -C "$APP_DIR"
chown -R sitora:sitora "$APP_DIR"
sudo -u sitora "$APP_DIR/sitora/.venv/bin/pip" install -q -r "$APP_DIR/sitora/requirements.txt"
systemctl restart sitora
bash "$APP_DIR/sitora/deploy/nginx-path.sh" || true   # строка в nginx Donatix на месте (вернёт, если пропала)
sleep 2
systemctl is-active --quiet sitora && echo "✅ Sitora обновлена: $(sudo -u donatix git -C /home/donatix/app log -1 --format='%h %s' FETCH_HEAD)" \
  || { journalctl -u sitora -n 30 --no-pager; exit 1; }
