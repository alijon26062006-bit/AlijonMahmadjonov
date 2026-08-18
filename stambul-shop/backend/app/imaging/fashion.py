"""Съёмочная ретушь одежды: невидимый манекен, вешалка, перекос.

Здесь единственное место в проекте, где картинку рисует модель, а не мы.
Всё остальное — вырезание по маске и арифметика, где товар неизменен по
построению. Тут иначе: убрать вешалку из-под воротника, развернуть
завернувшийся рукав или дать плечам объём, не перерисовывая пиксели,
нельзя в принципе.

Поэтому здесь два предохранителя. Первый — задание: модели прямым текстом
запрещено придумывать невидимое и менять фасон, цвет, фурнитуру и надписи.
Второй, и главный, — сверка результата с оригиналом отдельным проходом
(`app.services.ai_check`). Не сошлось — карточка помечается «нужна
проверка» и сама на витрину не попадает.

Правило, которое перевешивает всё остальное: лучше чуть менее нарядно,
но товар настоящий.
"""
import io

import httpx

from app.imaging.style import BACKGROUNDS, DEFAULT_BACKGROUND

API_URL = "https://api.openai.com/v1/images/edits"
IMAGE_MODEL = "gpt-image-1"
TIMEOUT = 240

PROMPT_VERSION = "FASHION_GHOST_MANNEQUIN_V1"

# Размер, который умеет отдавать модель. К формату карточки 4:5 приводим
# сами — так у всех товаров он одинаковый независимо от того, каким
# режимом обработали.
GEN_SIZE = "1024x1536"

PRINCIPLE = (
    "Ты профессиональный ретушёр товарной фотографии для магазина одежды. "
    "Твоя задача — не создать новый товар, а показать реальный товар с "
    "исходной фотографии. Исходное изображение — источник истины. "
    "Сохрани дизайн, крой, цвет, узор, ткань, швы, пуговицы, молнии, "
    "карманы, кружево, вышивку, стразы, жемчуг, принты, надписи, логотипы, "
    "длину рукавов и изделия, форму воротника и расположение декора. "
    "Исправляй только фотографические огрехи: фон, освещение, случайный "
    "перекос, вешалку, лёгкие складки, композицию. "
    "Если для исправления нужно придумать невидимую часть изделия — не "
    "придумывай её, оставь как есть."
)

STANDARD = (
    "Убери фон и посторонние предметы: стол, стену, пол, руку, вешалку "
    "целиком, если она не перекрыта тканью. Поставь вещь по центру "
    "фронтально. Сделай мягкий студийный свет как от большой софтбокс-"
    "панели: ровный, без пересветов, с сохранением текстуры ткани. "
    "Не меняй форму и пропорции изделия."
)

RESHAPE = (
    "Дополнительно приведи вещь к аккуратной товарной подаче методом "
    "«невидимый манекен»: дай плечам естественный объём, поправь форму "
    "воротника, расправь случайно завернувшийся или перекрутившийся "
    "рукав, выровняй центральную ось и лёгкий перекос, разгладь случайные "
    "складки от хранения. "
    "Не трогай складки, которые являются частью модели: плиссе, "
    "драпировку, сборки, защипы. Если изделие асимметрично по дизайну — "
    "сохрани асимметрию, не делай рукава одинаковыми ради симметрии. "
    "Восстанавливай положение только по видимым данным и симметрии самого "
    "изделия. Если рукав или часть изделия не видны — оставь как на "
    "оригинале."
)

FABRIC = (
    "Ткань должна остаться настоящей: сохрани фактуру материала, мелкие "
    "естественные складки и края. Не делай гладкий пластиковый вид и не "
    "превращай вещь в трёхмерный рендер. "
    "Для белых и светлых вещей особенно важно не пересветить: кружево, "
    "швы, жемчужины, края рукавов и воротник должны читаться."
)

SHADOW = (
    "Под вещью — очень слабая естественная тень, только чтобы появился "
    "объём. Без большого серого пятна, без жёсткого контура, без подиума."
)

# Подача зависит от вида товара: платье и кроссовки нельзя обрабатывать
# одинаково, а сумку не надеть на невидимый манекен.
KIND_HINTS = {
    "clothes": "Это одежда. Фронтальный вид, плечи на одном уровне.",
    "shoes": "Это обувь. Покажи её под лёгким углом три четверти, как в "
             "каталоге, обе половины пары на одном уровне. Невидимый "
             "манекен здесь не нужен.",
    "bag": "Это сумка или аксессуар. Покажи фронтально, ручки и ремень "
           "расправь естественно. Невидимый манекен здесь не нужен.",
    "home": "Это предмет для дома. Покажи фронтально, ровно, без наклона. "
            "Невидимый манекен здесь не нужен.",
}

