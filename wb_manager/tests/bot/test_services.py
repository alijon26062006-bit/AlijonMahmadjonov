"""Логика бота: телефон, подключение токена, себестоимость, запуск анализа."""

from __future__ import annotations

import logging

import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.helpers import SELLER_ID, personal_token
from wbm.bot.services import MAX_SHOPS_PER_USER, BotServices, looks_like_token
from wbm.db import repositories as repo
from wbm.db.models import Shop
from wbm.security.crypto import TokenCipher

Sessions = async_sessionmaker[AsyncSession]
PING_OK = {"TS": "2026-10-14T10:00:00+03:00", "Status": "OK"}
SELLER = {"name": "ИП Иванов", "sid": SELLER_ID, "tradeMark": "Платья Ромашка"}


def mock_wb(respx_mock: respx.MockRouter, *, denied: tuple[str, ...] = ()) -> None:
    for host in (
        "common-api",
        "content-api",
        "seller-analytics-api",
        "discounts-prices-api",
        "statistics-api",
        "advert-api",
        "feedbacks-api",
        "finance-api",
        "marketplace-api",
    ):
        url = f"https://{host}.wildberries.ru/ping"
        if host in denied:
            respx_mock.get(url).respond(403)
        else:
            respx_mock.get(url).respond(200, json=PING_OK)
    respx_mock.get("https://common-api.wildberries.ru/api/v1/seller-info").respond(200, json=SELLER)


async def user_with_phone(services: BotServices, telegram_id: int = 111) -> int:
    user = await services.register(telegram_id, telegram_id, "Алижон")
    await services.save_phone(user.id, "+7 (999) 123-45-67")
    return user.id


def test_token_detection() -> None:
    token = personal_token()

    assert looks_like_token(token)
    assert looks_like_token(f"вот токен: {token}")
    assert not looks_like_token("Привет! Как дела?")
    assert not looks_like_token("/analyze")


async def test_register_is_idempotent_and_phone_normalized(
    services: BotServices, sessions: Sessions
) -> None:
    first = await services.register(111, 111, "Алижон")
    again = await services.register(111, 222, None)
    await services.save_phone(first.id, "+7 (999) 123-45-67")

    async with sessions() as session:
        user = await repo.get_user_by_telegram(session, 111)
    assert first.id == again.id
    assert user is not None
    assert user.phone == "+79991234567"
    assert user.telegram_chat_id == 222
    assert user.name == "Алижон"


async def test_connect_token_saves_encrypted_shop(
    services: BotServices,
    sessions: Sessions,
    cipher: TokenCipher,
    respx_mock: respx.MockRouter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_wb(respx_mock, denied=("marketplace-api", "finance-api"))
    user_id = await user_with_phone(services)
    user = await services.register(111, 111, None)
    token = personal_token()

    with caplog.at_level(logging.DEBUG):
        result = await services.connect_token(user, f"Bearer {token}")

    assert result.ok, result.message
    assert result.shop_name == "Платья Ромашка"
    assert "finance" not in result.available
    assert "content" in result.available
    async with sessions() as session:
        shops = await repo.list_shops(session, user_id)
    assert len(shops) == 1
    stored: Shop = shops[0]
    assert stored.seller_id == SELLER_ID
    assert token not in stored.token_encrypted
    assert cipher.decrypt(stored.token_encrypted) == token
    assert token not in caplog.text


async def test_same_seller_token_updates_shop(
    services: BotServices, sessions: Sessions, respx_mock: respx.MockRouter
) -> None:
    mock_wb(respx_mock)
    await user_with_phone(services)
    user = await services.register(111, 111, None)

    first = await services.connect_token(user, personal_token())
    second = await services.connect_token(user, personal_token(id="другой-токен"))

    assert first.ok
    assert second.ok
    assert second.updated
    assert first.shop_id == second.shop_id


async def test_rejected_and_malformed_tokens(
    services: BotServices, sessions: Sessions, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(url__regex=r"https://.*\.wildberries\.ru/ping").respond(401)
    user_id = await user_with_phone(services)
    user = await services.register(111, 111, None)

    rejected = await services.connect_token(user, personal_token())
    malformed = await services.connect_token(user, "eyJ abc")

    assert not rejected.ok
    assert "не принял токен" in rejected.message
    assert not malformed.ok
    async with sessions() as session:
        assert await repo.list_shops(session, user_id) == []


async def test_shop_limit(
    services: BotServices, sessions: Sessions, respx_mock: respx.MockRouter
) -> None:
    mock_wb(respx_mock)
    user_id = await user_with_phone(services)
    user = await services.register(111, 111, None)
    async with sessions.begin() as session:
        for n in range(MAX_SHOPS_PER_USER):
            await repo.create_shop(
                session,
                user_id=user_id,
                name=f"М{n}",
                seller_id=f"s{n}",
                token_encrypted="x",
                token_fingerprint="y",
            )

    result = await services.connect_token(user, personal_token())

    assert not result.ok
    assert "не больше" in result.message


async def test_costs_and_analysis_are_scoped_to_owner(
    services: BotServices, sessions: Sessions
) -> None:
    owner = await user_with_phone(services, 111)
    stranger = await user_with_phone(services, 222)
    async with sessions.begin() as session:
        shop = await repo.create_shop(
            session, user_id=owner, name="М", token_encrypted="x", token_fingerprint="y"
        )
        shop_id = shop.id

    denied = await services.save_costs(stranger, shop_id, "c.csv", b"A;100\n")
    saved = await services.save_costs(owner, shop_id, "c.csv", b"A;100\nB;x\n")

    assert not denied.ok
    assert saved.ok
    assert saved.saved == 1
    assert len(saved.errors) == 1

    assert await services.start_analysis(stranger, shop_id, 1) == (None, False)
    run, is_new = await services.start_analysis(owner, shop_id, 1)
    assert run is not None
    assert is_new
    await services.remember_progress_message(run.id, 42)
    again, again_new = await services.start_analysis(owner, shop_id, 1)
    assert again is not None
    assert again.id == run.id
    assert not again_new
    assert await services.report_pdf(owner, run.id) is None  # ещё не готов
