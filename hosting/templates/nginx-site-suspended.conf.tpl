# Сгенерировано {{PANEL_NAME}} — сайт {{DOMAIN}} приостановлен (истёк тариф/нарушение).
# Заменяет обычный vhost, пока клиент не оплатит или блокировка не будет снята.

server {
    listen 80;
    listen [::]:80;
    server_name {{DOMAIN}};

    location / {
        default_type text/plain;
        add_header Content-Type "text/plain; charset=utf-8" always;
        return 402 "Сайт временно приостановлен.\nОбратитесь в панель управления, чтобы возобновить работу.";
    }
}
