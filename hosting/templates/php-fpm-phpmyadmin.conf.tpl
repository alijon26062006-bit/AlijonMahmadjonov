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

php_admin_value[open_basedir] = {{PHPMYADMIN_ROOT}}:/tmp
php_admin_value[memory_limit] = 256M
php_admin_value[max_execution_time] = 60
php_admin_value[upload_max_filesize] = 128M
php_admin_value[post_max_size] = 128M
php_admin_flag[expose_php] = off
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
