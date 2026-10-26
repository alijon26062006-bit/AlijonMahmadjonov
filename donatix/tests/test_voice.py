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
