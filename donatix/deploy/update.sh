#!/usr/bin/env bash
# Быстрое обновление сайта одной командой: свежий код → (если поменялись библиотеки — установка) → перезапуск →
# ждём, пока сайт ответит, и сразу пишем «готово». Запуск: sudo bash /home/donatix/app/donatix/deploy/update.sh
set -euo pipefail
APP_DIR=/home/donatix/app
START=$(date +%s)
step() { echo "• $1 ($(( $(date +%s) - START )) с)"; }

# Остановка не дольше 10 с: по умолчанию systemd ждёт 90 с, пока старый процесс (и боты партнёров) выключится
DROP=/etc/systemd/system/donatix.service.d/fast-stop.conf
if [ ! -f "$DROP" ]; then
  mkdir -p "$(dirname "$DROP")"
  printf '[Service]\nTimeoutStopSec=10\nKillMode=mixed\n' > "$DROP"
  systemctl daemon-reload
fi

OLD=$(sudo -u donatix git -C "$APP_DIR" rev-parse HEAD)
sudo -u donatix git -C "$APP_DIR" pull -q
NEW=$(sudo -u donatix git -C "$APP_DIR" rev-parse HEAD)
step "код скачан"
if [ "$OLD" != "$NEW" ] && sudo -u donatix git -C "$APP_DIR" diff --name-only "$OLD" "$NEW" | grep -q "requirements.txt"; then
  step "новые библиотеки — устанавливаю"
  sudo -u donatix "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/donatix/requirements.txt"
fi
systemctl restart donatix
step "перезапущен"
for _ in $(seq 1 60); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/robots.txt | grep -q 200; then
    echo "✅ Готово за $(( $(date +%s) - START )) с — версия $(sudo -u donatix git -C "$APP_DIR" log --oneline -1)"
    exit 0
  fi
  sleep 0.5
done
echo "⚠ Сайт не ответил за 30 с. Журнал: journalctl -u donatix -n 40"
exit 1
