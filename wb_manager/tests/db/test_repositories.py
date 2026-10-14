from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wbm.db import repositories as repo
from wbm.db.base import UTCDateTime
from wbm.db.models import (
    AnalysisRun,
    CheckResult,
    CheckStatus,
    DatasetStatus,
    Finding,
    RunDataset,
    RunSource,
    RunStatus,
    Severity,
    Shop,
)

Sessions = async_sessionmaker[AsyncSession]
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


async def make_user(sessions: Sessions, email: str = "seller@example.com") -> int:
    async with sessions.begin() as session:
        user = await repo.create_user(session, email, "argon2-hash")
        return user.id


async def make_shop(sessions: Sessions, user_id: int, name: str = "Магазин") -> int:
    """Каждому имени — свой ID продавца WB: один продавец не подключается дважды."""
    async with sessions.begin() as session:
        shop = await repo.create_shop(
            session,
            user_id=user_id,
            name=name,
            token_encrypted="gAAAA-зашифровано",
            token_fingerprint="abc123def456",
            seller_id=f"seller-{name}",
            token_kind=3,
            token_expires_at=NOW + timedelta(days=180),
            token_categories=["content", "statistics"],
        )
        return shop.id


# ── пользователи и вход ───────────────────────────────────────────────────────


async def test_user_email_is_normalized_and_unique(sessionmaker: Sessions) -> None:
    await make_user(sessionmaker, "  Seller@Example.COM ")

    async with sessionmaker() as session:
        user = await repo.get_user_by_email(session, "seller@example.com")
    assert user is not None
    assert user.email == "seller@example.com"
    assert user.is_active

    with pytest.raises(repo.EmailTakenError):
        await make_user(sessionmaker, "SELLER@example.com")


async def test_failed_logins_are_counted_by_email_and_ip(sessionmaker: Sessions) -> None:
    async with sessionmaker.begin() as session:
        for _ in range(3):
            await repo.record_login_attempt(session, email="a@b.ru", ip="1.1.1.1", success=False)
        await repo.record_login_attempt(session, email="a@b.ru", ip="1.1.1.1", success=True)
        await repo.record_login_attempt(session, email="c@d.ru", ip="1.1.1.1", success=False)

    since = datetime.now(UTC) - timedelta(minutes=15)
    async with sessionmaker() as session:
        assert await repo.count_failed_logins(session, since=since, email="A@B.ru") == 3
        assert await repo.count_failed_logins(session, since=since, ip="1.1.1.1") == 4
        future = datetime.now(UTC) + timedelta(minutes=1)
        assert await repo.count_failed_logins(session, since=future, ip="1.1.1.1") == 0
        with pytest.raises(ValueError, match="email или ip"):
            await repo.count_failed_logins(session, since=since)


# ── магазины: каждый видит только свои ────────────────────────────────────────


async def test_seller_sees_only_own_shops(sessionmaker: Sessions) -> None:
    alice = await make_user(sessionmaker, "alice@example.com")
    bob = await make_user(sessionmaker, "bob@example.com")
    shop_id = await make_shop(sessionmaker, alice)

    async with sessionmaker() as session:
        shop = await repo.get_shop(session, alice, shop_id)
        assert shop is not None
        assert shop.token_categories == ["content", "statistics"]
        assert shop.token_expires_at == NOW + timedelta(days=180)
        assert await repo.get_shop(session, bob, shop_id) is None
        assert await repo.list_shops(session, bob) == []
        assert [s.id for s in await repo.list_shops(session, alice)] == [shop_id]

    async with sessionmaker.begin() as session:
        assert not await repo.delete_shop(session, bob, shop_id)
    async with sessionmaker() as session:
        assert await repo.get_shop(session, alice, shop_id) is not None


async def test_cost_prices_are_replaced_by_new_file(sessionmaker: Sessions) -> None:
    shop_id = await make_shop(sessionmaker, await make_user(sessionmaker))

    async with sessionmaker.begin() as session:
        await repo.replace_cost_prices(
            session, shop_id, {"ART-1": Decimal("150.50"), "ART-2": Decimal("99")}
        )
    async with sessionmaker.begin() as session:
        count = await repo.replace_cost_prices(session, shop_id, {"ART-3": Decimal("1200.99")})

    async with sessionmaker() as session:
        prices = await repo.get_cost_prices(session, shop_id)
    assert count == 1
    assert prices == {"ART-3": Decimal("1200.99")}


