#!/usr/bin/env bash
# Подключить Sitora по скрытому адресу https://<домен Donatix>/<секрет>/ — без нового домена, DNS и сертификата.
# В настройки nginx Donatix добавляется ОДНА строка include (код и база Donatix не меняются).
# Перед правкой — копия; если nginx не принимает настройки — копия возвращается автоматически.
#   sudo bash nginx-path.sh            — проверить и при необходимости вернуть строку (безопасно запускать снова)
set -euo pipefail
ENV_FILE=/home/sitora/app/sitora/.env
SITE=/etc/nginx/sites-available/donatix
SNIP=/etc/nginx/snippets/sitora.conf
PORT=8020
[ "$(id -u)" = 0 ] || { echo "Запустите под root."; exit 1; }
SECRET=$(grep -oP '^SITORA_BASE_URL=https?://[^/]+/\K[^/]+' "$ENV_FILE")
[ -n "$SECRET" ] || { echo "В $ENV_FILE нет скрытого пути в SITORA_BASE_URL"; exit 1; }
mkdir -p /etc/nginx/snippets
cat > "$SNIP" <<NGINX
# Sitora — скрытый адрес. Не удаляйте: без этого бот не откроет мини-приложение.
location ^~ /$SECRET/ {
    proxy_pass http://127.0.0.1:$PORT/;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_read_timeout 60s;
    client_max_body_size 12m;
}
# VPS: живые графики (WebSocket) — агент на сервере клиента и мини-приложение
location = /$SECRET/agent {
    proxy_pass http://127.0.0.1:$PORT/agent;
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host \$host;
    proxy_set_header Authorization \$http_authorization;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
location = /$SECRET/ws/live {
    proxy_pass http://127.0.0.1:$PORT/ws/live;
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host \$host;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
NGINX
[ -f "$SITE" ] || { echo "Не найден $SITE — пришлите вывод: ls /etc/nginx/sites-enabled"; exit 1; }
if grep -q "include $SNIP;" "$SITE"; then
  nginx -t -q && systemctl reload nginx && echo "✓ Скрытый адрес подключён (/$SECRET/)"; exit 0
fi
BK="$SITE.bak-sitora-$(date +%F-%H%M%S)"; cp -a "$SITE" "$BK"
# строка include — сразу после каждой строки server_name (во всех блоках server: 80 и 443)
sed -i -E "s#^(\s*server_name\s+[^;]*;)#\1\n    include $SNIP;#" "$SITE"
if nginx -t -q 2>/dev/null; then
  systemctl reload nginx && echo "✓ Скрытый адрес подключён (/$SECRET/). Копия старых настроек: $BK"
else
  cp -a "$BK" "$SITE"; nginx -t -q && systemctl reload nginx
  echo "✖ nginx не принял настройки — вернул как было. Donatix работает. Пришлите: nginx -t"; exit 1
fi
