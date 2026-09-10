# Сгенерировано {{PANEL_NAME}} — vhost панели с HTTPS.
# Этот файл ставится вместо HTTP-версии, когда сертификат для {{CERT_DOMAIN}}
# уже выпущен (см. scripts/apply-panel-vhost.sh). Telegram работает только по
# HTTPS: и Mini App, и кнопка входа на сайте — по HTTP их просто не принимают.

server {
    listen 80;
    listen [::]:80;
    server_name {{PANEL_DOMAIN}};

    # Проверка Let's Encrypt по HTTP-01: должна оставаться доступной по HTTP,
    # иначе продление сертификата упрётся в редирект на HTTPS.
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
        default_type "text/plain";
        allow all;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name {{PANEL_DOMAIN}};

    ssl_certificate     /etc/letsencrypt/live/{{CERT_DOMAIN}}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{{CERT_DOMAIN}}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_stapling on;
    ssl_stapling_verify on;

    root {{PANEL_ROOT}};
    index index.php;

    access_log {{LOG_DIR}}/panel-access.log;
    error_log  {{LOG_DIR}}/panel-error.log warn;

    client_max_body_size {{UPLOAD_MAX_MB}}m;
    client_header_timeout 10s;
    client_body_timeout 15s;
    send_timeout 30s;
    keepalive_timeout 15s;
    reset_timedout_connection on;
    charset utf-8;

    # HSTS здесь НЕ ставим: его уже отдаёт сама панель (public/index.php), причём
    # с большим max-age и includeSubDomains. Два заголовка Strict-Transport-Security
    # в одном ответе — не ошибка, но браузер берёт первый, и значение из nginx
    # молча ослабляло бы политику.
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    limit_conn perip_conn 30;
    limit_req zone=general_req burst=40 nodelay;

    location = /login {
        limit_req zone=login_req burst=10 nodelay;
        try_files $uri /index.php?$query_string;
    }

    # Проверка Let's Encrypt по HTTP-01. Должна стоять ВЫШЕ правила "deny /\." —
    # иначе запрос к /.well-known/acme-challenge/... попадает под запрет точечных
    # путей, certbot получает 403, и сертификат не выпускается вообще.
    # Префикс ^~ выигрывает у регулярных location, поэтому порядок в файле не
    # единственная защита.
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
        default_type "text/plain";
        allow all;
    }

    location ~ /\. {
        deny all;
    }
    location ~* \.(env|ini|sql|log)$ {
        deny all;
    }

    location / {
        try_files $uri /index.php?$query_string;
    }

    location ~ ^/index\.php$ {
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root/index.php;
        fastcgi_pass unix:/run/php/hosting-panel.sock;
        fastcgi_read_timeout 60s;
    }

    location ~* \.(?:css|js|jpg|jpeg|png|gif|webp|svg|ico|woff2?)$ {
        expires 7d;
        access_log off;
        try_files $uri =404;
    }
}
