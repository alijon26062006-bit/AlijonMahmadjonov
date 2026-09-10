; Пул для самой панели управления — отдельный unix-пользователь (hosting-panel),
; НЕ www-data и НЕ клиентский. У этого пула НЕТ переменных MYSQL_ADMIN_* в окружении
; (см. .env vs /etc/hosting/worker.env) — панель физически не может создавать/удалять
; чужие базы данных, даже если в её PHP-коде появится баг.

[hosting-panel]
user = hosting-panel
group = hosting-panel

listen = /run/php/hosting-panel.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0660

pm = ondemand
pm.max_children = 8
pm.process_idle_timeout = 30s
pm.max_requests = 1000
request_terminate_timeout = 30s

php_admin_value[open_basedir] = {{HOSTING_ROOT}}:/tmp
php_admin_flag[expose_php] = off
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
php_admin_value[error_log] = /var/log/hosting/panel-php-error.log

; Панели не нужны shell-функции вообще
php_admin_value[disable_functions] = exec,shell_exec,system,passthru,proc_open,popen,pcntl_exec

php_admin_value[memory_limit] = 128M
php_admin_value[max_execution_time] = 30
php_admin_value[upload_max_filesize] = {{UPLOAD_MAX_MB}}M
php_admin_value[post_max_size] = {{UPLOAD_MAX_MB}}M

php_admin_value[opcache.enable] = 1
php_admin_value[opcache.memory_consumption] = 64
php_admin_value[opcache.validate_timestamps] = 1
php_admin_value[opcache.revalidate_freq] = 2
