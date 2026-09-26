"""bot doctor — ҳамаи нусхаҳои боти дӯкон дар ҳамин сервер.

    bot doctor          нишон медиҳад: куҷо насб аст, кадомаш кор мекунад, базаҳо
    bot doctor --fix    нусхаҳои зиёдатиро ХОМӮШ мекунад (ҳеҷ чиз нест намешавад)

Нусхаи асосӣ — ҳамон папкае, ки фармони `bot` бо он кор мекунад.
Нусхаи зиёдатӣ — папкаи дигар бо ҳамон токени бот. Пеш аз хомӯш кардан
базаи он ба data/other-copies/ нусхабардорӣ мешавад.
"""

from __future__ import annotations

import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import guard
from .config import ROOT

SEARCH_ROOTS = ("/root", "/home", "/opt", "/srv", "/var/www", "/usr/local", "/app")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "site-packages"}
UNIT_DIRS = ("/etc/systemd/system", "/lib/systemd/system", "/usr/lib/systemd/system")

G, R, Y, C, B, E = "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[1m", "\033[0m"


def ok(msg: str) -> None:
    print(f"{G}✅ {msg}{E}")


def bad(msg: str) -> None:
    print(f"{R}❌ {msg}{E}")


def warn(msg: str) -> None:
    print(f"{Y}⚠️  {msg}{E}")


# ── чӣ насб аст ───────────────────────────────────────────────────────
def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.split(" #")[0].strip().strip('"').strip("'")
    return values


def find_installs(roots=None, max_depth: int = 5) -> list[Path]:
    """Папкаҳое, ки дар онҳо боти дӯкон (shop/main.py) ҳаст."""
    found: set[Path] = set()
    for base in roots or SEARCH_ROOTS:
        base_path = Path(base)
        if not base_path.is_dir():
            continue
        base_depth = len(base_path.parts)
        for current, dirs, _files in os.walk(base_path, followlinks=False):
            here = Path(current)
            if len(here.parts) - base_depth >= max_depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if (here / "shop" / "main.py").is_file() and (here / "shop" / "db.py").is_file():
                found.add(here.resolve())
                dirs[:] = [d for d in dirs if d != "shop"]
    return sorted(found)


def db_path_for(install: Path, env: dict[str, str]) -> Path:
    data = Path(env.get("SHOP_DATA_DIR") or "data").expanduser()
    if not data.is_absolute():
        data = install / data
    return data / (env.get("SHOP_DB_NAME") or "shop.sqlite3")


