"""HTTP-API проверки ника. Только стандартная библиотека Python 3.10+.

    GET  /nick?game=ff&id=123456789        → {"ok": true, "nickname": "..."}
    GET  /nick?game=mlbb&id=123&server=456
    POST /nick   {"game": "ff", "id": "123456789"}
    GET  /games                            → список поддерживаемых игр
    GET  /health                           → проверка, что сервис жив

Наружу отдаётся только ник. Эндпоинты заказов (/order) сервис не вызывает
никогда — потратить деньги через него невозможно.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from . import games

log = logging.getLogger("nickapi")

FIRELOOT_URL = "https://partner.firelootshop.com/api/v1"

# Понятный текст вместо кода поставщика.
ERRORS: dict[str, str] = {
    "invalid_uid": "ID игрока неверный",
    "invalid_username": "Username неверный",
    "not_found": "Аккаунт не найден",
    "invalid_request": "Запрос неполный",
    "unauthorized": "Ключ API неверный",
    "region_unsupported": "Регион аккаунта не поддерживается",
    "product_not_found": "Эта игра недоступна на вашем ключе",
    "rate_limited": "Слишком много запросов, подождите немного",
    "service_unavailable": "Сервис поставщика временно недоступен",
}


# ── настройки ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    upstream: str = FIRELOOT_URL
    token: str = ""                 # свой ключ доступа к этому сервису
    host: str = "0.0.0.0"
    port: int = 8081
    timeout: float = 30.0
    cache_ttl: float = 300.0        # сколько секунд помнить найденный ник
    rate_limit: int = 60            # запросов в минуту с одного IP
    cors: bool = False


def read_env_file(path: pathlib.Path) -> dict[str, str]:
    """Читает .env, не требуя python-dotenv."""
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
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings(root: pathlib.Path | None = None) -> Settings:
    """Переменные окружения важнее .env рядом с проектом."""
    env = dict(read_env_file((root or pathlib.Path(__file__).resolve().parent.parent) / ".env"))
    env.update({k: v for k, v in os.environ.items() if v})

    def pick(*names: str, default: str = "") -> str:
        for name in names:
            if env.get(name):
                return env[name].strip()
        return default

    def number(name: str, default: float) -> float:
        try:
            return float(pick(name) or default)
        except ValueError:
            return default

    return Settings(
        api_key=pick("NICK_API_KEY", "FIRELOOT_KEY", "SHOP_SUPPLIER_KEY"),
        upstream=pick("NICK_API_UPSTREAM", "SHOP_SUPPLIER_URL", default=FIRELOOT_URL).rstrip("/"),
        token=pick("NICK_API_TOKEN"),
        host=pick("NICK_API_HOST", default="0.0.0.0"),
        port=int(number("NICK_API_PORT", 8081)),
        timeout=number("NICK_API_TIMEOUT", 30.0),
        cache_ttl=number("NICK_API_CACHE", 300.0),
        rate_limit=int(number("NICK_API_RATE", 60)),
        cors=pick("NICK_API_CORS") in ("1", "true", "yes", "on"),
    )


# ── вспомогательное ──────────────────────────────────────────────────
class Cache:
    """Найденные ники живут недолго — чтобы не дёргать поставщика зря."""

    def __init__(self, ttl: float) -> None:
        self.ttl = ttl
        self._items: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        if self.ttl <= 0:
            return None
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            expires, value = item
            if expires < time.monotonic():
                self._items.pop(key, None)
                return None
            return dict(value)

    def put(self, key: str, value: dict) -> None:
        if self.ttl <= 0:
            return
        with self._lock:
            if len(self._items) > 5000:        # защита от разрастания памяти
                self._items.clear()
            self._items[key] = (time.monotonic() + self.ttl, dict(value))


class RateLimiter:
    """Не больше N запросов в минуту с одного адреса."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, who: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits.get(who, ()) if now - t < 60.0]
            if len(hits) >= self.limit:
                self._hits[who] = hits
                return False
            hits.append(now)
            self._hits[who] = hits
            if len(self._hits) > 5000:
                self._hits = {who: hits}
            return True


