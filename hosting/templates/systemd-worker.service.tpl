[Unit]
Description={{PANEL_NAME}} root worker — выполняет задания из очереди jobs
After=network.target mariadb.service
Wants=mariadb.service

# Без этого пять быстрых падений подряд навсегда переводят службу в failed,
# и её приходится поднимать руками. Воркер должен возвращаться сам.
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
ExecStart=/usr/bin/php {{HOSTING_ROOT}}/hosting/worker/bin/hosting-worker.php
Restart=always
RestartSec=5
EnvironmentFile={{ENV_FILE}}

# Весь вывод воркера — в journal, чтобы `journalctl -u hosting-worker` показывал
# и причину неудачного задания, и причину, по которой он не может стартовать.
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hosting-worker

# Воркер выполняет root-операции (useradd, chown, nginx reload) по определению —
# песочница ему не сужает права, но код только с whitelisted job-типами (см. JobHandler::TYPES).
NoNewPrivileges=no

[Install]
WantedBy=multi-user.target
