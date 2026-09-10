# Сгенерировано {{PANEL_NAME}} — HTTPS-версия, добавляется после успешного выпуска сертификата.
# Клиент {{SYSTEM_USER}} · сайт {{DOMAIN}} · PHP {{PHP_VERSION}}

server {
    listen 80;
    listen [::]:80;
    server_name {{DOMAIN}};
    location ^~ /.well-known/acme-challenge/ {
        root {{ACME_WEBROOT}};
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {{DOMAIN}};

    ssl_certificate     {{SSL_CERT}};
    ssl_certificate_key {{SSL_KEY}};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    root {{DOC_ROOT}};
    index index.php index.html index.htm;

    access_log {{LOG_DIR}}/access.log;
    error_log  {{LOG_DIR}}/error.log warn;

    client_max_body_size {{UPLOAD_MAX_MB}}m;
    client_header_timeout 10s;
    client_body_timeout 15s;
    send_timeout 30s;
    keepalive_timeout 15s;
    keepalive_requests 500;
    reset_timedout_connection on;
    charset utf-8;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    limit_conn perip_conn 30;
    limit_req zone=general_req burst=40 nodelay;

    location ~ /\.(?!well-known) {
        deny all;
    }
    location ~* \.(env|ini|log|sql|bak|old|backup|git)$ {
        deny all;
    }
    location ~* ^/(?:composer\.(json|lock)|package(-lock)?\.json)$ {
        deny all;
    }

    location = /wp-login.php {
        limit_req zone=login_req burst=10 nodelay;
        try_files $uri =404;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_param HTTPS on;
        fastcgi_pass {{FPM_UPSTREAM}};
    }
    location = /xmlrpc.php {
        {{XMLRPC_RULE}}
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
        fastcgi_param HTTPS on;
        fastcgi_pass {{FPM_UPSTREAM}};
        fastcgi_index index.php;
        fastcgi_connect_timeout 5s;
        fastcgi_send_timeout 30s;
        fastcgi_read_timeout 40s;
        fastcgi_buffers 16 16k;
        fastcgi_buffer_size 32k;
    }

    location ~* \.(?:css|js|jpg|jpeg|png|gif|webp|svg|ico|woff2?|ttf)$ {
        expires 7d;
        access_log off;
        try_files $uri =404;
    }
}
