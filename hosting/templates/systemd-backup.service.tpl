[Unit]
Description={{PANEL_NAME}} — один запуск backup.sh для всех клиентов

[Service]
Type=oneshot
User=root
EnvironmentFile={{ENV_FILE}}
ExecStart={{HOSTING_ROOT}}/scripts/backup.sh --all
