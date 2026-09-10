; Сгенерировано {{PANEL_NAME}} — правки перезатрутся при следующем apply_php_fpm.
; Пул клиента {{SYSTEM_USER}} ({{EMAIL}}), тариф {{PLAN_TITLE}}

[{{SYSTEM_USER}}]
user = {{SYSTEM_USER}}
group = {{SYSTEM_USER}}

listen = {{LISTEN}}
listen.owner = www-data
listen.group = www-data
listen.mode = 0660

; ondemand — воркеры не висят в памяти, пока на сайт никто не заходит.
; Так 200 клиентов не превращаются в 200 вечно живых процессов PHP.
pm = ondemand
pm.max_children = {{PM_MAX_CHILDREN}}
pm.process_idle_timeout = 20s
pm.max_requests = 500
request_terminate_timeout = 40s

; Каждый клиент видит только свой дом и системный /tmp пула
php_admin_value[open_basedir] = {{HOME}}:/tmp
php_admin_value[upload_tmp_dir] = {{HOME}}/tmp
php_admin_value[sys_temp_dir] = {{HOME}}/tmp
php_admin_value[session.save_path] = {{HOME}}/tmp

php_admin_flag[expose_php] = off
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
php_admin_value[error_log] = {{HOME}}/logs/php-error.log
php_admin_flag[allow_url_include] = off

; disable_functions — это не sandbox, только дополнительный барьер поверх open_basedir,
; отдельного unix-пользователя и лимитов systemd/cgroup (см. templates/systemd-client-slice.tpl).
php_admin_value[disable_functions] = exec,shell_exec,system,passthru,proc_open,popen,proc_nice,pcntl_exec,dl,symlink,link

php_admin_value[memory_limit] = {{MEMORY_LIMIT_MB}}M
php_admin_value[upload_max_filesize] = {{UPLOAD_MAX_MB}}M
php_admin_value[post_max_size] = {{UPLOAD_MAX_MB}}M
php_admin_value[max_execution_time] = 30
php_admin_value[max_input_time] = 60

php_admin_value[opcache.enable] = 1
php_admin_value[opcache.memory_consumption] = 128
php_admin_value[opcache.interned_strings_buffer] = 16
php_admin_value[opcache.max_accelerated_files] = 10000
php_admin_value[opcache.validate_timestamps] = 1
php_admin_value[opcache.revalidate_freq] = 2

; Локальная почта клиентам не даётся (см. секцию MAIL в README) — используйте внешний SMTP.
php_admin_value[sendmail_path] = /bin/true
