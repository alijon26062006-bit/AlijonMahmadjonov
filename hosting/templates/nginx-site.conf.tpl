# Сгенерировано панелью {{PANEL_NAME}} — правки будут перезаписаны.
# Сайт: {{DOMAIN}} (клиент {{SYSTEM_USER}}, PHP {{PHP_VERSION}})

server {
    listen 80;
    listen [::]:80;
    server_name {{DOMAIN}} www.{{DOMAIN}};

    root {{DOC_ROOT}};
    index index.php index.html index.htm;

    access_log {{LOG_DIR}}/access.log;
    error_log  {{LOG_DIR}}/error.log;

    client_max_body_size {{UPLOAD_MAX_MB}}m;
    charset utf-8;

    # Служебные файлы наружу не отдаём
    location ~ /\.(?!well-known) {
        deny all;
    }
    location ~* ^/(?:composer\.(json|lock)|package(-lock)?\.json|\.env.*)$ {
        deny all;
    }

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        try_files $uri =404;
        include fastcgi_params;
        fastcgi_split_path_info ^(.+\.php)(/.+)$;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_param PATH_INFO $fastcgi_path_info;
        fastcgi_param HTTPS $https if_not_empty;
        fastcgi_pass {{FPM_UPSTREAM}};
        fastcgi_index index.php;
        fastcgi_read_timeout 120s;
        fastcgi_buffers 16 16k;
        fastcgi_buffer_size 32k;
    }

    location ~* \.(?:css|js|jpg|jpeg|png|gif|webp|svg|ico|woff2?|ttf)$ {
        expires 7d;
        access_log off;
        try_files $uri =404;
    }
}
