"""Голосовой помощник админки: голос → текст → ответ (с живыми цифрами) → голос; только для админа."""
import base64
import json

import httpx
from conftest import make_client, web_login
from fastapi.testclient import TestClient

from donatix import voice


def _openai(calls, reply="Сегодня продано на 12 долларов."):
    """Подставной OpenAI: распознаёт фразу, первый раз просит цифры (инструмент), потом отвечает."""
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if req.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": "Сколько продали сегодня?"})
        if req.url.path.endswith("/chat/completions"):
            body = json.loads(req.content)
            if not any(m.get("role") == "tool" for m in body["messages"]):
                return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "shop_summary", "arguments": '{"period": "today"}'}},
                    {"id": "c2", "type": "function", "function": {"name": "open_page", "arguments": '{"page": "заказы"}'}}]}}]})
            tool = next(m for m in body["messages"] if m.get("role") == "tool")
            assert "sales" in json.loads(tool["content"])                     # цифры пришли из базы
            return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})
        if req.url.path.endswith("/audio/speech"):
            return httpx.Response(200, content=b"ID3fake-mp3")
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def test_voice_turn_uses_live_numbers_and_answers_with_audio(conn, config, monkeypatch):
    monkeypatch.setattr(config, "openai_api_key", "sk-test")
    calls = []
    out = voice.ask(conn, config, audio=b"webm-bytes", filename="voice.webm", transport=_openai(calls))
    assert out["ok"] and out["heard"] == "Сколько продали сегодня?" and "долларов" in out["reply"]
    assert base64.b64decode(out["audio"]) == b"ID3fake-mp3" and out["go"] == "/admin/orders"
    assert calls == ["/v1/audio/transcriptions", "/v1/chat/completions", "/v1/chat/completions", "/v1/audio/speech"]


def test_voice_typed_question_and_friendly_errors(conn, config, monkeypatch):
    monkeypatch.setattr(config, "openai_api_key", "sk-test")
    calls = []
    out = voice.ask(conn, config, text="Сколько продали?", transport=_openai(calls))
    assert out["ok"] and "/v1/audio/transcriptions" not in calls              # написали — распознавать нечего
    bad = httpx.MockTransport(lambda req: httpx.Response(401, json={"error": "bad key"}))
    out = voice.ask(conn, config, text="привет", transport=bad)
    assert not out["ok"] and "Ключ OpenAI" in out["error"]
    assert voice.ask(conn, config, audio=b"", text="")["silent"]


def test_tools_read_only_data(conn, config):
    uid, _ = make_client(conn, login="voicefan")
    assert voice.find_client(conn, config, "voicefan")["clients"][0]["login"] == "voicefan"
    assert voice.pending(conn, config)["payments"] == []
    s = voice.shop_summary(conn, config, "30d")
    assert "net_profit" in s and "waiting" in s
    assert voice.run_tool(conn, config, "open_page", {"page": "баннеры"})[1] == "/admin/banners"
    assert "error" in voice.run_tool(conn, config, "delete_everything", {})[0]   # чего нет — того не сделает


def test_endpoint_admin_only_and_needs_key(app, conn, config, monkeypatch):
    from conftest import csrf_of
    anon = TestClient(app)
    assert anon.post("/admin/assistant/ask", data={"text": "привет"}, follow_redirects=False).status_code in (302, 303, 401, 403)
    a = TestClient(app)
    web_login(a, "admin@example.com", "adminpass123")
    token = csrf_of(a.get("/admin").text)
    monkeypatch.setattr(config, "openai_api_key", "")
    r = a.post("/admin/assistant/ask", data={"csrf": token, "text": "привет"})
    assert r.status_code == 503 and "openai.sh" in r.json()["error"]
    monkeypatch.setattr(config, "openai_api_key", "sk-test")
    seen = {}
    monkeypatch.setattr(voice, "ask", lambda conn, config, **kw: seen.update(kw) or {"ok": True, "heard": "x", "reply": "y",
                                                                                     "audio": None, "go": None})
    r = a.post("/admin/assistant/ask", data={"csrf": token, "history": '[{"role": "user", "text": "раньше"}]', "page": "/admin"},
               files={"audio": ("voice.mp4", b"abc", "audio/mp4")})
    assert r.status_code == 200 and seen["filename"] == "voice.mp4" and seen["audio"] == b"abc"
    assert seen["history"][0]["text"] == "раньше"
    page = a.get("/admin").text
    assert 'data-voice' in page and 'id="vo"' in page and "admin-voice.js" in page
    buyer = TestClient(app)
    make_client(conn, login="nobody")
    web_login(buyer, "nobody@example.com", "password123")
    assert "admin-voice.js" not in buyer.get("/panel").text                   # у клиентов помощника нет


