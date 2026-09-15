"""Что делать с разобранным уведомлением банка.

Порядок шагов выбран так, чтобы одно зачисление не могло закрыть две
заявки и чтобы одно и то же уведомление не сработало дважды:

  1. Уведомление записывается в bank_payments — ДО всякой работы с
     деньгами. Повтор упирается в уникальный индекс и до денег не
     доходит. Проверять отдельным SELECT нельзя: два сообщения подряд
     успевают проскочить между проверкой и вставкой.

  2. Разбор. Не разобралось — платёж остаётся владельцу на руки, и
     никакие деньги не двигаются.

  3. Поиск заявок ровно на эту сумму. Сравнение целыми числами в
     дирамах — точное.

  4. Ровно одна заявка — зачисляем. Несколько — НЕ выбираем наугад:
     владелец решит сам, кто из двоих платил. Ни одной — платёж
     остаётся неопознанным.

Само зачисление делает та же функция, что и кнопка в панели. Свой
второй путь начисления денег разошёлся бы с первым при первой правке:
кто-то поправил бы реферальный процент в одном месте и забыл в другом.
"""
from __future__ import annotations

from dataclasses import dataclass

from app import db
from app.money import fmt
from app.userbot import parser
from app.userbot.log import get

log = get()

#: Кем помечаются заявки, закрытые юзерботом. Ноль — не человек.
ROBOT = 0


@dataclass
class Result:
    """Чем кончилась обработка одного уведомления."""
    status: str
    amount: int = 0
    deposit_id: int | None = None
    note: str = ""

    @property
    def confirmed(self) -> bool:
        return self.status == db.BANK_MATCHED


async def handle(
    conn, bot, *, source: str, message_id: int, text: str,
) -> Result:
    """Обработать одно уведомление банка. Возвращает, чем кончилось."""
    notice = parser.parse(text)
    body = parser.safe_body(text)

    # Записываем ВСЁ, включая неразобранное: владелец должен видеть, что
    # уведомление приходило, даже если бот его не понял.
    payment = await db.claim_bank_payment(
        conn, source=source, message_id=message_id,
        op_code=notice.op_code, amount=notice.amount, sender=notice.sender,
        card_tail=notice.card_tail, bank_time=notice.bank_time,
        status=db.BANK_FAILED, note=notice.error, body=body,
    )
    if payment is None:
        log.info("%s Duplicate ignored — сообщение %s уже обрабатывали",
                 "[USERBOT]", message_id)
        return Result(status="duplicate", note="повтор")

    if not notice.ok:
        log.warning("[USERBOT] Parser error — %s (сообщение %s)",
                    notice.error, message_id)
        await _tell_owner(
            bot,
            "🚫 <b>Уведомление банка не разобрал</b>\n"
            f"<blockquote>{notice.error}</blockquote>\n\n"
            "<i>Деньги не зачислены. Проверьте заявку руками: "
            "/panel → 📥 Заявки.</i>",
        )
        return Result(status=db.BANK_FAILED, note=notice.error)

    log.info("[USERBOT] Payment detected")
    log.info("[USERBOT] Amount: %s", fmt(notice.amount))
    if notice.op_code:
        log.info("[USERBOT] Operation code: %s", notice.op_code)
    log.info("[USERBOT] Matching order...")

    waiting = await db.pending_deposits_for(conn, notice.amount)

    if len(waiting) == 1:
        return await _confirm(conn, bot, payment, waiting[0], notice)

    if len(waiting) > 1:
        return await _ambiguous(conn, bot, payment, waiting, notice)

    return await _unknown(conn, bot, payment, notice)


