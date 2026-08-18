"""Письма покупателю.

Почта — единственный канал, который есть у всех: вошедший через Google
может не иметь Telegram вовсе. Поэтому письмо о принятом заказе уходит
даже тому, кто выключил уведомления: иначе человек не узнает, куда платить.

Отправка живёт в воркере и завёрнута в поток: smtplib синхронный, а
блокировать цикл событий ради чужого почтового сервера нельзя.
"""
import asyncio
import html
import smtplib
from email.message import EmailMessage

from app.config import get_settings


def _plain(text: str) -> str:
    return " ".join(text.split())


def _send_blocking(to: str, subject: str, body_text: str, body_html: str) -> None:
    s = get_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{s.shop_name} <{s.mail_from}>"
    message["To"] = to
    message.set_content(body_text)
    message.add_alternative(body_html, subtype="html")

    if s.smtp_tls:
        server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20)
    try:
        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_pass)
        server.send_message(message)
    finally:
        server.quit()


async def send(to: str | None, subject: str, lines: list[str]) -> bool:
    """Отправляет письмо. Молча возвращает False, если почта не настроена.

    Ошибка отправки не должна ронять заказ: заказ уже принят, а письмо —
    дело второе, и владелец всё равно увидит его в боте.
    """
    s = get_settings()
    if not to or not s.mail_ready:
        return False

    body_text = "\n".join(lines)
    body_html = _html_page(subject, lines)
    try:
        await asyncio.to_thread(_send_blocking, to, subject, body_text, body_html)
        return True
    except Exception:
        return False


def _html_page(subject: str, lines: list[str]) -> str:
    """Письмо в той же строгой манере, что и сайт: белое, чёрное, без картинок.

    Картинки в письмах половина почтовых клиентов не показывает, поэтому
    вся вёрстка держится на тексте и одной рамке.
    """
    s = get_settings()
    body = "".join(
        f'<p style="margin:0 0 12px;font-size:15px;line-height:22px;'
        f'color:#0A0A0A">{html.escape(line)}</p>' if line else
        '<div style="height:8px"></div>'
        for line in lines)
    return f"""<!doctype html>
<html lang="ru"><body style="margin:0;padding:24px;background:#FAFAFA;
  font-family:-apple-system,'Segoe UI',Roboto,sans-serif">
  <div style="max-width:520px;margin:0 auto;background:#FFFFFF;
    border:1px solid #EAEAEA;border-radius:12px;padding:28px">
    <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;
      color:#6E6E6E;margin-bottom:16px">{html.escape(s.shop_name)}</div>
    <h1 style="margin:0 0 20px;font-size:22px;line-height:28px;
      color:#0A0A0A">{html.escape(subject)}</h1>
    {body}
  </div>
  <div style="max-width:520px;margin:16px auto 0;font-size:12px;
    color:#A1A1A1;text-align:center">
    {html.escape(s.site_url)}
  </div>
</body></html>"""
