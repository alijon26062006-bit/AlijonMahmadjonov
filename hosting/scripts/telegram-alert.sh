#!/usr/bin/env bash
# Отправляет одно сообщение админу в Telegram. Используется monitor.sh и другими
# скриптами для алертов. Тихо ничего не делает, если TELEGRAM_BOT_TOKEN или
# TELEGRAM_ADMIN_CHAT_ID не заданы — не ломает остальной скрипт из-за отсутствия конфигурации.
#
# Использование: telegram-alert.sh "текст сообщения"

set -euo pipefail

TEXT="${1:-}"
if [[ -z "$TEXT" ]]; then
  echo "Использование: telegram-alert.sh <текст>" >&2
  exit 1
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_ADMIN_CHAT_ID:-}" ]]; then
  echo "[telegram-alert] не настроено (TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_CHAT_ID) — сообщение только в лог:" >&2
  echo "$TEXT" >&2
  exit 0
fi

curl -s -m 10 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_ADMIN_CHAT_ID}" \
  --data-urlencode "text=${TEXT}" \
  --data-urlencode "parse_mode=" \
  -o /dev/null || echo "[telegram-alert] не удалось отправить сообщение" >&2