async def _confirm(conn, bot, payment, deposit, notice) -> Result:
    """Ровно одна подходящая заявка — закрываем её."""
    from app.handlers.admin import _resolve_deposit

    report = await _resolve_deposit(conn, bot, deposit.id, ROBOT, approved=True)
    fresh = await db.get_deposit(conn, deposit.id)

    if fresh is None or fresh.status != db.DEP_APPROVED:
        # Кто-то успел раньше — владелец руками или второй процесс.
        # Деньги уже зачислены им, второй раз не начисляем.
        log.warning("[USERBOT] Заявку %s закрыли раньше нас — не трогаем",
                    deposit.id)
        await db.close_bank_payment(
            conn, payment.id, status=db.BANK_AMBIGUOUS,
            note="заявку закрыли раньше",
        )
        return Result(status=db.BANK_AMBIGUOUS, amount=notice.amount,
                      note="заявку закрыли раньше")

    await db.close_bank_payment(
        conn, payment.id, status=db.BANK_MATCHED, deposit_id=deposit.id,
        note=f"из поля {notice.source_field}",
    )
    log.info("[USERBOT] Payment confirmed: %s", deposit.id)
    await _tell_owner(
        bot,
        "💳 <b>Оплата подтверждена автоматически</b>\n"
        f"├ Заявка: <code>№{deposit.id}</code>\n"
        f"├ Сумма: <b>{fmt(notice.amount)}</b>\n"
        f"├ Клиент: <code>{deposit.user_id}</code>\n"
        + (f"├ Отправитель: <code>{notice.sender}</code>\n"
           if notice.sender else "")
        + (f"├ Код банка: <code>{notice.op_code}</code>\n"
           if notice.op_code else "")
        + f"└ {notice.bank_time or 'время не указано'}",
    )
    return Result(status=db.BANK_MATCHED, amount=notice.amount,
                  deposit_id=deposit.id, note=report)


async def _ambiguous(conn, bot, payment, waiting, notice) -> Result:
    """Заявок несколько. Угадывать нельзя — деньги чужие."""
    note = f"подходящих заявок: {len(waiting)}"
    await db.close_bank_payment(
        conn, payment.id, status=db.BANK_AMBIGUOUS, note=note,
    )
    log.warning("[USERBOT] Ambiguous payment — %s", note)

    rows = "\n".join(
        f"├ <code>№{d.id}</code> — клиент <code>{d.user_id}</code>, "
        f"<code>/dep_ok {d.id}</code>"
        for d in waiting[:8]
    )
    await _tell_owner(
        bot,
        "⚠️ <b>Пришла оплата, но заявок несколько</b>\n"
        f"├ Сумма: <b>{fmt(notice.amount)}</b>\n"
        + (f"├ Отправитель: <code>{notice.sender}</code>\n"
           if notice.sender else "")
        + f"└ Ждут той же суммы: <b>{len(waiting)}</b>\n\n"
        f"{rows}\n\n"
        "<blockquote>Деньги <b>не зачислены</b>. Выбирать наугад нельзя — "
        "зачислили бы чужой платёж. Сверьте отправителя и подтвердите "
        "нужную заявку сами.</blockquote>",
    )
    return Result(status=db.BANK_AMBIGUOUS, amount=notice.amount, note=note)


async def _unknown(conn, bot, payment, notice) -> Result:
    """Заявки на такую сумму нет — платёж остаётся неопознанным."""
    await db.close_bank_payment(
        conn, payment.id, status=db.BANK_UNKNOWN, note="заявки на эту сумму нет",
    )
    log.info("[USERBOT] Unknown payment — %s", fmt(notice.amount))
    await _tell_owner(
        bot,
        "❔ <b>Пришла оплата без заявки</b>\n"
        f"├ Сумма: <b>{fmt(notice.amount)}</b>\n"
        + (f"├ Отправитель: <code>{notice.sender}</code>\n"
           if notice.sender else "")
        + (f"├ Код банка: <code>{notice.op_code}</code>\n"
           if notice.op_code else "")
        + f"└ {notice.bank_time or 'время не указано'}\n\n"
        "<blockquote>Никто не оставлял заявку на такую сумму. Возможно, "
        "клиент заплатил, не нажав «Пополнить», — тогда начислите ему "
        "вручную: /panel → 👥 Клиенты.</blockquote>",
    )
    return Result(status=db.BANK_UNKNOWN, amount=notice.amount)


async def _tell_owner(bot, text: str) -> None:
    """Написать владельцам. Молча падать здесь нельзя, но и ронять
    обработку платежа из-за недоступного чата — тоже."""
    if bot is None:
        return
    from app.services.delivery import notify_admins

    try:
        await notify_admins(bot, text)
    except Exception as exc:  # noqa: BLE001 — письмо не важнее платежа
        log.warning("[USERBOT] не смог написать владельцу: %s", exc)
