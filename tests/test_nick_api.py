"""Тесты API проверки ника. Поставщик подменяется — сеть не нужна."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from nickapi import games, server


def make_service(reply, *, token: str = "", **overrides) -> server.Service:
    """reply — либо (status, data), либо функция от payload."""
    calls: list[dict] = []

    def fetch(url: str, key: str, payload: dict, timeout: float):
        calls.append({"url": url, "key": key, "payload": payload})
        return reply(payload) if callable(reply) else reply

    settings = server.Settings(api_key="test-key", token=token, **overrides)
    service = server.Service(settings, fetch=fetch)
    service.calls = calls          # type: ignore[attr-defined]
    return service


# ── таблица игр ───────────────────────────────────────────────────────
def test_game_lookup_accepts_aliases_and_case():
    assert games.find("ff").key == "ff"
    assert games.find("Mobile_Legends").key == "mlbb"
    assert games.find("PUBGM").key == "pubg"
    assert games.find("чего-то нет") is None


def test_every_game_has_sku_except_telegram():
    for game in games.GAMES:
        assert game.sku or game.telegram, game.key


def test_listing_marks_games_needing_server():
    by_key = {row["game"]: row for row in games.listing()}
    assert by_key["mlbb"]["needs_server"] is True
    assert by_key["ff"]["needs_server"] is False


# ── логика проверки ───────────────────────────────────────────────────
def test_valid_id_returns_nickname():
    service = make_service((200, {"valid": True, "player_name": "AlijonTJ"}))
    result = service.nick("ff", "123456789")
    assert result == {"ok": True, "game": "ff", "title": "Free Fire (СНГ)",
                      "id": "123456789", "nickname": "AlijonTJ", "cached": False}
    assert service.calls[0]["url"].endswith("/validate")
    assert service.calls[0]["payload"] == {"sku": "diamonds_110", "uid": "123456789"}


def test_invalid_id_returns_readable_error():
    service = make_service((200, {"valid": False, "error": {"code": "invalid_uid"}}))
    result = service.nick("pubg", "1")
    assert result["ok"] is False
    assert result["code"] == "invalid_uid"
    assert result["error"] == "ID игрока неверный"


def test_unknown_game_lists_supported_ones():
    service = make_service((200, {}))
    result = service.nick("dota", "123")
    assert result["code"] == "unknown_game"
    assert "ff" in result["error"]
    assert service.calls == []          # поставщика не дёргали


def test_missing_id_is_rejected_before_request():
    service = make_service((200, {}))
    assert service.nick("ff", "   ")["code"] == "invalid_request"
    assert service.calls == []


def test_mlbb_requires_server_and_sends_it():
    service = make_service((200, {"valid": True, "player_name": "Player"}))
    assert service.nick("mlbb", "123")["code"] == "server_required"
    assert service.calls == []

    service.nick("mlbb", "123", "2001")
    assert service.calls[0]["payload"]["server_id"] == "2001"


def test_telegram_uses_its_own_endpoint_and_strips_at():
    service = make_service((200, {"valid": True, "name": "Alijon"}))
    result = service.nick("tg", "@alijon", amount=100)
    assert result["nickname"] == "Alijon"
    assert service.calls[0]["url"].endswith("/telegram/check")
    assert service.calls[0]["payload"] == {"username": "alijon", "stars": 100}


def test_network_failure_reports_service_unavailable():
    service = make_service((0, {}))
    result = service.nick("ff", "123456789")
    assert result["code"] == "service_unavailable"


def test_missing_key_is_reported_not_sent():
    service = server.Service(server.Settings(api_key=""), fetch=lambda *a: (200, {}))
    assert service.nick("ff", "123456789")["code"] == "no_key"


def test_result_is_cached_and_supplier_called_once():
    service = make_service((200, {"valid": True, "player_name": "AlijonTJ"}))
    first = service.nick("ff", "123456789")
    second = service.nick("ff", "123456789")
    assert first["cached"] is False and second["cached"] is True
    assert len(service.calls) == 1


def test_failures_are_not_cached():
    service = make_service((200, {"valid": False, "error": {"code": "invalid_uid"}}))
    service.nick("ff", "123456789")
    service.nick("ff", "123456789")
    assert len(service.calls) == 2


def test_cache_can_be_disabled():
    service = make_service((200, {"valid": True, "player_name": "X"}), cache_ttl=0)
    service.nick("ff", "1")
    service.nick("ff", "1")
    assert len(service.calls) == 2


def test_rate_limiter_counts_per_address():
    limiter = server.RateLimiter(2)
    assert limiter.allow("1.1.1.1") and limiter.allow("1.1.1.1")
    assert not limiter.allow("1.1.1.1")
    assert limiter.allow("2.2.2.2")          # чужой адрес не страдает


def test_rate_limit_zero_means_unlimited():
    limiter = server.RateLimiter(0)
    assert all(limiter.allow("1.1.1.1") for _ in range(100))


# ── настройки ─────────────────────────────────────────────────────────
def test_env_file_is_read_without_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        '# комментарий\nSHOP_SUPPLIER_KEY="abc"\nNICK_API_PORT=9001\nмусор\n',
        encoding="utf-8",
    )
    cfg = server.load_settings(tmp_path)
    assert cfg.api_key == "abc"
    assert cfg.port == 9001


def test_environment_wins_over_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("SHOP_SUPPLIER_KEY=fromfile\n", encoding="utf-8")
    monkeypatch.setenv("NICK_API_KEY", "fromenv")
    assert server.load_settings(tmp_path).api_key == "fromenv"


def test_broken_numbers_fall_back_to_defaults(tmp_path):
    (tmp_path / ".env").write_text("NICK_API_PORT=порт\n", encoding="utf-8")
    assert server.load_settings(tmp_path).port == 8081


# ── живой HTTP ────────────────────────────────────────────────────────
@pytest.fixture
def live(request):
    """Поднимает сервис на свободном порту localhost и гасит после теста."""
    service = getattr(request, "param", None) or make_service(
        (200, {"valid": True, "player_name": "AlijonTJ"}))
    handler = type("Bound", (server.Handler,), {"service": service})
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", service
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def fetch(url: str, headers: dict | None = None, data: dict | None = None):
    request = urllib.request.Request(
        url, headers=headers or {},
        data=json.dumps(data).encode() if data is not None else None,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def test_health_answers_without_token(live):
    base, _ = live
    status, body = fetch(f"{base}/health")
    assert status == 200 and body["ok"] is True


def test_get_nick_over_http(live):
    base, _ = live
    status, body = fetch(f"{base}/nick?game=ff&id=123456789")
    assert status == 200
    assert body["nickname"] == "AlijonTJ"


def test_post_nick_over_http(live):
    base, _ = live
    status, body = fetch(f"{base}/nick", data={"game": "ff", "id": "123456789"})
    assert status == 200 and body["nickname"] == "AlijonTJ"


def test_bad_json_body_is_rejected(live):
    base, _ = live
    request = urllib.request.Request(f"{base}/nick", data=b"{not json", method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(request, timeout=5)
    assert exc.value.code == 400


def test_games_endpoint_lists_all(live):
    base, _ = live
    status, body = fetch(f"{base}/games")
    assert status == 200
    assert len(body["games"]) == len(games.GAMES)


def test_unknown_path_is_404(live):
    base, _ = live
    assert fetch(f"{base}/order")[0] == 404


@pytest.mark.parametrize("live", [make_service(
    (200, {"valid": True, "player_name": "AlijonTJ"}), token="secret")], indirect=True)
def test_token_protects_nick_but_not_health(live):
    base, _ = live
    assert fetch(f"{base}/health")[0] == 200
    assert fetch(f"{base}/nick?game=ff&id=1")[0] == 401
    assert fetch(f"{base}/nick?game=ff&id=1", {"X-Api-Key": "wrong"})[0] == 401
    assert fetch(f"{base}/nick?game=ff&id=1", {"X-Api-Key": "secret"})[0] == 200
    assert fetch(f"{base}/nick?game=ff&id=1",
                 {"Authorization": "Bearer secret"})[0] == 200


@pytest.mark.parametrize("live", [make_service(
    (200, {"valid": False, "error": {"code": "invalid_uid"}}))], indirect=True)
def test_invalid_id_answers_404_with_reason(live):
    base, _ = live
    status, body = fetch(f"{base}/nick?game=ff&id=1")
    assert status == 404
    assert body["error"] == "ID игрока неверный"


@pytest.mark.parametrize("live", [make_service((200, {}), rate_limit=1)], indirect=True)
def test_rate_limit_answers_429(live):
    base, _ = live
    fetch(f"{base}/nick?game=ff&id=1")
    assert fetch(f"{base}/nick?game=ff&id=1")[0] == 429


# ── аудит: защита ────────────────────────────────────────────────────
def _handler_from(peer: str, headers: dict):
    handler = type("H", (server.Handler,), {"service": make_service((200, {}))})
    fake = handler.__new__(handler)
    fake.client_address = (peer, 5555)
    fake.headers = headers
    return fake


def test_forged_forwarded_header_does_not_bypass_limit():
    """Снаружи подставной X-Forwarded-For игнорируется — лимит не обойти."""
    assert _handler_from("203.0.113.5", {"X-Forwarded-For": "1.2.3.4"})._who() == "203.0.113.5"


def test_forwarded_header_trusted_from_local_proxy():
    """За nginx на этом же сервере настоящий адрес клиента берётся из заголовка."""
    assert _handler_from("127.0.0.1", {"X-Forwarded-For": "1.2.3.4, 10.0.0.1"})._who() == "1.2.3.4"


def test_options_answers_without_body(live):
    import http.client

    base, _ = live
    host, port = base.replace("http://", "").split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    conn.request("OPTIONS", "/nick")
    resp = conn.getresponse()
    assert resp.status == 204
    assert resp.read() == b""
    # То же соединение продолжает работать — мусора после 204 нет.
    conn.request("GET", "/health")
    assert conn.getresponse().status == 200
    conn.close()


def test_huge_body_is_refused(live):
    base, _ = live
    request = urllib.request.Request(
        f"{base}/nick", data=b"{" + b" " * (server.MAX_BODY + 10) + b"}", method="POST"
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(request, timeout=5)
    assert exc.value.code == 413


def test_access_key_is_not_written_to_log(caplog):
    fake = _handler_from("203.0.113.5", {})
    with caplog.at_level("INFO", logger="nickapi"):
        fake.log_message('"%s" %s', "GET /nick?game=ff&key=supersecret&id=1", "200")
    assert "supersecret" not in caplog.text
    assert "key=***" in caplog.text
