#!/usr/bin/env bash
# Проверка вживую: настоящий ИИ читает чек → на какую нашу карту пришли деньги → какому кассиру уйдёт чек.
# Ничего не зачисляет и не записывает.
#
#   sudo bash /home/donatix/app/donatix/deploy/receipt-check.sh /путь/к/чеку.jpg
#
# То же самое проще — в админ-боте: команда /chek и фото чека.
set -euo pipefail
APP_DIR=/home/donatix/app
[ -n "${1:-}" ] && [ -f "$1" ] || { echo "Укажите фото чека: sudo bash $0 /root/chek.jpg"; exit 1; }
TMP=$(mktemp /tmp/chek.XXXXXX); cp "$1" "$TMP"; chmod 644 "$TMP"
cd "$APP_DIR" && sudo -u donatix .venv/bin/python -m donatix receipt-check "$TMP"; rm -f "$TMP"
