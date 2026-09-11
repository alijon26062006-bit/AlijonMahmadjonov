; Отдельный пул для общего phpMyAdmin — свой unix-пользователь, не www-data.
[phpmyadmin]
user = phpmyadmin
group = phpmyadmin
listen = /run/php/phpmyadmin.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0660

pm = ondemand
pm.max_children = 4
pm.process_idle_timeout = 30s
pm.max_requests = 300
request_terminate_timeout = 60s

; Пакет дистрибутива разложен по нескольким каталогам: сам код в
; {{PHPMYADMIN_ROOT}}, общие библиотеки (Composer CaBundle и прочие) в
; /usr/share/php, настройки в /etc/phpmyadmin, сессии и временные файлы в
; /var/lib/phpmyadmin. Без них open_basedir рубит загрузку автозагрузчика, и
; phpMyAdmin отдаёт пустой 500 ещё до первой строки интерфейса.
php_admin_value[open_basedir] = {{PHPMYADMIN_ROOT}}:/usr/share/php:/etc/phpmyadmin:/var/lib/phpmyadmin:/tmp
php_admin_value[session.save_path] = /var/lib/phpmyadmin/tmp
php_admin_value[memory_limit] = 256M
php_admin_value[max_execution_time] = 60
php_admin_value[upload_max_filesize] = 128M
php_admin_value[post_max_size] = 128M
php_admin_flag[expose_php] = off
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
