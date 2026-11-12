"""cloud-init для новых серверов: ставит агент панели и включает вход root по паролю."""
from __future__ import annotations

import base64

from .config import BASE_DIR

AGENT_PATH = BASE_DIR / "agent" / "amcloud_agent.py"

UNIT = """[Unit]
Description=AM Cloud metrics agent
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/amcloud-agent
Restart=always
RestartSec=15
DynamicUser=no
User=root
Nice=10

[Install]
WantedBy=multi-user.target
"""


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def build_user_data(panel_url: str, server_id: int, agent_token: str) -> str:
    agent = AGENT_PATH.read_text(encoding="utf-8")
    conf = f"PANEL_URL={panel_url}\nSERVER_ID={server_id}\nTOKEN={agent_token}\n"
    return f"""#cloud-config
ssh_pwauth: true
write_files:
  - path: /usr/local/bin/amcloud-agent
    permissions: "0755"
    encoding: b64
    content: {_b64(agent)}
  - path: /etc/amcloud-agent.conf
    permissions: "0600"
    encoding: b64
    content: {_b64(conf)}
  - path: /etc/systemd/system/amcloud-agent.service
    permissions: "0644"
    encoding: b64
    content: {_b64(UNIT)}
runcmd:
  - [systemctl, daemon-reload]
  - [systemctl, enable, --now, amcloud-agent.service]
"""