# ── очередь анализов ──────────────────────────────────────────────────────────


async def test_enqueue_checks_owner_and_reuses_active_run(sessionmaker: Sessions) -> None:
    alice = await make_user(sessionmaker, "alice@example.com")
    bob = await make_user(sessionmaker, "bob@example.com")
    shop_id = await make_shop(sessionmaker, alice)

    async with sessionmaker.begin() as session:
        assert await repo.enqueue_run(session, user_id=bob, shop_id=shop_id) is None
        first = await repo.enqueue_run(
            session, user_id=alice, shop_id=shop_id, source=RunSource.TELEGRAM
        )
        assert first is not None
        again = await repo.enqueue_run(session, user_id=alice, shop_id=shop_id)
        assert again is not None
        assert again.id == first.id
        assert first.status == RunStatus.QUEUED
        assert first.source == RunSource.TELEGRAM


async def test_worker_takes_runs_in_order(sessionmaker: Sessions) -> None:
    user = await make_user(sessionmaker)
    shop_a = await make_shop(sessionmaker, user, "A")
    shop_b = await make_shop(sessionmaker, user, "B")
    async with sessionmaker.begin() as session:
        run_a = await repo.enqueue_run(session, user_id=user, shop_id=shop_a)
    async with sessionmaker.begin() as session:
        run_b = await repo.enqueue_run(session, user_id=user, shop_id=shop_b)
    assert run_a is not None
    assert run_b is not None

    async with sessionmaker.begin() as session:
        claimed = await repo.claim_next_run(session, "worker-1", now=NOW)
        assert claimed is not None
        assert claimed.id == run_a.id
        assert claimed.status == RunStatus.RUNNING
        assert claimed.attempts == 1
        assert claimed.started_at == NOW
    async with sessionmaker.begin() as session:
        second = await repo.claim_next_run(session, "worker-2", now=NOW)
        assert second is not None
        assert second.id == run_b.id
    async with sessionmaker.begin() as session:
        assert await repo.claim_next_run(session, "worker-1") is None


async def test_progress_only_from_owning_worker(sessionmaker: Sessions) -> None:
    user = await make_user(sessionmaker)
    shop_id = await make_shop(sessionmaker, user)
    async with sessionmaker.begin() as session:
        await repo.enqueue_run(session, user_id=user, shop_id=shop_id)
        run = await repo.claim_next_run(session, "worker-1", now=NOW)
        assert run is not None
        run_id = run.id

    async with sessionmaker.begin() as session:
        assert not await repo.report_progress(
            session, run_id, "worker-2", progress=50, stage="Отзывы"
        )
        assert await repo.report_progress(
            session, run_id, "worker-1", progress=150, stage="Загрузка отзывов", now=NOW
        )
    async with sessionmaker() as session:
        stored = await session.get(AnalysisRun, run_id)
        assert stored is not None
        assert stored.progress == 100
        assert stored.stage == "Загрузка отзывов"


async def test_finished_run_with_results_visible_only_to_owner(sessionmaker: Sessions) -> None:
    alice = await make_user(sessionmaker, "alice@example.com")
    bob = await make_user(sessionmaker, "bob@example.com")
    shop_id = await make_shop(sessionmaker, alice)
    async with sessionmaker.begin() as session:
        await repo.enqueue_run(session, user_id=alice, shop_id=shop_id)
        run = await repo.claim_next_run(session, "w", now=NOW)
        assert run is not None
        run_id = run.id

    finding = Finding(
        severity=Severity.CRITICAL,
        position=0,
        title="Закончится через 3 дня",
        products=[{"nm_id": 123456, "vendor_code": "ART-1", "name": "Платье"}],
        facts={"остаток": 12, "заказов_в_день": 4.0, "дней_запаса": 3.0},
        reason="Заказывают 4 шт. в день, на складе 12 шт.",
        recommendation="Отгрузите поставку в ближайшие дни",
    )
    checks = [
        CheckResult(
            check_id="stock_out",
            title="Товар закончится",
            status=CheckStatus.PROBLEMS,
            position=0,
            findings=[finding],
        ),
        CheckResult(
            check_id="unit_economics",
            title="Продажи в минус",
            status=CheckStatus.NEEDS_COST,
            position=1,
            message="Загрузите себестоимость",
        ),
    ]
    datasets = [
        RunDataset(dataset="stocks", status=DatasetStatus.OK, rows=120),
        RunDataset(dataset="adverts", status=DatasetStatus.ERROR, rows=0, message="HTTP 403"),
    ]
    async with sessionmaker.begin() as session:
        assert await repo.finish_run(
            session,
            run_id,
            "w",
            datasets=datasets,
            checks=checks,
            summary={"critical": 1},
            report_text="Итог: 1 критичная проблема",
            now=NOW,
        )

    async with sessionmaker() as session:
        assert await repo.get_run(session, bob, run_id) is None
        loaded = await repo.get_run(session, alice, run_id)
    assert loaded is not None
    assert loaded.status == RunStatus.DONE
    assert loaded.progress == 100
    assert loaded.finished_at == NOW
    assert [c.check_id for c in loaded.checks] == ["stock_out", "unit_economics"]
    stored = loaded.checks[0].findings[0]
    assert stored.products[0]["name"] == "Платье"
    assert stored.facts["дней_запаса"] == 3.0
    assert {d.dataset: d.status for d in loaded.datasets} == {"stocks": "ok", "adverts": "error"}

    async with sessionmaker() as session:
        runs = await repo.list_runs(session, alice, shop_id)
        assert [r.id for r in runs] == [run_id]
        assert await repo.list_runs(session, bob, shop_id) == []