def _post(url: str, key: str, payload: dict, timeout: float) -> tuple[int, dict]:
    """POST c JSON. Ошибки сети наружу не летят — возвращаем код и тело."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:            # 4xx/5xx — тело важно
        raw, status = exc.read(), exc.code
    except Exception as exc:                          # таймаут, DNS, обрыв
        log.warning("Поставщик недоступен: %s", exc)
        return 0, {}
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        data = {}
    return status, (data if isinstance(data, dict) else {})


# ── логика проверки ──────────────────────────────────────────────────
@dataclass
class Service:
    settings: Settings
    fetch: Callable[[str, str, dict, float], tuple[int, dict]] = _post
    cache: Cache = field(init=False)
    limiter: RateLimiter = field(init=False)

    def __post_init__(self) -> None:
        self.cache = Cache(self.settings.cache_ttl)
        self.limiter = RateLimiter(self.settings.rate_limit)

    def nick(self, game_key: str, uid: str, server: str = "", amount: int = 50) -> dict:
        game = games.find(game_key)
        if game is None:
            known = ", ".join(g.key for g in games.GAMES)
            return {"ok": False, "code": "unknown_game",
                    "error": f"Игра «{game_key}» не поддерживается. Есть: {known}"}

        uid = (uid or "").strip().lstrip("@")
        if not uid:
            return {"ok": False, "code": "invalid_request",
                    "error": f"Не указан {game.id_label}"}
        if game.needs_server and not (server or "").strip():
            return {"ok": False, "code": "server_required",
                    "error": "Для этой игры нужен номер сервера (server)"}
        if not self.settings.api_key:
            return {"ok": False, "code": "no_key",
                    "error": "На сервере не задан ключ NICK_API_KEY"}

        cache_key = f"{game.key}|{uid}|{server}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            cached["cached"] = True
            return cached

        if game.telegram:
            path, payload = "/telegram/check", {"username": uid, "stars": int(amount)}
        else:
            path, payload = "/validate", {"sku": game.sku, "uid": uid}
            if server:
                payload["server_id"] = str(server).strip()

        status, data = self.fetch(
            f"{self.settings.upstream}{path}", self.settings.api_key,
            payload, self.settings.timeout,
        )
        if status == 0:
            return {"ok": False, "code": "service_unavailable",
                    "error": ERRORS["service_unavailable"]}

        nickname = data.get("player_name") or data.get("name")
        if status == 200 and data.get("valid") is True and nickname:
            result = {"ok": True, "game": game.key, "title": game.title,
                      "id": uid, "nickname": str(nickname), "cached": False}
            if server:
                result["server"] = str(server)
            self.cache.put(cache_key, result)
            return result

        error = data.get("error") if isinstance(data.get("error"), dict) else {}
        code = error.get("code") or data.get("code") or (
            "invalid_username" if game.telegram else "invalid_uid")
        message = ERRORS.get(code) or error.get("message") or data.get("message") \
            or f"Проверка не прошла (HTTP {status})"
        return {"ok": False, "game": game.key, "id": uid, "code": code, "error": message}


# ── HTTP ─────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    service: Service                      # подставляется в serve()
    server_version = "nickapi/1.0"
    protocol_version = "HTTP/1.1"

    # ── ответы ──
    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if self.service.settings.cors:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Api-Key")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:   # тише стандартного
        log.info("%s %s", self.address_string(), fmt % args)

    # ── доступ ──
    def _authorized(self, query: dict[str, list[str]]) -> bool:
        token = self.service.settings.token
        if not token:
            return True
        given = self.headers.get("X-Api-Key") or ""
        if not given:
            auth = self.headers.get("Authorization") or ""
            given = auth[7:] if auth.lower().startswith("bearer ") else ""
        if not given:
            given = (query.get("key") or [""])[0]
        return given == token

    def _who(self) -> str:
        forwarded = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return forwarded or self.client_address[0]

    # ── маршруты ──
    def do_OPTIONS(self) -> None:          # noqa: N802 — имя задано базовым классом
        self._send(204, {})

    def do_GET(self) -> None:              # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        self._route(parsed.path.rstrip("/") or "/", query, {})

    def do_POST(self) -> None:             # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(length, 64 * 1024)) if length > 0 else b""
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self._send(400, {"ok": False, "code": "bad_json", "error": "Тело запроса не JSON"})
            return
        self._route(parsed.path.rstrip("/") or "/", parse_qs(parsed.query),
                    body if isinstance(body, dict) else {})

    def _route(self, path: str, query: dict[str, list[str]], body: dict) -> None:
        if path in ("/health", "/"):
            self._send(200, {"ok": True, "service": "nickapi",
                             "games": len(games.GAMES),
                             "key": bool(self.service.settings.api_key)})
            return
        if not self._authorized(query):
            self._send(401, {"ok": False, "code": "unauthorized",
                             "error": "Нужен заголовок X-Api-Key"})
            return
        if path == "/games":
            self._send(200, {"ok": True, "games": games.listing()})
            return
        if path != "/nick":
            self._send(404, {"ok": False, "code": "not_found",
                             "error": "Есть только /nick, /games и /health"})
            return
        if not self.service.limiter.allow(self._who()):
            self._send(429, {"ok": False, "code": "rate_limited",
                             "error": ERRORS["rate_limited"]})
            return

        def value(*names: str) -> str:
            for name in names:
                if body.get(name):
                    return str(body[name]).strip()
                if query.get(name):
                    return query[name][0].strip()
            return ""

        amount = value("stars", "amount")
        result = self.service.nick(
            value("game", "g"),
            value("id", "uid", "player", "username"),
            value("server", "server_id", "zone"),
            int(amount) if amount.isdigit() else 50,
        )
        codes = {"unauthorized": 502, "no_key": 500, "service_unavailable": 503,
                 "unknown_game": 400, "invalid_request": 400, "server_required": 400,
                 "rate_limited": 429}
        self._send(200 if result["ok"] else codes.get(result.get("code", ""), 404), result)


def serve(settings: Settings | None = None) -> None:
    cfg = settings or load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")

    handler = type("BoundHandler", (Handler,), {"service": Service(cfg)})
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), handler)
    httpd.daemon_threads = True

    print(f"✅ API проверки ника: http://{cfg.host}:{cfg.port}")
    print(f"   Пример:  curl 'http://127.0.0.1:{cfg.port}/nick?game=ff&id=123456789'")
    if not cfg.api_key:
        print("⚠️  Ключ поставщика не найден — задайте NICK_API_KEY")
    if not cfg.token:
        print("⚠️  NICK_API_TOKEN пуст — сервис отвечает всем. "
              "Закройте его ключом или файрволом.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹  Остановлен")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
