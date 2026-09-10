[Unit]
Description={{PANEL_NAME}} — certbot renew + reload nginx при успехе

[Service]
Type=oneshot
User=root
ExecStart=/usr/bin/certbot renew --quiet --deploy-hook "nginx -t && systemctl reload nginx"
