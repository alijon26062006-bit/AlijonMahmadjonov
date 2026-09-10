[Unit]
Description={{PANEL_NAME}} telegram bot — отвечает на /start и открывает Mini App
After=network-online.target
Wants=network-online.target

StartLimitIntervalSec=0

[Service]
Type=simple
# Боту не нужны ни root, ни база: он только принимает сообщения и отправляет
# кнопку. Всё привилегированное делает root-воркер по заданиям из очереди.
User=hosting-panel
Group=hosting-panel
ExecStart=/usr/bin/php {{HOSTING_ROOT}}/hosting/worker/bin/hosting-bot.php
Restart=always
RestartSec=5
EnvironmentFile=-{{ENV_FILE}}

StandardOutput=journal
StandardError=journal
SyslogIdentifier=hosting-bot

NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
# ProtectHome намеренно НЕ включаем: репозиторий часто лежит в /root, и с
# закрытым /home|/root служба не смогла бы прочитать собственный скрипт.
# Единственное, что боту нужно писать, — offset обработанных сообщений.
ReadWritePaths=/var/lib/hosting

[Install]
WantedBy=multi-user.target
