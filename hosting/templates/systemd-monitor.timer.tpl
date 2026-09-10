[Unit]
Description={{PANEL_NAME}} — периодическая проверка ресурсов и алерты в Telegram

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
