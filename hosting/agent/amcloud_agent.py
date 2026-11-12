#!/usr/bin/env python3
"""Агент панели на сервере клиента.

Раз в 30 секунд отправляет в панель: память, диск, нагрузку и топ процессов.
Только чтение /proc, без сторонних библиотек. Ничего не принимает извне и не выполняет команд.
Настройки: /etc/amcloud-agent.conf (PANEL_URL, SERVER_ID, TOKEN).
"""
import json
import os
import time
import urllib.request

CONF = "/etc/amcloud-agent.conf"
INTERVAL = 30


def conf():
    out = {}
    with open(CONF) as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                out[k] = v
    return out


def meminfo():
    m = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":", 1)
            m[k] = int(v.split()[0]) * 1024
    total = m.get("MemTotal", 0)
    avail = m.get("MemAvailable", m.get("MemFree", 0))
    return total - avail, total


def disk():
    st = os.statvfs("/")
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    return total - free, total


def procs(prev, dt):
    """Топ-5 процессов по CPU за последний интервал и их память."""
    hz = os.sysconf("SC_CLK_TCK")
    page = os.sysconf("SC_PAGE_SIZE")
    cur, rows = {}, []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/stat") as f:
                raw = f.read()
            name = raw[raw.index("(") + 1:raw.rindex(")")]
            fields = raw[raw.rindex(")") + 2:].split()
            ticks = int(fields[11]) + int(fields[12])
            rss = int(fields[21]) * page
        except (OSError, ValueError, IndexError):
            continue
        cur[pid] = ticks
        if pid in prev and dt > 0:
            cpu = (ticks - prev[pid]) / hz / dt * 100
            rows.append({"name": name[:40], "cpu": round(cpu, 1), "mem": rss})
    rows.sort(key=lambda r: (r["cpu"], r["mem"]), reverse=True)
    return cur, rows[:5]


def main():
    c = conf()
    url = c["PANEL_URL"].rstrip("/") + "/api/agent/report"
    prev, last = {}, time.monotonic()
    while True:
        now = time.monotonic()
        prev, top = procs(prev, now - last)
        last = now
        mem_used, mem_total = meminfo()
        disk_used, disk_total = disk()
        body = json.dumps({
            "server_id": int(c["SERVER_ID"]), "mem_used": mem_used, "mem_total": mem_total,
            "disk_used": disk_used, "disk_total": disk_total, "load1": os.getloadavg()[0], "procs": top,
        }).encode()
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + c["TOKEN"]})
        try:
            urllib.request.urlopen(req, timeout=10).read()
        except Exception:
            pass  # панель недоступна — попробуем в следующий раз
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
