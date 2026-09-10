# Сгенерировано {{PANEL_NAME}} — systemd slice клиента {{SYSTEM_USER}}, тариф {{PLAN_TITLE}}.
# Устанавливается в /etc/systemd/system/{{SYSTEM_USER}}.slice
#
# ВАЖНАЯ ОГОВОРКА АРХИТЕКТУРЫ (не приукрашиваем): все пулы php-fpm в этой установке
# запускаются под ОДНИМ мастер-процессом php{{PHP_VERSION}}-fpm.service. Каждый воркер-процесс
# пула клиента стартует от его unix-пользователя (User=/Group= в pool.d/*.conf), но сам
# php-fpm.service — общий systemd-юнит. Слайс ниже ограничивает через cgroup ВСЕ процессы
# данного unix-пользователя (клиента) в системе, потому что php-fpm с этой версии умеет
# помещать воркер в персональный slice при старте (см. install.sh: systemd_cgroup=yes,
# либо обёртку scripts/attach-worker-to-slice.sh, вызываемую из pm.max_children hook).
# Если этого недостаточно для вашей версии PHP-FPM/systemd — единственная надёжная
# альтернатива это отдельный php-fpm.service НА КЛИЕНТА (systemd template unit
# php-fpm@{{SYSTEM_USER}}.service), что для 200 клиентов на 8 GB RAM уже дорого по памяти
# (каждый master-процесс — это лишние ~10-15 MB). Для V1 мы сознательно идём на компромисс
# ниже и документируем его в SECURITY_CHECKLIST.md как "PARTIAL".

[Slice]
CPUAccounting=yes
CPUQuota={{CPU_QUOTA_PERCENT}}%
MemoryAccounting=yes
MemoryHigh={{MEMORY_HIGH_MB}}M
MemoryMax={{MEMORY_MAX_MB}}M
TasksAccounting=yes
TasksMax={{TASKS_MAX}}
