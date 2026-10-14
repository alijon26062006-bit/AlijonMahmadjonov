"""Сборка зависимостей для запуска бота и воркера из настроек окружения."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from wbm.config import (
    WBSettings,
    get_app_settings,
    get_database_settings,
    get_report_settings,
    get_security_settings,
    get_telegram_settings,
    get_wb_settings,
)
from wbm.db.session import make_engine, make_sessionmaker
from wbm.logging_setup import SecretRedactingFilter, configure_logging
from wbm.report import ClaudeReportWriter, ReportWriter
from wbm.security.crypto import TokenCipher


@dataclass(slots=True)
class App:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    cipher: TokenCipher
    wb_settings: WBSettings
    report_writer: ReportWriter | None
    telegram_token: str
    redactor: SecretRedactingFilter


def build_app() -> App:
    database = get_database_settings().database_url.get_secret_value()
    fernet = get_security_settings().fernet_keys.get_secret_value()
    telegram = get_telegram_settings().telegram_bot_token.get_secret_value()
    report = get_report_settings()
    api_key = report.anthropic_api_key.get_secret_value() if report.anthropic_api_key else ""

    secrets = [database, telegram, api_key, *fernet.split(",")]
    redactor = configure_logging(get_app_settings().log_level, secrets=[s for s in secrets if s])

    engine = make_engine(database)
    writer: ReportWriter | None = None
    if api_key:
        writer = ClaudeReportWriter.from_api_key(
            api_key,
            model=report.anthropic_model,
            effort=report.anthropic_effort,
            timeout=report.anthropic_timeout,
        )
    return App(
        engine=engine,
        sessionmaker=make_sessionmaker(engine),
        cipher=TokenCipher.from_setting(fernet),
        wb_settings=get_wb_settings(),
        report_writer=writer,
        telegram_token=telegram,
        redactor=redactor,
    )