def db_stats(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row

        def one(sql: str):
            try:
                return con.execute(sql).fetchone()[0]
            except sqlite3.Error:
                return None

        stats = {
            "users": one("SELECT COUNT(*) FROM users") or 0,
            "last_order": one("SELECT MAX(id) FROM orders") or 0,
            "last_order_at": one("SELECT MAX(created_at) FROM orders") or "—",
            "balance": (one("SELECT SUM(balance) FROM users") or 0) / 100,
        }
        con.close()
        return stats
    except sqlite3.Error as exc:
        return {"error": str(exc)}


# ── чӣ кор мекунад ────────────────────────────────────────────────────
@dataclass
class Proc:
    pid: int
    cwd: str
    in_container: bool


def running_bots() -> list[Proc]:
    procs: list[Proc] = []
    me = os.getpid()
    for entry in Path("/proc").iterdir() if Path("/proc").is_dir() else []:
        if not entry.name.isdigit() or int(entry.name) == me:
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if "shop.main" not in cmd:
            continue
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            cwd = "?"
        try:
            in_container = os.readlink(entry / "root") != "/"
        except OSError:
            in_container = False
        procs.append(Proc(int(entry.name), cwd, in_container))
    return procs


@dataclass
class Unit:
    name: str
    workdir: str
    active: str
    enabled: str


def _systemctl(*args: str) -> str:
    try:
        return subprocess.run(
            ["systemctl", *args], capture_output=True, text=True, timeout=15
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def shop_units() -> list[Unit]:
    """Хидматҳои systemd, ки боти дӯконро оғоз мекунанд."""
    units: list[Unit] = []
    seen: set[str] = set()
    for folder in UNIT_DIRS:
        for file in sorted(Path(folder).glob("*.service")) if Path(folder).is_dir() else []:
            if file.name in seen:
                continue
            try:
                text = file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "shop.main" not in text:
                continue
            seen.add(file.name)
            workdir = ""
            match = re.search(r"^WorkingDirectory=(.+)$", text, re.MULTILINE)
            if match:
                workdir = match.group(1).strip()
            props = dict(
                line.split("=", 1)
                for line in _systemctl("show", file.name, "-p", "ActiveState",
                                       "-p", "UnitFileState").splitlines()
                if "=" in line
            )
            units.append(Unit(file.name, workdir, props.get("ActiveState", "?"),
                              props.get("UnitFileState", "?")))
    return units


def docker_bots() -> list[str]:
    try:
        out = subprocess.run(
            ["docker", "ps", "--no-trunc", "--format", "{{.ID}}\t{{.Names}}\t{{.Command}}"],
            capture_output=True, text=True, timeout=15,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in out.splitlines() if "shop" in line]


# ── тасвири як насб ───────────────────────────────────────────────────
@dataclass
class Install:
    path: Path
    token_tag: str
    db: Path
    is_main: bool
    same_bot: bool
    stats: dict | None
    procs: list[Proc] = field(default_factory=list)
    units: list[Unit] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return bool(self.procs) or any(u.active == "active" for u in self.units)


def _inside(path: str, install: Path) -> bool:
    try:
        return Path(path).resolve() == install or install in Path(path).resolve().parents
    except OSError:
        return False


def survey(main_root: Path | None = None, roots=None) -> tuple[list[Install], list[Proc], list[Unit]]:
    main_root = Path(main_root or ROOT).resolve()
    roots = roots or SEARCH_ROOTS
    main_env = read_env(main_root / ".env")
    main_tag = guard.token_tag(main_env.get("SHOP_BOT_TOKEN", "")) if main_env.get(
        "SHOP_BOT_TOKEN") else ""

    paths = set(find_installs(roots)) | {main_root}
    procs, units = running_bots(), shop_units()
    installs: list[Install] = []
    for path in sorted(paths):
        env = read_env(path / ".env")
        token = env.get("SHOP_BOT_TOKEN", "")
        tag = guard.token_tag(token) if token else ""
        db = db_path_for(path, env)
        installs.append(Install(
            path=path, token_tag=tag, db=db, is_main=path == main_root,
            same_bot=bool(tag) and tag == main_tag, stats=db_stats(db),
            procs=[p for p in procs if not p.in_container and _inside(p.cwd, path)],
            units=[u for u in units if u.workdir and _inside(u.workdir, path)],
        ))
    matched = {p.pid for i in installs for p in i.procs}
    stray_procs = [p for p in procs if p.pid not in matched]
    matched_units = {u.name for i in installs for u in i.units}
    stray_units = [u for u in units if u.name not in matched_units]
    return installs, stray_procs, stray_units


def diverged(main_db: Path, other_db: Path, limit: int = 15) -> dict:
    """Чӣ дар нусхаи дигар ҳаст, ки дар базаи асосӣ нест."""
    report = {"balances": [], "orders_only_there": []}
    try:
        con = sqlite3.connect(f"file:{main_db}?mode=ro", uri=True)
        con.execute("ATTACH DATABASE ? AS other", (f"file:{other_db}?mode=ro",))
        report["balances"] = con.execute(
            "SELECT o.id, o.username, COALESCE(m.balance, 0), o.balance "
            "FROM other.users o LEFT JOIN main.users m ON m.id = o.id "
            "WHERE COALESCE(m.balance, 0) != o.balance "
            "ORDER BY ABS(o.balance - COALESCE(m.balance, 0)) DESC LIMIT ?", (limit,)
        ).fetchall()
        report["orders_only_there"] = con.execute(
            "SELECT o.id, o.created_at, o.title, o.target, o.price, o.status "
            "FROM other.orders o LEFT JOIN main.orders m ON m.id = o.id "
            "WHERE m.id IS NULL OR m.created_at != o.created_at OR m.target IS NOT o.target "
            "ORDER BY o.id DESC LIMIT ?", (limit,)
        ).fetchall()
        con.close()
    except sqlite3.Error as exc:
        report["error"] = str(exc)
    return report


# ── амал ──────────────────────────────────────────────────────────────
def backup_db(src: Path, dest_dir: Path, label: str) -> Path | None:
    if not src.is_file():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_") or "copy"
    dest = dest_dir / f"{safe}-{time.strftime('%Y%m%d-%H%M%S')}.sqlite3"
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return dest


def stop_install(inst: Install, main_label: str) -> list[str]:
    """Нусхаи зиёдатиро хомӯш мекунад ва намегузорад, ки боз сар шавад."""
    done: list[str] = []
    for unit in inst.units:
        _systemctl("stop", unit.name)
        _systemctl("disable", unit.name)
        done.append(f"служба {unit.name} остановлена и снята с автозапуска")
    for proc in inst.procs:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except OSError:
            continue
        for _ in range(20):
            try:
                os.kill(proc.pid, 0)
            except OSError:
                break
            time.sleep(0.5)
        else:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        done.append(f"процесс {proc.pid} остановлен")
    guard.mark_moved(inst.db.parent, f"лишняя копия; основная: {main_label}")
    done.append("метка MOVED_TO поставлена — сама не запустится")
    return done


# ── ҳисобот ───────────────────────────────────────────────────────────
def describe(inst: Install) -> None:
    if inst.is_main:
        role = f"{G}ОСНОВНАЯ (с ней работает команда bot){E}"
    elif inst.same_bot:
        role = f"{R}ЛИШНЯЯ КОПИЯ ЭТОГО ЖЕ БОТА{E}"
    elif not inst.token_tag:
        role = "без токена (не настроена)"
    else:
        role = "другой бот (другой токен) — не трогаем"
    print(f"\n{B}{inst.path}{E}\n   {role}")
    state = f"{G}работает{E}" if inst.running else "не запущена"
    print(f"   сейчас: {state}")
    for proc in inst.procs:
        print(f"   процесс: pid {proc.pid}")
    for unit in inst.units:
        print(f"   служба: {unit.name}  ({unit.active}, автозапуск: {unit.enabled})")
    if inst.stats is None:
        print(f"   база: нет ({inst.db})")
    elif "error" in inst.stats:
        print(f"   база: {inst.db} — не читается: {inst.stats['error']}")
    else:
        s = inst.stats
        print(f"   база: {inst.db}")
        print(f"         людей {s['users']}, последний заказ #{s['last_order']} "
              f"({str(s['last_order_at'])[:16].replace('T', ' ')}), на счетах {s['balance']:.2f} с.")


def run(argv: list[str]) -> int:
    fix = "--fix" in argv
    if os.geteuid() != 0:
        warn("Запустите от root, иначе часть процессов и служб не видно.")

    print(f"{B}Поиск копий бота на этом сервере{E}  ({guard.host_label()})")
    installs, stray_procs, stray_units = survey()
    main = next(i for i in installs if i.is_main)
    for inst in installs:
        describe(inst)

    dupes = [i for i in installs if i.same_bot and not i.is_main]
    running_dupes = [i for i in dupes if i.running]
    containers = docker_bots()

    print(f"\n{C}── Итог {'─' * 40}{E}")
    if not main.running:
        warn("Основной бот сейчас НЕ запущен. Запустить:  bot")
    for proc in stray_procs:
        warn(f"Бот-процесс pid {proc.pid} не из найденных папок (cwd {proc.cwd}"
             f"{', в контейнере' if proc.in_container else ''}).")
    for unit in stray_units:
        warn(f"Служба {unit.name} ({unit.active}) запускает бота из {unit.workdir or '?'}.")
    for line in containers:
        warn(f"Docker-контейнер с ботом: {line}")
        print("     Остановить: docker update --restart=no ID && docker stop ID")

    if not dupes:
        ok("Лишних копий этого бота на сервере нет.")
    for inst in dupes:
        if inst.stats and "error" not in inst.stats and main.stats and "error" not in main.stats:
            diff = diverged(main.db, inst.db)
            if diff.get("balances"):
                warn(f"В копии {inst.path} у {len(diff['balances'])}+ людей другой баланс:")
                for uid, name, here, there in diff["balances"]:
                    print(f"     {uid} @{name or '—'}: основная {here / 100:.2f} с., копия {there / 100:.2f} с.")
            if diff.get("orders_only_there"):
                warn("Заказы, которые есть только в копии:")
                for oid, at, title, target, price, status in diff["orders_only_there"]:
                    print(f"     #{oid} {str(at)[:16].replace('T', ' ')} {title} → {target} "
                          f"{price / 100:.2f} с. [{status}]")

    if running_dupes and not fix:
        bad(f"Работает лишних копий: {len(running_dupes)}. Выключить (ничего не удаляется):")
        print(f"     {B}bot doctor --fix{E}")
    if fix and dupes:
        backup_dir = main.db.parent / "other-copies"
        main_label = f"{guard.host_label()} {main.path}"
        for inst in dupes:
            print(f"\n{B}Выключаю копию {inst.path}{E}")
            saved = backup_db(inst.db, backup_dir, str(inst.path))
            if saved:
                ok(f"её база сохранена: {saved}")
            for line in stop_install(inst, main_label):
                ok(line)
        print()
        ok("Готово. Работает только основная копия.")
        print("   Если у кого-то из списка выше другой баланс — пришлите этот вывод, перенесём.")
    return 0


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
