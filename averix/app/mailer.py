"""
Отправка писем: подтверждение почты и восстановление пароля.

Настраивается переменными окружения. Если они не заданы, письма
не уходят — и это не авария: маркетплейс работает, а восстановление
пароля просто недоступно, о чём прямо написано в документации.
Выдумывать «отправлено» там, где ничего не отправлялось, нельзя.

Отправка идёт в отдельном потоке после того, как всё записано в базу:
чужой почтовый сервер не должен задерживать ответ человеку и тем
более ронять форму, если он недоступен.

Пароль от почтового ящика читается только здесь, на сервере.
В журнал не попадает ни он, ни адрес получателя целиком.
"""
import smtplib
import threading
from email.message import EmailMessage

from . import journal
from .config import (
    SITE_URL,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_TLS,
    SMTP_USER,
)

_TIMEOUT = 10


def configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def _hide(address: str) -> str:
    """Для журнала: видно домен и первую букву, но не сам адрес."""
    name, _, domain = (address or "").partition("@")
    return f"{name[:1]}***@{domain}" if domain else "***"


def _send(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        if SMTP_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=_TIMEOUT)
            server.starttls()
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=_TIMEOUT)
        with server:
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        journal.event("письмо.отправлено", кому=_hide(to))
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        # Ни текста ошибки сервера, ни адреса, ни темы: в теме бывает
        # имя человека, а в ошибке — строка подключения с логином.
        journal.warn("письмо.не_доставлено", причина=type(exc).__name__,
                     кому=_hide(to))


def send(to: str, subject: str, body: str) -> bool:
    """Ставит письмо в очередь. False — почта в проекте не настроена."""
    if not configured() or not to:
        return False
    threading.Thread(target=_send, args=(to, subject, body), daemon=True).start()
    return True


# ============================================================
# Готовые письма
# ============================================================

def send_verification(to: str, token: str) -> bool:
    return send(
        to,
        "AVERIX — подтвердите почту",
        "Здравствуйте!\n\n"
        "Вы указали этот адрес при регистрации на AVERIX Freelance.\n"
        "Чтобы подтвердить его, откройте ссылку:\n\n"
        f"{SITE_URL}/freelance/verify?token={token}\n\n"
        "Ссылка действует двое суток.\n"
        "Если вы не регистрировались — просто не отвечайте на это письмо.\n",
    )


def send_reset(to: str, token: str) -> bool:
    return send(
        to,
        "AVERIX — восстановление пароля",
        "Здравствуйте!\n\n"
        "Кто-то запросил восстановление пароля для этого адреса.\n"
        "Если это вы, откройте ссылку и задайте новый пароль:\n\n"
        f"{SITE_URL}/freelance/reset?token={token}\n\n"
        "Ссылка действует два часа и срабатывает один раз.\n"
        "Если вы ничего не запрашивали, ничего делать не нужно:\n"
        "пароль останется прежним.\n",
    )
