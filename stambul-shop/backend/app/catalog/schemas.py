"""Разделы магазина и поля товаров.

Один список описывает всё: разделы витрины, поля карточки, фильтры каталога
и то, какие размеры предлагать при заведении вариантов. Новый раздел — ещё
одна запись здесь, ни база, ни интерфейс не меняются.
"""
from pydantic import BaseModel

# ─────────────────────────── Размерные линейки ───────────────────────────
#
# В одежде в ходу и буквы, и числа, поэтому предлагаем обе: продавец
# выбирает нужные при заведении товара, лишние просто не отмечает.

SIZES_LETTER = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL"]
SIZES_WOMEN_NUM = ["36", "38", "40", "42", "44", "46", "48", "50", "52", "54", "56"]
SIZES_MEN_NUM = ["44", "46", "48", "50", "52", "54", "56", "58", "60"]
SIZES_SHOES = [str(n) for n in range(35, 47)]
SIZES_KIDS_AGE = ["0-3 мес", "3-6 мес", "6-9 мес", "9-12 мес", "1-2 года",
                  "2-3 года", "3-4 года", "4-5 лет", "5-6 лет", "7-8 лет",
                  "9-10 лет", "11-12 лет", "13-14 лет"]
SIZES_KIDS_HEIGHT = ["80", "86", "92", "98", "104", "110", "116", "122", "128",
                     "134", "140", "146", "152", "158", "164"]
SIZES_BRA = ["70A", "70B", "70C", "75A", "75B", "75C", "75D", "80B", "80C",
             "80D", "85B", "85C", "85D", "90C", "90D"]
SIZES_ONE = ["Один размер"]

COLORS = ["Чёрный", "Белый", "Серый", "Бежевый", "Коричневый", "Красный",
          "Бордовый", "Розовый", "Оранжевый", "Жёлтый", "Зелёный", "Хаки",
          "Голубой", "Синий", "Тёмно-синий", "Фиолетовый", "Молочный",
          "Золотой", "Серебряный", "Разноцветный"]


class Option(BaseModel):
    value: str
    label: str


class Field(BaseModel):
    key: str
    label: str
    type: str = "string"            # string | text | int | enum_one | enum_many | bool
    required: bool = False
    options: list[str] | None = None
    filter: str = "none"            # multiselect | range | checkbox | none
    unit: str | None = None
    hint: str | None = None
    searchable: bool = False


class Category(BaseModel):
    slug: str
    title: str
    group: str                      # раздел витрины
    icon: str                       # имя иконки во фронтенде
    order: int = 100
    # линейки размеров, предлагаемые при заведении вариантов
    size_scales: list[tuple[str, list[str]]] = []
    fields: list[Field] = []

    def field(self, key: str) -> Field | None:
        return next((f for f in self.fields if f.key == key), None)


def opts(*values: str) -> list[str]:
    return list(values)


# ─────────────────────────── Общие поля ───────────────────────────

SEASON = Field(key="season", label="Сезон", type="enum_one", filter="multiselect",
               options=opts("Лето", "Демисезон", "Зима", "Всесезонный"))
MATERIAL = Field(key="material", label="Состав, материал", type="string",
                 max_len=120, searchable=True,
                 hint="Например: 95% хлопок, 5% эластан")
MADE_IN = Field(key="made_in", label="Страна", type="enum_one",
                filter="multiselect",
                options=opts("Китай", "Казахстан", "Узбекистан", "Россия",
                             "Италия", "Бангладеш", "Другая"))
STYLE = Field(key="style", label="Стиль", type="enum_one", filter="multiselect",
              options=opts("Повседневный", "Классический", "Спортивный",
                           "Вечерний", "Домашний"))


def _clothes_fields(extra: list[Field] | None = None) -> list[Field]:
    kind = extra or []
    return [*kind, SEASON, MATERIAL, STYLE, MADE_IN]


# ─────────────────────────── Разделы ───────────────────────────

