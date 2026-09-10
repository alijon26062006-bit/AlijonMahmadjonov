[Unit]
Description={{PANEL_NAME}} — ежедневная проверка и продление сертификатов

[Timer]
OnCalendar=*-*-* 04:10:00
Persistent=true

[Install]
WantedBy=timers.target
