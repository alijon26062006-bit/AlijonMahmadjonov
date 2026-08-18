"""Подготовка фотографии товара для каталога.

Правило, вокруг которого всё построено: **пиксели товара не трогаем**.
Модель здесь занята одним делом — строит маску, то есть отвечает, где на
снимке товар, а где стол, рука и стена. Всё остальное — вырезание по этой
маске, фон, масштаб, тень — обычная арифметика над картинкой.

Это не осторожность ради осторожности. В требованиях сказано: не менять
форму, цвет, логотипы и надписи. Генеративная модель, перерисовывающая
кадр целиком, выполнить это не может в принципе — она может лишь стараться.
Здесь надпись на коробке остаётся той же самой, потому что это буквально
те же пиксели.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageFilter

from app.imaging.style import (
    BACKGROUNDS, CANVAS, DARK_MAX, DEFAULT_BACKGROUND, JPEG_QUALITY,
    LIGHT_MIN, MIN_EDGE_CONTRAST, SHADOW, STYLE_VERSION, SUBJECT_RATIO,
    SUBJECT_SHIFT_Y, Background,
)

MAX_INPUT_SIDE = 2000       # больше не нужно: маску считаем и так медленно


class ImagingError(Exception):
    """Ошибка обработки, которую нужно показать человеку словами."""


@dataclass
class Result:
    data: bytes
    background: str
    subject_luma: float
    style_version: int
    width: int
    height: int


# ─────────────────────────── Маска товара ───────────────────────────

_session = None


def _cutout(image: Image.Image) -> Image.Image:
    """Отделяет товар от фона. Возвращает RGBA с прозрачным фоном."""
    global _session
    try:
        from rembg import new_session, remove
    except ImportError:  # pragma: no cover — зависимость ставится в образ
        raise ImagingError(
            "Модуль отделения фона не установлен на сервере") from None

    if _session is None:
        # Сессия держит модель в памяти между вызовами: загрузка занимает
        # секунды, и делать её на каждую фотографию расточительно.
        _session = new_session("u2net")
    try:
        return remove(image, session=_session).convert("RGBA")
    except Exception as error:
        raise ImagingError(f"Не удалось отделить товар от фона: {error}") from None


# ─────────────────────────── Выбор фона ───────────────────────────

def _subject_stats(cut: Image.Image) -> tuple[float, float]:
    """Средняя яркость товара и яркость его краёв.

    Края считаем отдельно: белая коробка в целом светлая, но пропасть на
    фоне она может именно кромкой, и решать нужно по ней.
    """
    alpha = cut.getchannel("A")
    gray = cut.convert("L")

    solid = alpha.point(lambda a: 255 if a > 160 else 0)
    body_luma = _mean_where(gray, solid)

    # кромка: то, что осталось от маски после сжатия внутрь
    inner = solid.filter(ImageFilter.MinFilter(9))
    edge = Image.composite(Image.new("L", solid.size, 0), solid, inner)
    edge_luma = _mean_where(gray, edge)
    body = body_luma if body_luma is not None else 128.0
    return body, edge_luma if edge_luma is not None else body


def _mean_where(gray: Image.Image, mask: Image.Image) -> float | None:
    """Средняя яркость пикселей под маской — по гистограмме, без перебора."""
    total = count = 0
    for level, n in enumerate(gray.histogram(mask=mask)):
        total += level * n
        count += n
    return (total / count) if count else None


def choose_background(subject_luma: float, edge_luma: float) -> Background:
    """Фон подбирается под товар, но только из трёх фирменных.

    Логика ровно та, что в требованиях: тёмному товару светлый фон,
    среднему — самый светлый, очень светлому — сероватый, чтобы не
    растворился. Плюс проверка контраста по кромке.
    """
    if subject_luma >= LIGHT_MIN:
        chosen = BACKGROUNDS["soft_gray"]
    elif subject_luma <= DARK_MAX:
        chosen = BACKGROUNDS["light"]
    else:
        chosen = BACKGROUNDS["very_light"]

    order = ["very_light", "light", "soft_gray"]
    while abs(edge_luma - chosen.luma) < MIN_EDGE_CONTRAST:
        index = order.index(chosen.key)
        if index + 1 >= len(order):
            break
        chosen = BACKGROUNDS[order[index + 1]]
    return chosen


# ─────────────────────────── Сборка кадра ───────────────────────────

def _trim(cut: Image.Image) -> Image.Image:
    box = cut.getchannel("A").getbbox()
    if box is None:
        raise ImagingError("На фотографии не нашёлся товар")
    return cut.crop(box)


def _shadow_layer(subject: Image.Image, size: tuple[int, int],
                  left: int, bottom: int) -> Image.Image:
    """Мягкая студийная тень: приплюснутый силуэт товара под ним."""
    width, height = subject.size
    shadow_h = max(6, int(height * SHADOW["squash"]))
    shadow_w = max(6, int(width * SHADOW["spread"]))

    silhouette = subject.getchannel("A").resize((shadow_w, shadow_h),
                                                Image.LANCZOS)
    layer = Image.new("L", size, 0)
    x = left - (shadow_w - width) // 2
    y = bottom - shadow_h // 2 + int(size[1] * SHADOW["offset"])
    layer.paste(silhouette, (x, y))
    layer = layer.filter(ImageFilter.GaussianBlur(SHADOW["blur"]))
    return layer.point(lambda v: int(v * SHADOW["opacity"]))


def _open(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        return image
    except Exception:
        raise ImagingError("Файл не похож на изображение") from None


def compose(original: bytes, *, background: str | None = None,
            cutout_png: bytes | None = None) -> Result:
    """Главная функция: из снимка с телефона делает карточку каталога.

    `cutout_png` — уже готовая маска от стороннего сервиса. Если её нет,
    строим сами.
    """
    if cutout_png is not None:
        cut_source = _open(cutout_png).convert("RGBA")
    else:
        image = _open(original).convert("RGB")
        if max(image.size) > MAX_INPUT_SIDE:
            image.thumbnail((MAX_INPUT_SIDE, MAX_INPUT_SIDE), Image.LANCZOS)
        cut_source = _cutout(image)

    cut = _trim(cut_source)
    subject_luma, edge_luma = _subject_stats(cut)

    if background and background in BACKGROUNDS:
        chosen = BACKGROUNDS[background]          # владелец выбрал вручную
    else:
        chosen = choose_background(subject_luma or 128, edge_luma or 128)

    canvas_w, canvas_h = CANVAS
    scale = min(canvas_w * SUBJECT_RATIO / cut.width,
                canvas_h * SUBJECT_RATIO / cut.height)
    new_size = (max(1, round(cut.width * scale)), max(1, round(cut.height * scale)))
    subject = cut.resize(new_size, Image.LANCZOS)

    left = (canvas_w - subject.width) // 2
    top = (canvas_h - subject.height) // 2 + int(canvas_h * SUBJECT_SHIFT_Y)

    canvas = Image.new("RGB", CANVAS, chosen.rgb)
    shadow = _shadow_layer(subject, CANVAS, left, top + subject.height)
    dark = Image.new("RGB", CANVAS, (0, 0, 0))
    canvas = Image.composite(dark, canvas, shadow)
    canvas.paste(subject, (left, top), subject)

    buffer = io.BytesIO()
    canvas.save(buffer, "JPEG", quality=JPEG_QUALITY, optimize=True,
                progressive=True)
    return Result(data=buffer.getvalue(), background=chosen.key,
                  subject_luma=round(subject_luma or 0, 1),
                  style_version=STYLE_VERSION,
                  width=canvas_w, height=canvas_h)


def fit_canvas(data: bytes, background: str | None = None) -> Result:
    """Приводит уже готовую картинку к формату карточки.

    Нужна после генеративной ретуши: модель отдаёт свой размер, а в
    каталоге у всех товаров кадр одинаковый. Пиксели не растягиваем —
    вписываем и добираем полями того же цвета, что и края изображения,
    поэтому стык незаметен.
    """
    image = _open(data).convert("RGB")
    canvas_w, canvas_h = CANVAS

    scale = min(canvas_w / image.width, canvas_h / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    fitted = image.resize(size, Image.LANCZOS)

    chosen = BACKGROUNDS.get(background or "") if background else None
    if chosen is None:
        # цвет полей берём с краёв самой картинки: так поле не спорит с
        # фоном, который нарисовала модель
        edge = fitted.crop((0, 0, fitted.width, max(1, fitted.height // 40)))
        fill = tuple(round(v) for v in _average(edge))
    else:
        fill = chosen.rgb

    canvas = Image.new("RGB", CANVAS, fill)
    canvas.paste(fitted, ((canvas_w - fitted.width) // 2,
                          (canvas_h - fitted.height) // 2))

    buffer = io.BytesIO()
    canvas.save(buffer, "JPEG", quality=JPEG_QUALITY, optimize=True,
                progressive=True)
    return Result(data=buffer.getvalue(),
                  background=chosen.key if chosen else "generated",
                  subject_luma=0.0, style_version=STYLE_VERSION,
                  width=canvas_w, height=canvas_h)


def _average(image: Image.Image) -> tuple[float, float, float]:
    pixels = image.getdata()
    n = max(1, len(pixels))
    totals = [0, 0, 0]
    for r, g, b in pixels:
        totals[0] += r
        totals[1] += g
        totals[2] += b
    return (totals[0] / n, totals[1] / n, totals[2] / n)
