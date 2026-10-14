"""Результаты проверок сохраняются в базу и читаются обратно без потерь."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.checks.factory import NOW, bundle, feedback, orders, stock
from wbm.analysis.persist import check_records, dataset_records, summary
from wbm.checks import run_checks
from wbm.db import repositories as repo
from wbm.domain.data import DataResult


async def test_outcomes_roundtrip(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    data = bundle(
        orders=orders(1, 28, days_ago=13),
        stocks=[stock(1, 0)],
        feedbacks=[feedback(1, 1, "Брак")],
        finance=DataResult.error("WB ответил HTTP 503"),
    )
    outcomes = run_checks(data)

    async with sessionmaker.begin() as session:
        user = await repo.create_user(session, "a@b.ru", "hash")
        shop = await repo.create_shop(
            session, user_id=user.id, name="М", token_encrypted="x", token_fingerprint="y"
        )
        await repo.enqueue_run(session, user_id=user.id, shop_id=shop.id)
        run = await repo.claim_next_run(session, "w", now=NOW)
        assert run is not None
        assert await repo.finish_run(
            session,
            run.id,
            "w",
            datasets=dataset_records(data),
            checks=check_records(outcomes),
            summary=summary(outcomes),
        )

    async with sessionmaker() as session:
        loaded = await repo.get_run(session, user.id, run.id)
    assert loaded is not None
    assert [c.check_id for c in loaded.checks] == [o.check_id for o in outcomes]
    stock_out = loaded.checks[0]
    assert stock_out.status == "problems"
    finding = stock_out.findings[0]
    assert finding.severity == "critical"
    assert finding.products[0]["metrics"]["остаток_шт"] == 0
    datasets = {d.dataset: d for d in loaded.datasets}
    assert datasets["orders"].rows == 28
    assert datasets["finance"].status == "error"
    assert loaded.summary is not None
    assert loaded.summary["worst"] == "critical"
    assert "deductions" in loaded.summary["checks_without_data"]
