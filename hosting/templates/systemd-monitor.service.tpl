[Unit]
Description={{PANEL_NAME}} — один запуск monitor.sh

[Service]
Type=oneshot
User=root
EnvironmentFile={{ENV_FILE}}
ExecStart={{HOSTING_ROOT}}/hosting/scripts/monitor.sh