CATEGORIES: list[Category] = [
    Category(
        slug="women_clothes", title="Женская одежда", group="Одежда",
        icon="shirt", order=1,
        size_scales=[("Буквы", SIZES_LETTER), ("Числа", SIZES_WOMEN_NUM)],
        fields=_clothes_fields([
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Платье", "Блузка, рубашка", "Футболка", "Свитер, кофта",
                               "Костюм", "Юбка", "Брюки", "Джинсы", "Куртка",
                               "Пальто", "Пуховик", "Спортивный костюм",
                               "Домашняя одежда", "Хиджаб, абая")),
        ])),
    Category(
        slug="men_clothes", title="Мужская одежда", group="Одежда",
        icon="shirt", order=2,
        size_scales=[("Буквы", SIZES_LETTER), ("Числа", SIZES_MEN_NUM)],
        fields=_clothes_fields([
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Футболка", "Рубашка", "Свитер, кофта", "Костюм",
                               "Брюки", "Джинсы", "Куртка", "Пальто", "Пуховик",
                               "Спортивный костюм", "Домашняя одежда")),
        ])),
    Category(
        slug="kids_clothes", title="Детская одежда", group="Детям",
        icon="baby", order=3,
        size_scales=[("Возраст", SIZES_KIDS_AGE), ("Рост, см", SIZES_KIDS_HEIGHT)],
        fields=_clothes_fields([
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Комплект", "Платье", "Футболка", "Кофта",
                               "Брюки", "Джинсы", "Куртка", "Комбинезон",
                               "Пижама", "Школьная форма", "Для новорождённых")),
            Field(key="gender", label="Кому", type="enum_one", filter="multiselect",
                  options=opts("Девочке", "Мальчику", "Универсально")),
        ])),
    Category(
        slug="shoes", title="Обувь", group="Обувь и аксессуары",
        icon="footprints", order=4,
        size_scales=[("Размер", SIZES_SHOES)],
        fields=[
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Кроссовки", "Туфли", "Ботинки", "Сапоги",
                               "Босоножки", "Сандалии", "Тапочки", "Балетки",
                               "Мокасины", "Угги")),
            Field(key="gender", label="Кому", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Женская", "Мужская", "Детская")),
            Field(key="upper", label="Верх", type="enum_one", filter="multiselect",
                  options=opts("Натуральная кожа", "Экокожа", "Замша", "Текстиль",
                               "Нубук")),
            SEASON, MADE_IN,
        ]),
    Category(
        slug="underwear", title="Нижнее бельё", group="Одежда",
        icon="heart", order=5,
        size_scales=[("Буквы", SIZES_LETTER), ("Бюстгальтеры", SIZES_BRA),
                     ("Числа", SIZES_WOMEN_NUM)],
        fields=[
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Комплект", "Бюстгальтер", "Трусы", "Пижама",
                               "Ночная сорочка", "Термобельё", "Носки",
                               "Колготки", "Корректирующее")),
            Field(key="gender", label="Кому", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Женское", "Мужское", "Детское")),
            MATERIAL, MADE_IN,
        ]),
    Category(
        slug="accessories", title="Аксессуары и сумки",
        group="Обувь и аксессуары", icon="briefcase", order=6,
        size_scales=[("Размер", SIZES_ONE)],
        fields=[
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Сумка", "Рюкзак", "Кошелёк", "Ремень", "Часы",
                               "Очки", "Шарф, палантин", "Шапка", "Перчатки",
                               "Украшения", "Чемодан")),
            Field(key="gender", label="Кому", type="enum_one", filter="multiselect",
                  options=opts("Женские", "Мужские", "Универсальные")),
            MATERIAL, MADE_IN,
        ]),
    Category(
        slug="home_textile", title="Текстиль для дома", group="Для дома",
        icon="bed", order=7,
        size_scales=[("Размер", ["1,5-спальный", "2-спальный", "Евро",
                                 "Семейный", "Один размер"])],
        fields=[
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Постельное бельё", "Одеяло", "Подушка", "Плед",
                               "Полотенце", "Скатерть", "Штора", "Ковёр",
                               "Халат")),
            MATERIAL, MADE_IN,
        ]),
    Category(
        slug="dishes", title="Посуда и кухня", group="Для дома",
        icon="utensils", order=8,
        size_scales=[("Размер", SIZES_ONE)],
        fields=[
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Набор посуды", "Кастрюля", "Сковорода", "Чайник",
                               "Сервиз", "Тарелки", "Чашки, кружки", "Столовые приборы",
                               "Контейнеры", "Термос", "Для выпечки")),
            Field(key="material_kitchen", label="Материал", type="enum_one",
                  filter="multiselect",
                  options=opts("Нержавеющая сталь", "Керамика", "Фарфор", "Стекло",
                               "Чугун", "Алюминий", "Пластик", "Дерево")),
            Field(key="pieces", label="Предметов в наборе", type="int",
                  min=1, max=200, filter="range"),
            MADE_IN,
        ]),
    Category(
        slug="appliances", title="Бытовая техника", group="Для дома",
        icon="washing-machine", order=9,
        size_scales=[("Размер", SIZES_ONE)],
        fields=[
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Чайник", "Блендер", "Мясорубка", "Миксер",
                               "Тостер", "Кофеварка", "Утюг", "Фен",
                               "Пылесос", "Мультиварка", "Микроволновка",
                               "Обогреватель", "Вентилятор")),
            Field(key="power", label="Мощность, Вт", type="int",
                  min=1, max=5000, filter="range"),
            Field(key="warranty", label="Гарантия", type="enum_one",
                  filter="multiselect",
                  options=opts("Нет", "3 месяца", "6 месяцев", "1 год", "2 года")),
            MADE_IN,
        ]),
    Category(
        slug="toys", title="Игрушки", group="Детям",
        icon="toy-brick", order=10,
        size_scales=[("Размер", SIZES_ONE)],
        fields=[
            Field(key="kind", label="Что это", type="enum_one", required=True,
                  filter="multiselect",
                  options=opts("Мягкая игрушка", "Конструктор", "Кукла",
                               "Машинка", "Настольная игра", "Развивающая",
                               "Для улицы", "Радиоуправляемая", "Пазл")),
            Field(key="age", label="Возраст", type="enum_one", filter="multiselect",
                  options=opts("0-1 год", "1-3 года", "3-6 лет", "6-9 лет",
                               "9-12 лет", "12+")),
            MADE_IN,
        ]),
]

