#!/usr/bin/env python3
"""Агент VPS-панели: раз в секунду отправляет нагрузку сервера на панель.

Только стандартная библиотека Python 3 и /proc — ставить ничего не нужно.
Канал — WebSocket (wss://ДОМЕН/agent) с токеном этого сервера.
Обрыв — переподключение с паузой. Настройки — /etc/panel-agent.env (права 600).
"""
import base64
import json
import os
import socket
import ssl
import struct
import time
from urllib.parse import urlparse

CONF = os.environ.get("PANEL_AGENT_CONF", "/etc/panel-agent.env")


def read_conf():
    conf = {}
    with open(CONF) as fh:
        for line in fh:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                conf[k] = v
    return conf


# ── сбор данных из /proc ──

def cpu_times():
    out = []
    with open("/proc/stat") as fh:
        for line in fh:
            if not line.startswith("cpu"):
                break
            parts = line.split()
            vals = list(map(int, parts[1:9]))
            idle = vals[3] + vals[4]
            out.append((sum(vals), idle))
    return out  # [итого, cpu0, cpu1, ...]


def meminfo():
    info = {}
    with open("/proc/meminfo") as fh:
        for line in fh:
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) * 1024
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    return {"total": total, "used": total - avail,
            "swap_total": info.get("SwapTotal", 0),
            "swap_used": info.get("SwapTotal", 0) - info.get("SwapFree", 0)}


def disk_io():
    rd = wr = 0
    with open("/proc/diskstats") as fh:
        for line in fh:
            p = line.split()
            name = p[2]
            if name.startswith(("loop", "ram", "sr", "dm-")) or (name[-1].isdigit() and not name.startswith("nvme")):
                continue
            if name.startswith("nvme") and "p" in name[4:]:
                continue
            rd += int(p[5]) * 512
            wr += int(p[9]) * 512
    return rd, wr


def net_io():
    rx = tx = 0
    with open("/proc/net/dev") as fh:
        for line in fh.readlines()[2:]:
            name, data = line.split(":", 1)
            if name.strip() == "lo":
                continue
            v = data.split()
            rx += int(v[0])
            tx += int(v[8])
    return rx, tx


def connections():
    n = 0
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path) as fh:
                n += sum(1 for line in fh.readlines()[1:] if line.split()[3] == "01")
        except OSError:
            pass
    return n


def processes():
    """{pid: (имя, cpu-тики, rss байт)}"""
    page = os.sysconf("SC_PAGE_SIZE")
    out = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/stat") as fh:
                raw = fh.read()
            name = raw[raw.index("(") + 1:raw.rindex(")")]
            rest = raw[raw.rindex(")") + 2:].split()
            ticks = int(rest[11]) + int(rest[12])
            rss = int(rest[21]) * page
            out[int(pid)] = (name, ticks, rss)
        except (OSError, ValueError, IndexError):
            continue
    return out


