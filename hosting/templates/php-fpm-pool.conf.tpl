; Сгенерировано панелью {{PANEL_NAME}} — правки будут перезаписаны.
; Пул клиента {{SYSTEM_USER}} ({{EMAIL}})

[{{SYSTEM_USER}}]
user = {{SYSTEM_USER}}
group = {{SYSTEM_USER}}

listen = {{LISTEN}}
listen.owner = {{WEB_USER}}
listen.group = {{WEB_USER}}
listen.mode = 0660

pm = ondemand
pm.max_children = 10
pm.process_idle_timeout = 30s
pm.max_requests = 500

; Каждый клиент видит только свой дом и системный /tmp пула
php_admin_value[open_basedir] = {{HOME}}:/usr/share/php:/tmp
php_admin_value[upload_tmp_dir] = {{HOME}}/tmp
php_admin_value[sys_temp_dir] = {{HOME}}/tmp
php_admin_value[session.save_path] = {{HOME}}/tmp
php_admin_value[error_log] = {{HOME}}/logs/php-error.log
php_admin_flag[log_errors] = on
php_admin_flag[display_errors] = off

; Шелл из PHP клиентам не нужен
php_admin_value[disable_functions] = exec,passthru,shell_exec,system,proc_open,popen,proc_nice,pcntl_exec,dl,symlink,link
php_admin_flag[allow_url_include] = off

php_admin_value[memory_limit] = 256M
php_admin_value[upload_max_filesize] = {{UPLOAD_MAX_MB}}M
php_admin_value[post_max_size] = {{UPLOAD_MAX_MB}}M
php_admin_value[max_execution_time] = 60