async def test_failed_run_and_new_run_after_it(sessionmaker: Sessions) -> None:
    user = await make_user(sessionmaker)
    shop_id = await make_shop(sessionmaker, user)
    async with sessionmaker.begin() as session:
        await repo.enqueue_run(session, user_id=user, shop_id=shop_id)
        run = await repo.claim_next_run(session, "w")
        assert run is not None
        assert await repo.fail_run(session, run.id, "w", error="WB недоступен")
        assert not await repo.fail_run(session, run.id, "w", error="повтор")
        fresh = await repo.enqueue_run(session, user_id=user, shop_id=shop_id)
        assert fresh is not None
        assert fresh.id != run.id


async def test_stale_runs_are_requeued_then_failed(sessionmaker: Sessions) -> None:
    user = await make_user(sessionmaker)
    shop_id = await make_shop(sessionmaker, user)
    async with sessionmaker.begin() as session:
        queued = await repo.enqueue_run(session, user_id=user, shop_id=shop_id)
        assert queued is not None
        run_id = queued.id

    for attempt in range(1, 4):
        async with sessionmaker.begin() as session:
            run = await repo.claim_next_run(session, f"w{attempt}", now=NOW)
            assert run is not None
            assert run.id == run_id
            assert run.attempts == attempt
        async with sessionmaker.begin() as session:
            moved = await repo.requeue_stale_runs(
                session, stale_before=NOW + timedelta(minutes=5), max_attempts=3
            )
            assert moved == 1

    async with sessionmaker() as session:
        stored = await session.get(AnalysisRun, run_id)
    assert stored is not None
    assert stored.status == RunStatus.FAILED
    assert stored.error is not None


async def test_deleting_shop_removes_its_runs_and_results(sessionmaker: Sessions) -> None:
    user = await make_user(sessionmaker)
    shop_id = await make_shop(sessionmaker, user)
    async with sessionmaker.begin() as session:
        await repo.enqueue_run(session, user_id=user, shop_id=shop_id)
        run = await repo.claim_next_run(session, "w")
        assert run is not None
        check = CheckResult(check_id="x", title="X", status=CheckStatus.OK, position=0)
        await repo.finish_run(session, run.id, "w", datasets=[], checks=[check])

    async with sessionmaker.begin() as session:
        assert await repo.delete_shop(session, user, shop_id)

    async with sessionmaker() as session:
        for model in (Shop, AnalysisRun, CheckResult):
            count = (await session.execute(select(func.count()).select_from(model))).scalar_one()
            assert count == 0, model.__name__


def test_naive_datetime_is_rejected() -> None:
    naive = datetime(2027, 1, 1)

    with pytest.raises(ValueError, match="часового пояса"):
        UTCDateTime().process_bind_param(naive, sqlite.dialect())


async def test_same_wb_seller_cannot_be_added_twice(sessionmaker: Sessions) -> None:
    user = await make_user(sessionmaker)
    await make_shop(sessionmaker, user, "A")

    with pytest.raises(IntegrityError):
        await make_shop(sessionmaker, user, "A")