CLOTHES_SLUGS = {"women_clothes", "men_clothes", "kids_clothes", "underwear"}
SHOES_SLUGS = {"shoes"}
BAG_SLUGS = {"accessories"}


class FashionError(Exception):
    """Ошибка ретуши, которую показываем человеку словами."""


def kind_for(category_slug: str) -> str:
    if category_slug in CLOTHES_SLUGS:
        return "clothes"
    if category_slug in SHOES_SLUGS:
        return "shoes"
    if category_slug in BAG_SLUGS:
        return "bag"
    return "home"


def build_prompt(*, kind: str, reshape: bool, background: str,
                 note: str = "") -> str:
    bg = BACKGROUNDS.get(background) or BACKGROUNDS[DEFAULT_BACKGROUND]
    parts = [
        PRINCIPLE,
        KIND_HINTS.get(kind, KIND_HINTS["clothes"]),
        STANDARD,
    ]
    if reshape and kind == "clothes":
        parts.append(RESHAPE)
    parts += [
        FABRIC,
        SHADOW,
        f"Фон — ровный студийный, нейтральный, цвета примерно "
        f"RGB {bg.rgb[0]},{bg.rgb[1]},{bg.rgb[2]}, с едва заметным "
        f"перепадом яркости. Без интерьера, мебели, растений, текстур и "
        f"цветных заливок.",
        "Товар занимает примерно 80% высоты кадра, отступы сверху и снизу "
        "одинаковые.",
    ]
    if note.strip():
        # Пожелание владельца идёт последним и не отменяет запретов выше
        parts.append("Отдельно от владельца магазина: "
                     + note.strip()[:300])
    return "\n".join(parts)


def _message(response) -> str:
    try:
        return response.json().get("error", {}).get("message", "")
    except Exception:
        return response.text[:200]


def _unknown_parameter(response) -> bool:
    """Отказ из-за незнакомого поля, а не из-за сути запроса."""
    text = _message(response).lower()
    return ("unknown parameter" in text or "unsupported parameter" in text
            or "input_fidelity" in text or "quality" in text)


async def retouch(image: bytes, *, api_key: str, kind: str, reshape: bool,
                  background: str, note: str = "", model: str = "") -> bytes:
    """Отдаёт обработанную картинку. Бросает FashionError, если не вышло."""
    if not api_key:
        raise FashionError("Не задан ключ OpenAI")
    if not image:
        raise FashionError("Нет исходной фотографии")

    prompt = build_prompt(kind=kind, reshape=reshape, background=background,
                          note=note)

    # Необязательные поля идут первой попыткой: они заметно улучшают
    # сохранение деталей, но у разных версий API их может не быть. Отказ
    # именно по ним — не повод терять фотографию, повторяем без них.
    base = {"model": model or IMAGE_MODEL, "prompt": prompt, "size": GEN_SIZE,
            "n": "1"}
    attempts = [{**base, "input_fidelity": "high", "quality": "high"},
                {**base, "quality": "high"},
                base]

    response = None
    for index, data in enumerate(attempts):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(
                    API_URL, headers={"Authorization": f"Bearer {api_key}"},
                    data=data,
                    files={"image": ("photo.png", io.BytesIO(image),
                                     "image/png")})
        except httpx.HTTPError as error:
            raise FashionError(f"Не дозвонился до OpenAI: {error}") from None

        if response.status_code != 400 or index == len(attempts) - 1:
            break
        if not _unknown_parameter(response):
            break

    if response.status_code == 401:
        raise FashionError("Ключ OpenAI не принят")
    if response.status_code == 429:
        raise FashionError("Слишком часто либо кончился лимит OpenAI")
    if response.status_code >= 400:
        raise FashionError(f"OpenAI отказал: {_message(response)[:300]}")

    try:
        import base64
        payload = response.json()["data"][0]
        if payload.get("b64_json"):
            return base64.b64decode(payload["b64_json"])
        url = payload["url"]
    except (KeyError, IndexError, ValueError):
        raise FashionError("Не разобрал ответ модели") from None

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            picture = await client.get(url)
        picture.raise_for_status()
        return picture.content
    except httpx.HTTPError:
        raise FashionError("Не смог забрать готовую картинку") from None