def test_realtime_key_like_chatgpt_voice_with_fallbacks(config, monkeypatch):
    """Голосовой режим (как в ChatGPT): одноразовый ключ с голосом marin, инструментами и инструкциями;
    не приняли полные настройки — простые; новый адрес недоступен — старый (бета)."""
    monkeypatch.setattr(config, "openai_api_key", "sk-test")
    seen = []

    def ok(req):
        seen.append((req.url.path, json.loads(req.content)))
        return httpx.Response(200, json={"value": "ek_123", "expires_at": 1})
    out = voice.realtime_session(config, transport=httpx.MockTransport(ok))
    assert out == {"ok": True, "key": "ek_123", "model": "gpt-realtime", "mode": "ga"}
    path, body = seen[0]
    assert path == "/v1/realtime/client_secrets"
    s = body["session"]
    assert s["audio"]["output"]["voice"] == "marin" and s["model"] == "gpt-realtime"
    assert {t["name"] for t in s["tools"]} >= {"shop_summary", "open_page"} and "function" not in s["tools"][0]
    assert "Donatix" in s["instructions"]

    calls = []

    def picky(req):
        calls.append(req.url.path)
        body = json.loads(req.content)
        if req.url.path.endswith("/client_secrets") and "turn_detection" in json.dumps(body):
            return httpx.Response(400, json={"error": {"message": "Unknown parameter"}})
        return httpx.Response(200, json={"value": "ek_simple"})
    assert voice.realtime_session(config, transport=httpx.MockTransport(picky))["key"] == "ek_simple"

    def old(req):
        if req.url.path.endswith("/client_secrets"):
            return httpx.Response(404, json={"error": "not found"})
        assert req.headers["OpenAI-Beta"] == "realtime=v1"
        return httpx.Response(200, json={"client_secret": {"value": "ek_beta"}})
    out = voice.realtime_session(config, transport=httpx.MockTransport(old))
    assert out["key"] == "ek_beta" and out["mode"] == "beta"
    bad = voice.realtime_session(config, transport=httpx.MockTransport(lambda r: httpx.Response(401, json={})))
    assert not bad["ok"] and "Ключ OpenAI" in bad["error"]


def test_speak_falls_back_to_classic_voice(config, monkeypatch):
    monkeypatch.setattr(config, "openai_api_key", "sk-test")
    tried = []

    def handler(req):
        body = json.loads(req.content)
        tried.append((body["model"], body["voice"]))
        if body["voice"] == "marin":
            return httpx.Response(400, json={"error": {"message": "Invalid voice"}})
        return httpx.Response(200, content=b"mp3")
    assert voice.speak(config, "Привет", transport=httpx.MockTransport(handler)) == b"mp3"
    assert tried == [("gpt-4o-mini-tts", "marin"), ("gpt-4o-mini-tts", "coral")]


def test_realtime_and_tool_endpoints_admin_only(app, conn, config, monkeypatch):
    from conftest import csrf_of
    a = TestClient(app)
    web_login(a, "admin@example.com", "adminpass123")
    token = csrf_of(a.get("/admin").text)
    monkeypatch.setattr(config, "openai_api_key", "sk-test")
    monkeypatch.setattr(voice, "realtime_session", lambda cfg: {"ok": True, "key": "ek_1", "model": "gpt-realtime", "mode": "ga"})
    assert a.post("/admin/assistant/realtime", data={"csrf": token}).json()["key"] == "ek_1"
    r = a.post("/admin/assistant/tool", data={"csrf": token, "name": "open_page", "args": '{"page": "клиенты"}'}).json()
    assert r["go"] == "/admin/users"
    r = a.post("/admin/assistant/tool", data={"csrf": token, "name": "shop_summary", "args": '{"period": "today"}'}).json()
    assert "sales" in r["output"]
    anon = TestClient(app)
    assert anon.post("/admin/assistant/tool", data={"name": "pending"}, follow_redirects=False).status_code in (302, 303, 401, 403)
