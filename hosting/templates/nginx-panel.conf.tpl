# Сгенерировано {{PANEL_NAME}} — vhost самой панели управления.
# Слушает {{PANEL_DOMAIN}} (обычно panel.{{ROOT_DOMAIN}}). SSL добавляется отдельно
# после первого certbot (см. install.sh) — этот файл HTTP-only, редиректит на HTTPS,
# если сертификат уже есть (переменная {{HTTPS_REDIRECT}} подставляется install.sh).

server {
    listen 80;
    listen [::]:80;
    server_name {{PANEL_DOMAIN}};

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

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    limit_conn perip_conn 30;
    limit_req zone=general_req burst=40 nodelay;

    location = /login {
        limit_req zone=login_req burst=10 nodelay;
        try_files $uri /index.php?$query_string;
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
