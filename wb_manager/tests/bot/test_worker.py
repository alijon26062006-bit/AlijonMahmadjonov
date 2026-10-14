"""Полный цикл: очередь → воркер → проверки → текст → база → уведомление с PDF."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.checks.factory import NOW, feedback, orders, stock
from tests.helpers import make_settings, personal_token
from wbm.analysis.runner import AnalysisDeps
from wbm.bot.texts import run_summary
from wbm.collectors import Collector
from wbm.config import WorkerSettings
from wbm.db import repositories as repo
from wbm.db.models import RunDataset, RunStatus
from wbm.domain.data import DataResult, Dataset
from wbm.security.crypto import TokenCipher
from wbm.wb_client import Category, WBClient
from wbm.worker import Worker

Sessions = async_sessionmaker[AsyncSession]


@dataclass
class FakeNotifier:
    progress_texts: list[str] = field(default_factory=list)
    finished_text: str | None = None
    pdf: bytes = b""
    failed_text: str | None = None

    async def progress(self, chat_id: int, message_id: int | None, text: str) -> None:
        self.progress_texts.append(text)

    async def finished(
        self, chat_id: int, message_id: int | None, text: str, pdf: bytes, filename: str
    ) -> None:
        self.finished_text, self.pdf = text, pdf

    async def failed(self, chat_id: int, message_id: int | None, text: str) -> None:
        self.failed_text = text


def fake_collector(dataset: Dataset, category: Category, rows: list[object]) -> Collector:
    async def collect(client: WBClient, now: datetime, days: int) -> DataResult[object]:
        return DataResult.ok(rows)

    return Collector(dataset, category, dataset.value, collect)


def broken_collector() -> Collector:
    async def collect(client: WBClient, now: datetime, days: int) -> DataResult[object]:
        raise RuntimeError("WB изменил формат")

    return Collector(Dataset.FEEDBACKS, Category.FEEDBACKS, "отзывы", collect)


async def queued_run(sessions: Sessions, cipher: TokenCipher, token: str) -> int:
    async with sessions.begin() as session:
        user = await repo.get_or_create_telegram_user(
            session, telegram_user_id=1, chat_id=1, name="А"
        )
        shop = await repo.create_shop(
            session,
            user_id=user.id,
            name="Платья <Ромашка>",
            token_encrypted=cipher.encrypt(token),
            token_fingerprint="abc",
            token_categories=["statistics", "analytics", "feedbacks"],
        )
        run = await repo.enqueue_run(session, user_id=user.id, shop_id=shop.id, notify_chat_id=1)
        assert run is not None
        return run.id


def worker(
    sessions: Sessions, cipher: TokenCipher, collectors: list[Collector], notifier: FakeNotifier
) -> Worker:
    deps = AnalysisDeps(
        sessionmaker=sessions,
        cipher=cipher,
        wb_settings=make_settings(),
        collectors=collectors,
        clock=lambda: NOW,
    )
    return Worker(deps, WorkerSettings(_env_file=None), notifier, worker_id="test")


async def test_full_analysis_cycle(sessions: Sessions, cipher: TokenCipher) -> None:
    run_id = await queued_run(sessions, cipher, personal_token())
    notifier = FakeNotifier()
    collectors = [
        fake_collector(Dataset.ORDERS, Category.STATISTICS, list(orders(1, 28, days_ago=13))),
        fake_collector(Dataset.STOCKS, Category.ANALYTICS, [stock(1, 0)]),
        fake_collector(Dataset.FEEDBACKS, Category.FEEDBACKS, [feedback(1, 1, "Брак")]),
        fake_collector(Dataset.FINANCE, Category.FINANCE, []),  # нет доступа в токене
    ]

    assert await worker(sessions, cipher, collectors, notifier).process_next("test-0")

    async with sessions() as session:
        run = await repo.load_run_details(session, run_id)
    assert run is not None
    assert run.status == RunStatus.DONE
    assert run.summary is not None
    assert run.summary["report_source"] == "template"
    finding = run.checks[0].findings[0]
    assert finding.text is not None
    assert "Что сделать" in finding.text
    datasets = {d.dataset: d for d in (await _datasets(sessions, run_id))}
    assert datasets["finance"].status == "skipped"
    assert "нет доступа" in (datasets["finance"].message or "")
    assert datasets["campaign_stats"].message is not None

    assert notifier.finished_text is not None
    assert "готов" in notifier.finished_text
    assert "&lt;Ромашка&gt;" in notifier.finished_text  # название экранировано для HTML
    reader = PdfReader(io.BytesIO(notifier.pdf))
    assert "Отчёт об анализе магазина" in reader.pages[0].extract_text()


async def _datasets(sessions: Sessions, run_id: int) -> list[RunDataset]:
    async with sessions() as session:
        run = await repo.get_run(session, 1, run_id)
        assert run is not None
        return list(run.datasets)


async def test_broken_collector_does_not_break_analysis(
    sessions: Sessions, cipher: TokenCipher
) -> None:
    run_id = await queued_run(sessions, cipher, personal_token())
    notifier = FakeNotifier()

    await worker(sessions, cipher, [broken_collector()], notifier).process_next("test-0")

    async with sessions() as session:
        run = await repo.load_run_details(session, run_id)
    assert run is not None
    assert run.status == RunStatus.DONE
    unanswered = next(c for c in run.checks if c.check_id == "unanswered")
    assert unanswered.status == "no_data"
    assert notifier.finished_text is not None


async def test_unreadable_token_fails_run_with_message(
    sessions: Sessions, cipher: TokenCipher
) -> None:
    run_id = await queued_run(sessions, TokenCipher.from_setting(cipher_key()), personal_token())
    notifier = FakeNotifier()

    await worker(sessions, cipher, [], notifier).process_next("test-0")

    async with sessions() as session:
        run = await repo.load_run_details(session, run_id)
    assert run is not None
    assert run.status == RunStatus.FAILED
    assert notifier.failed_text is not None
    assert "токен" in notifier.failed_text


def cipher_key() -> str:
    from wbm.security.crypto import generate_key

    return generate_key()


async def test_empty_queue(sessions: Sessions, cipher: TokenCipher) -> None:
    assert not await worker(sessions, cipher, [], FakeNotifier()).process_next("test-0")


def test_summary_top_five_and_escaping() -> None:
    from wbm.db.models import AnalysisRun, CheckResult, Finding

    findings = [
        Finding(
            severity="advice",
            position=i,
            title=f"Совет {i}",
            products=[],
            facts={},
            reason="r",
            recommendation="<script>",
            text=None,
        )
        for i in range(7)
    ]
    findings.insert(
        0,
        Finding(
            severity="critical",
            position=0,
            title="Главное",
            products=[],
            facts={},
            reason="r",
            recommendation="x",
            text="Срочно",
        ),
    )
    run = AnalysisRun(
        status="done",
        period_days=30,
        summary={"summary_text": "Итог"},
        checks=[
            CheckResult(check_id="a", title="A", status="problems", position=0, findings=findings),
            CheckResult(check_id="b", title="B", status="needs_cost", position=1, message="m"),
        ],
    )

    text = run_summary(run, "Ромашка")

    assert "1. 🔴 <b>Главное</b>" in text
    assert "5." in text
    assert "6." not in text
    assert "<script>" not in text
    assert "/costs" in text
