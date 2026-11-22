"""user_data для нового (или переустановленного) сервера.

1. Разрешает вход root по паролю: /etc/ssh/sshd_config.d/00-panel.conf. Имя с 00 —
   sshd берёт первое значение, и наш файл читается раньше 50-cloud-init.conf.
2. Ставит агента живой аналитики (только стандартная библиотека Python) и
   systemd-службу для него. Токен сервера — в /etc/panel-agent.env с правами 600.
"""
from __future__ import annotations

import base64
from pathlib import Path

AGENT_SOURCE = Path(__file__).resolve().parents[2] / "vps_agent" / "panel_agent.py"
MAX_USER_DATA = 32 * 1024

SSHD_CONF = "PermitRootLogin yes\nPasswordAuthentication yes\n"

UNIT = """[Unit]
Description=VPS panel live agent
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/panel-agent/agent.py
Restart=always
RestartSec=5
Nice=10

[Install]
WantedBy=multi-user.target
"""


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def build(agent_url: str, agent_token: str) -> str:
    agent = AGENT_SOURCE.read_text(encoding="utf-8")
    env = f"PANEL_URL={agent_url}\nPANEL_TOKEN={agent_token}\n"
    doc = f"""#cloud-config
write_files:
  - path: /etc/ssh/sshd_config.d/00-panel.conf
    permissions: '0644'
    encoding: b64
    content: {_b64(SSHD_CONF)}
  - path: /opt/panel-agent/agent.py
    permissions: '0755'
    encoding: b64
    content: {_b64(agent)}
  - path: /etc/panel-agent.env
    permissions: '0600'
    encoding: b64
    content: {_b64(env)}
  - path: /etc/systemd/system/panel-agent.service
    permissions: '0644'
    encoding: b64
    content: {_b64(UNIT)}
runcmd:
  - [sh, -c, "systemctl restart ssh || systemctl restart sshd || true"]
  - [sh, -c, "command -v python3 >/dev/null || (apt-get update -y && apt-get install -y python3) || dnf install -y python3 || true"]
  - [systemctl, daemon-reload]
  - [systemctl, enable, --now, panel-agent.service]
"""
    if len(doc.encode()) > MAX_USER_DATA:
        raise ValueError("user_data больше 32 КиБ — Hetzner его не примет")
    return doc