BY_SLUG = {c.slug: c for c in CATEGORIES}
GROUP_ORDER = ["Одежда", "Обувь и аксессуары", "Детям", "Для дома"]


# ─────────────────────── Разделы, заведённые владельцем ───────────────────
#
# Разделы из этого файла — костяк магазина: у каждого свои поля и свои
# размерные линейки. Но товар не всегда в них помещается, и заставлять
# владельца ждать программиста ради нового раздела неправильно. Поэтому
# он может завести свой прямо из бота: такой раздел получает общий набор
# полей и попадает в группу «Разное».

CUSTOM_GROUP = "Разное"
_CUSTOM: dict[str, Category] = {}


def custom_category(slug: str, title: str, order: int = 100) -> Category:
    return Category(
        slug=slug, title=title, group=CUSTOM_GROUP, icon="package", order=order,
        size_scales=[("Размер", SIZES_LETTER), ("Без размера", SIZES_ONE)],
        fields=[SEASON, MATERIAL, STYLE, MADE_IN])


def register_custom(rows: list[tuple[str, str, int]]) -> None:
    """Обновляет список своих разделов. Вызывается там, где он нужен."""
    _CUSTOM.clear()
    for slug, title, order in rows:
        if slug not in BY_SLUG:
            _CUSTOM[slug] = custom_category(slug, title, order)


def all_categories() -> list[Category]:
    return [*CATEGORIES, *_CUSTOM.values()]


def get_category(slug: str) -> Category | None:
    return BY_SLUG.get(slug) or _CUSTOM.get(slug)


def groups() -> list[dict]:
    """Витрина: разделы с категориями внутри."""
    out = []
    everything = all_categories()
    for name in [*GROUP_ORDER, CUSTOM_GROUP]:
        items = sorted((c for c in everything if c.group == name),
                       key=lambda c: c.order)
        if items:
            out.append({"title": name,
                        "categories": [{"slug": c.slug, "title": c.title,
                                        "icon": c.icon} for c in items]})
    return out


def serialize(category: Category) -> dict:
    return {
        "slug": category.slug,
        "title": category.title,
        "group": category.group,
        "icon": category.icon,
        "size_scales": [{"title": t, "sizes": s} for t, s in category.size_scales],
        "colors": COLORS,
        "fields": [f.model_dump() for f in category.fields],
    }
