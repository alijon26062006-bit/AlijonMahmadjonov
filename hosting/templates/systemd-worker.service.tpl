[Unit]
Description={{PANEL_NAME}} root worker — выполняет задания из очереди jobs
After=network.target mariadb.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/php {{HOSTING_ROOT}}/worker/bin/hosting-worker.php
Restart=on-failure
RestartSec=5
EnvironmentFile={{ENV_FILE}}

# Воркер выполняет root-операции (useradd, chown, nginx reload) по определению —
# песочница ему не сужает права, но код только с whitelisted job-типами (см. JobHandler::TYPES).
NoNewPrivileges=no

[Install]
WantedBy=multi-user.target
