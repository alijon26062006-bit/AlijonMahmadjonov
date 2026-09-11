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

    # Общий лимит на страницу. Строгий «login_req» (5 запросов в минуту) здесь
    # стоять не может: одна страница phpMyAdmin тянет десятки css/js/картинок, и
    # всё после десятого файла получало 503 — интерфейс не открывался вообще.
    # Строгий лимит применяется ниже, точечно, к самой форме входа.
    limit_req zone=general_req burst=60 nodelay;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location ~ /\. {
        deny all;
    }

    # В каталоге пакета лежит ссылка doc/ на его документацию. Открыв её,
    # человек видит оглавление «Welcome to phpMyAdmin's documentation» и решает,
    # что phpMyAdmin сломан. Плюс setup/ и examples/ — это инструменты установки,
    # которым на работающем сервере делать нечего.
    location ^~ /doc/ {
        deny all;
    }
    location ^~ /setup {
        deny all;
    }
    location ^~ /examples/ {
        deny all;
    }
    location ^~ /sql/ {
        deny all;
    }
    location ^~ /libraries/ {
        deny all;
    }
    location ^~ /templates/ {
        deny all;
    }

    # Статика отдаётся без строгих лимитов и без записи в лог — это картинки
    # и скрипты самого phpMyAdmin, а не действия пользователя.
    location ~* \.(?:css|js|png|gif|jpg|jpeg|svg|ico|woff2?|ttf|map)$ {
        expires 7d;
        access_log off;
        try_files $uri =404;
    }

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    # Строгий лимит — только на отправку формы входа: именно её перебирают.
    # GET той же страницы под лимит не попадает, иначе интерфейс не открыть.
    location = /index.php {
        # Зона login_post считает только POST (см. nginx-global-hosting.conf):
        # открыть страницу входа можно сколько угодно раз, а вот перебирать
        # пароли — не больше пяти попыток в минуту.
        limit_req zone=login_post burst=10 nodelay;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root/index.php;
        fastcgi_pass unix:/run/php/phpmyadmin.sock;
        fastcgi_read_timeout 60s;
    }

    location ~ \.php$ {
        try_files $uri =404;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_pass unix:/run/php/phpmyadmin.sock;
        fastcgi_read_timeout 60s;
    }
}
