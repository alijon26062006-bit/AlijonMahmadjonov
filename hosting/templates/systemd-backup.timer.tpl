[Unit]
Description={{PANEL_NAME}} — ежедневное резервное копирование

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true

[Install]
WantedBy=timers.target