class Sampler:
    def __init__(self):
        self.prev_cpu = cpu_times()
        self.prev_disk = disk_io()
        self.prev_net = net_io()
        self.prev_proc = processes()
        self.prev_t = time.monotonic()
        self.hz = os.sysconf("SC_CLK_TCK")
        self.cores = max(len(self.prev_cpu) - 1, 1)

    def sample(self):
        t = time.monotonic()
        dt = max(t - self.prev_t, 0.001)
        cpu = cpu_times()
        pct = []
        for (tot, idle), (ptot, pidle) in zip(cpu, self.prev_cpu):
            d = tot - ptot
            pct.append(round(100.0 * (d - (idle - pidle)) / d, 1) if d > 0 else 0.0)
        rd, wr = disk_io()
        rx, tx = net_io()
        procs = processes()
        mem = meminfo()
        st = os.statvfs("/")
        disk_total = st.f_blocks * st.f_frsize
        disk_used = disk_total - st.f_bavail * st.f_frsize
        top = []
        for pid, (name, ticks, rss) in procs.items():
            before = self.prev_proc.get(pid)
            used = (ticks - before[1]) if before else 0
            top.append((used, pid, name, rss))
        top.sort(reverse=True)
        load = os.getloadavg()
        with open("/proc/uptime") as fh:
            uptime = float(fh.read().split()[0])
        data = {
            "t": int(time.time()),
            "cpu": pct[0] if pct else 0.0,
            "cores": pct[1:],
            "ram_used": mem["used"], "ram_total": mem["total"],
            "swap_used": mem["swap_used"], "swap_total": mem["swap_total"],
            "disk_used": disk_used, "disk_total": disk_total,
            "disk_read": int((rd - self.prev_disk[0]) / dt), "disk_write": int((wr - self.prev_disk[1]) / dt),
            "net_in": int((rx - self.prev_net[0]) / dt), "net_out": int((tx - self.prev_net[1]) / dt),
            "load": [round(x, 2) for x in load], "uptime": int(uptime),
            "conns": connections(),
            "top": [{"pid": pid, "name": name[:40], "cpu": round(100.0 * used / self.hz / dt, 1),
                     "rss": rss} for used, pid, name, rss in top[:10]],
        }
        self.prev_cpu, self.prev_disk, self.prev_net, self.prev_proc, self.prev_t = cpu, (rd, wr), (rx, tx), procs, t
        return data


# ── минимальный WebSocket-клиент (RFC 6455) ──

class WS:
    def __init__(self, url, token):
        u = urlparse(url)
        port = u.port or (443 if u.scheme == "wss" else 80)
        raw = socket.create_connection((u.hostname, port), timeout=15)
        if u.scheme == "wss":
            raw = ssl.create_default_context().wrap_socket(raw, server_hostname=u.hostname)
        key = base64.b64encode(os.urandom(16)).decode()
        path = u.path or "/"
        req = (f"GET {path} HTTP/1.1\r\nHost: {u.hostname}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
               f"Authorization: Bearer {token}\r\nUser-Agent: panel-agent/1\r\n\r\n")
        raw.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = raw.recv(1024)
            if not chunk:
                raise ConnectionError("сервер закрыл соединение")
            head += chunk
        status = head.split(b"\r\n", 1)[0]
        if b" 101 " not in status:
            raise ConnectionError(status.decode(errors="replace"))
        self.sock = raw
        self.sock.settimeout(0.05)

    def send(self, text):
        payload = text.encode()
        header = bytearray([0x81])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack("!H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", n)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + mask + masked)

    def drain(self):
        """Прочитать входящие кадры: ответить на ping, заметить close."""
        try:
            data = self.sock.recv(4096)
        except (socket.timeout, ssl.SSLWantReadError):
            return
        if not data:
            raise ConnectionError("соединение закрыто")
        opcode = data[0] & 0x0F
        if opcode == 0x8:
            raise ConnectionError("панель закрыла соединение")
        if opcode == 0x9:  # ping → pong
            self.sock.sendall(bytes([0x8A, 0x80]) + os.urandom(4))

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def main():
    conf = read_conf()
    url, token = conf["PANEL_URL"], conf["PANEL_TOKEN"]
    sampler = Sampler()
    pause = 2
    while True:
        ws = None
        try:
            ws = WS(url, token)
            pause = 2
            while True:
                started = time.monotonic()
                ws.send(json.dumps(sampler.sample(), separators=(",", ":")))
                ws.drain()
                time.sleep(max(0.0, 1.0 - (time.monotonic() - started)))
        except Exception as exc:  # noqa: BLE001 — любой обрыв: подождать и переподключиться
            print(f"panel-agent: {exc}; повтор через {pause} с", flush=True)
            if ws:
                ws.close()
            time.sleep(pause)
            pause = min(pause * 2, 60)


if __name__ == "__main__":
    main()
