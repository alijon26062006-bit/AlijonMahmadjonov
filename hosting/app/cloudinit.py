"""cloud-init для новых серверов: ставит агент панели и включает вход root по паролю."""
from __future__ import annotations

import base64

from .config import BASE_DIR

AGENT_PATH = BASE_DIR / "agent" / "averix_agent.py"

UNIT = """[Unit]
Description=Averix metrics agent
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/averix-agent
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


# Сервер создаётся с ключом панели; чтобы клиент мог войти root по своему паролю, разрешаем это явно.
# Файл с префиксом 00- читается раньше 50-cloud-init.conf, а в sshd побеждает первое значение.
SSHD = "PermitRootLogin yes\nPasswordAuthentication yes\n"


def build_user_data(panel_url: str, server_id: int, agent_token: str) -> str:
    agent = AGENT_PATH.read_text(encoding="utf-8")
    conf = f"PANEL_URL={panel_url}\nSERVER_ID={server_id}\nTOKEN={agent_token}\n"
    return f"""#cloud-config
ssh_pwauth: true
write_files:
  - path: /usr/local/bin/averix-agent
    permissions: "0755"
    encoding: b64
    content: {_b64(agent)}
  - path: /etc/averix-agent.conf
    permissions: "0600"
    encoding: b64
    content: {_b64(conf)}
  - path: /etc/ssh/sshd_config.d/00-averix.conf
    permissions: "0644"
    encoding: b64
    content: {_b64(SSHD)}
  - path: /etc/systemd/system/averix-agent.service
    permissions: "0644"
    encoding: b64
    content: {_b64(UNIT)}
runcmd:
  - [sh, -c, "systemctl restart ssh 2>/dev/null || systemctl restart sshd"]
  - [systemctl, daemon-reload]
  - [systemctl, enable, --now, averix-agent.service]
"""
