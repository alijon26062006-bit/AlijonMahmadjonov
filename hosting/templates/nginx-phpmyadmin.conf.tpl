# Сгенерировано {{PANEL_NAME}} — общий phpMyAdmin для всех клиентов на db.{{ROOT_DOMAIN}}.
# Клиент входит своей собственной DB-учёткой, root-логин запрещён в config.inc.php.

server {
    listen 80;
    listen [::]:80;
    server_name db.{{ROOT_DOMAIN}};

    root {{PHPMYADMIN_ROOT}};
    index index.php;

    access_log {{LOG_DIR}}/phpmyadmin-access.log;
    error_log  {{LOG_DIR}}/phpmyadmin-error.log warn;

    client_max_body_size 128m;
    limit_conn perip_conn 20;
    limit_req zone=login_req burst=10 nodelay;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location ~ /\. {
        deny all;
    }

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        try_files $uri =404;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_pass unix:/run/php/phpmyadmin.sock;
        fastcgi_read_timeout 60s;
    }
}
