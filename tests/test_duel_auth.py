"""Подпись Telegram: своё пропускаем, чужое и подделанное — нет."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from duel.auth import AuthError, WebAppUser, authenticate, check_init_data, parse_user

TOKEN = "123456:TEST-TOKEN"


def make_init_data(token=TOKEN, user_id=42, name="Алиджон", auth_date=None, **extra):
    """Собирает initData ровно так, как это делает Telegram."""
    fields = {
        "user": json.dumps(
            {"id": user_id, "first_name": name, "username": "alijon"},
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        "auth_date": str(int(auth_date if auth_date is not None else time.time())),
        "query_id": "AAA",
        **extra,
    }
    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_valid_signature_passes():
    fields = check_init_data(make_init_data(), TOKEN)
    assert json.loads(fields["user"])["id"] == 42


def test_signature_from_another_bot_is_rejected():
    with pytest.raises(AuthError):
        check_init_data(make_init_data(token="999:OTHER"), TOKEN)


def test_tampered_user_id_is_rejected():
    """Подменить id в подписанной строке нельзя — это главная защита."""
    raw = make_init_data(user_id=42)
    forged = raw.replace("42", "43")
    with pytest.raises(AuthError):
        check_init_data(forged, TOKEN)


def test_missing_hash_is_rejected():
    with pytest.raises(AuthError):
        check_init_data("user=%7B%7D&auth_date=1", TOKEN)


def test_empty_init_data_is_rejected():
    with pytest.raises(AuthError):
        check_init_data("", TOKEN)


def test_stale_signature_is_rejected():
    old = make_init_data(auth_date=time.time() - 90_000)
    with pytest.raises(AuthError):
        check_init_data(old, TOKEN)


def test_fresh_signature_within_the_window_passes():
    recent = make_init_data(auth_date=time.time() - 60)
    assert check_init_data(recent, TOKEN)


def test_user_is_parsed():
    user = parse_user(check_init_data(make_init_data(), TOKEN))
    assert user.id == 42 and user.username == "alijon"
    assert user.name == "Алиджон"


def test_room_code_travels_in_start_param():
    data = make_init_data(start_param="ABC123")
    user = parse_user(check_init_data(data, TOKEN))
    assert user.start_param == "ABC123"


def test_name_falls_back_when_telegram_gave_nothing():
    assert WebAppUser(id=7, first_name="").name == "Игрок 7"


def test_dev_mode_only_helps_when_there_is_no_init_data():
    fallback = WebAppUser(id=1, first_name="Отладка")
    assert authenticate("", TOKEN, dev_mode=True, dev_fallback=fallback).id == 1
    with pytest.raises(AuthError):
        authenticate("мусор", TOKEN, dev_mode=True, dev_fallback=fallback)


def test_dev_mode_off_means_no_shortcuts():
    with pytest.raises(AuthError):
        authenticate("", TOKEN, dev_mode=False)
