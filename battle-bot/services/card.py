"""Картинка участника для сторис и чатов.

Пересланный текст со ссылкой никто не выкладывает, а картинку — выкладывают.
Поэтому бот рисует участнику готовый постер: его ник, соперник, призыв
голосовать и адрес бота. Каждый участник становится рекламой батла.

Модуль намеренно не знает про Telegram: на вход — имена и ссылка, на выходе
PNG в байтах. Так его легко проверить тестами.
"""
from __future__ import annotations

import logging
from io import BytesIO

log = logging.getLogger(__name__)

WIDTH, HEIGHT = 1080, 1920

# сверху вниз: тёмно-синий уходит в почти чёрный — на таком фоне светлый
# текст читается и в светлой, и в тёмной теме Telegram
TOP = (32, 38, 78)
BOTTOM = (10, 12, 26)
ACCENT = (255, 196, 72)
LIGHT = (255, 255, 255)
MUTED = (150, 160, 190)

# первый существующий файл и будет шрифтом; DejaVu есть почти в любой Linux
FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def font_path() -> str:
    from pathlib import Path

    for candidate in FONTS:
        if Path(candidate).exists():
            return candidate
    return ""


_ready: bool | None = None


def available() -> bool:
    """Можно ли вообще рисовать: есть библиотека и шрифт.

    Проверяется до показа кнопки — обещать картинку и не дать её хуже, чем
    не обещать вовсе. Ответ не меняется на ходу, поэтому запоминается: иначе
    каждая кнопка лезла бы на диск.
    """
    global _ready
    if _ready is None:
        try:
            import PIL
        except ImportError:
            _ready = False
        else:
            _ready = bool(PIL and font_path())
        if not _ready:
            log.warning("Картинки для сторис выключены: нет Pillow или шрифта")
    return _ready


def clean(name: str, limit: int = 20) -> str:
    """Оставить то, что шрифт умеет нарисовать.

    Эмодзи и прочие символы DejaVu не знает и рисует пустыми квадратами —
    лучше их убрать, чем показать участнику постер с квадратами вместо ника.
    """
    kept = [
        char for char in (name or "")
        if char.isalnum() or char in " _-.·"
    ]
    text = "".join(kept).strip()
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text or "участник"


def _fit(draw, text: str, size: int, width: int, floor: int = 24):
    """Подобрать размер шрифта так, чтобы строка влезла по ширине."""
    from PIL import ImageFont

    path = font_path()
    while size > floor:
        font = ImageFont.truetype(path, size)
        if draw.textlength(text, font=font) <= width:
            return font
        size -= 4
    return ImageFont.truetype(path, floor)


def _center(draw, text: str, y: int, font, fill) -> None:
    draw.text((WIDTH // 2, y), text, font=font, fill=fill, anchor="ma")


def _background(image) -> None:
    """Вертикальный градиент: рисуем построчно, без лишних зависимостей."""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        share = y / HEIGHT
        color = tuple(
            int(TOP[channel] + (BOTTOM[channel] - TOP[channel]) * share)
            for channel in range(3)
        )
        draw.line([(0, y), (WIDTH, y)], fill=color)


def render(nickname: str, rival: str, link: str, title: str = "БИТВА НИКОВ",
           prize: str = "") -> bytes:
    """Постер участника в PNG. Размер — как сторис, 1080×1920."""
    from PIL import Image, ImageDraw, ImageFont

    path = font_path()
    image = Image.new("RGB", (WIDTH, HEIGHT), BOTTOM)
    _background(image)
    draw = ImageDraw.Draw(image)

    me, other = clean(nickname), clean(rival)
    margin = 90
    inner = WIDTH - margin * 2

    # рамка: без неё картинка сливается с фоном ленты
    draw.rounded_rectangle(
        (40, 40, WIDTH - 40, HEIGHT - 40), radius=60, outline=(70, 80, 130), width=4
    )

    # шапка: где это происходит
    _center(draw, clean(title, 28).upper(), 150, ImageFont.truetype(path, 46), MUTED)
    draw.line([(margin, 250), (WIDTH - margin, 250)], fill=(70, 80, 120), width=3)

    # главное — ник; он должен читаться с расстояния вытянутой руки
    _center(draw, f"@{me}", 400, _fit(draw, f"@{me}", 150, inner), LIGHT)

    # значок «против» между именами: взгляд сразу видит, что это поединок
    draw.ellipse((WIDTH // 2 - 70, 640, WIDTH // 2 + 70, 780), outline=ACCENT, width=5)
    _center(draw, "VS", 675, ImageFont.truetype(path, 60), ACCENT)

    _center(draw, f"@{other}", 840, _fit(draw, f"@{other}", 90, inner), MUTED)

    if prize:
        _center(draw, clean(prize, 30), 1010, ImageFont.truetype(path, 48), LIGHT)

    # призыв: ради него всё и рисуется
    call = ImageFont.truetype(path, 104)
    _center(draw, "ГОЛОСУЙ", 1150, call, ACCENT)
    _center(draw, "ЗА МЕНЯ", 1280, call, ACCENT)

    # плашка со ссылкой внизу — куда идти голосовать
    address = clean_link(link)
    draw.rounded_rectangle((margin, 1520, WIDTH - margin, 1700), radius=40, fill=LIGHT)
    _center(draw, address, 1570, _fit(draw, address, 64, inner - 80), BOTTOM)

    _center(draw, "голосование в боте · бесплатно", 1760,
            ImageFont.truetype(path, 38), MUTED)

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def clean_link(link: str) -> str:
    """Ссылка без протокола и без хвоста: на картинке важен адрес бота."""
    text = (link or "").replace("https://", "").replace("http://", "")
    return text.split("?")[0].rstrip("/") or "t.me"
