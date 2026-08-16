"""Все 15 категорий первой версии.

Новая категория = ещё один вызов make_schema / make_parts_category.
Код обработчиков и БД при этом не меняются.
"""
from app.schemas_engine.base_schemas import (
    YES_NO, make_parts_category, make_schema, opts,
)
from app.schemas_engine.fields import CategorySchema, FieldSpec

# ─────────────────────────── Недвижимость ───────────────────────────

ROOMS = opts(("0", "Студия"), ("1", "1 комната"), ("2", "2 комнаты"),
             ("3", "3 комнаты"), ("4", "4 комнаты"), ("5", "5+ комнат"))

PROPERTY = opts(("apartment", "Квартира"), ("room", "Комната"),
                ("studio", "Студия"), ("house", "Дом"))

_flat_core = [
    FieldSpec(key="property_type", label="Тип жилья", type="enum_one", required=True,
              options=PROPERTY, filter="multiselect"),
    FieldSpec(key="rooms", label="Количество комнат", type="enum_one", required=True,
              options=ROOMS, filter="multiselect", post_format="{v}"),
    FieldSpec(key="area", label="Общая площадь, м²", type="int", required=True,
              min=5, max=2000, unit="м²", filter="range", post_format="{v} м²"),
    FieldSpec(key="floor", label="Этаж / этажность", type="string", max_len=10,
              hint="Например: 3/9. Если дом — нажмите «Пропустить»",
              post_format="Этаж {v}"),
]

rent_flat = make_schema(
    "rent_flat", "realty", "Аренда квартиры", "🔑", order=1,
    title_template="{property_type}, {rooms}, {area} м²",
    hashtags=["аренда", "недвижимость"], is_rent=True, geo=True,
    price_label="Цена аренды", negotiable=True,
    specific=_flat_core + [
        FieldSpec(key="rent_period", label="Срок аренды", type="enum_one", required=True,
                  options=opts(("month", "Помесячно"), ("day", "Посуточно")),
                  filter="exact", post_format="{v}"),
        FieldSpec(key="furniture", label="Мебель", type="bool", filter="checkbox",
                  post_format="С мебелью"),
        FieldSpec(key="appliances", label="Бытовая техника", type="enum_many",
                  options=opts(("fridge", "Холодильник"), ("washer", "Стиральная машина"),
                               ("ac", "Кондиционер"), ("tv", "Телевизор"),
                               ("stove", "Плита")),
                  filter="multiselect"),
        FieldSpec(key="renovation", label="Ремонт", type="enum_one",
                  options=opts(("euro", "Евроремонт"), ("cosmetic", "Косметический"),
                               ("none", "Без ремонта")),
                  filter="multiselect"),
        FieldSpec(key="deposit", label="Депозит", type="bool", filter="checkbox"),
        FieldSpec(key="kids_pets", label="Можно с детьми / животными", type="bool",
                  filter="checkbox"),
    ])

sale_flat = make_schema(
    "sale_flat", "realty", "Продажа квартиры", "🏢", order=2,
    title_template="{property_type}, {rooms}, {area} м²",
    hashtags=["продажа", "недвижимость"], negotiable=True, geo=True,
    specific=_flat_core + [
        FieldSpec(key="market", label="Новостройка или вторичка", type="enum_one",
                  required=True,
                  options=opts(("new", "Новостройка"), ("secondary", "Вторичка")),
                  filter="multiselect", post_format="{v}"),
        FieldSpec(key="year_built", label="Год постройки", type="int",
                  min=1900, max=2027, filter="range"),
        FieldSpec(key="wall", label="Материал дома", type="enum_one",
                  options=opts(("brick", "Кирпич"), ("panel", "Панель"),
                               ("monolith", "Монолит"), ("block", "Блок")),
                  filter="multiselect"),
        FieldSpec(key="living_area", label="Жилая площадь, м²", type="int",
                  min=5, max=2000, unit="м²", filter="range"),
        FieldSpec(key="furniture", label="Мебель остаётся", type="bool", filter="checkbox"),
        FieldSpec(key="docs_ready", label="Документы готовы", type="bool",
                  filter="checkbox"),
    ])

# ─────────────────────────────── Авто ───────────────────────────────

ENGINE = opts(("petrol", "Бензин"), ("diesel", "Дизель"), ("gas_petrol", "Газ/бензин"),
              ("hybrid", "Гибрид"), ("electric", "Электро"))
GEARBOX = opts(("mt", "Механика"), ("at", "Автомат"), ("robot", "Робот"),
               ("cvt", "Вариатор"))
BODY = opts(("sedan", "Седан"), ("hatch", "Хэтчбек"), ("wagon", "Универсал"),
            ("cross", "Кроссовер"), ("suv", "Внедорожник"), ("minivan", "Минивэн"),
            ("pickup", "Пикап"), ("coupe", "Купе"))

car_sale = make_schema(
    "car_sale", "auto", "Продажа автомобилей", "🚗", order=1,
    title_template="{brand} {model}, {year}",
    hashtags=["продажа_авто"], negotiable=True,
    specific=[
        FieldSpec(key="vin", label="VIN или номер кузова", type="identifier",
                  identifier="vin_or_frame", filter="exact",
                  hint="17 символов VIN или номер кузова вида ACV30-1234567. "
                       "Марка и год заполнятся сами. Можно пропустить"),
        FieldSpec(key="brand", label="Марка", type="enum_one", required=True,
                  options_ref="brands:cars", allow_other=True, filter="multiselect"),
        FieldSpec(key="model", label="Модель", type="enum_one", required=True,
                  options_ref="models:cars", depends_on="brand", allow_other=True,
                  filter="multiselect"),
        FieldSpec(key="year", label="Год выпуска", type="int", required=True,
                  min=1950, max=2027, filter="range", post_format="{v} г."),
        FieldSpec(key="mileage", label="Пробег, км", type="int", required=True,
                  min=0, max=1_000_000, unit="км", filter="range",
                  post_format="{v} км"),
        FieldSpec(key="engine_type", label="Тип двигателя", type="enum_one",
                  required=True, options=ENGINE, filter="multiselect",
                  post_format="{v}"),
        FieldSpec(key="engine_volume", label="Объём двигателя, л", type="decimal",
                  min=0.5, max=8.0, unit="л", filter="range",
                  visible_if={"engine_type": ["petrol", "diesel", "gas_petrol", "hybrid"]},
                  post_format="{v} л"),
        FieldSpec(key="transmission", label="Коробка передач", type="enum_one",
                  required=True, options=GEARBOX, filter="multiselect",
                  post_format="{v}"),
        FieldSpec(key="drive", label="Привод", type="enum_one",
                  options=opts(("fwd", "Передний"), ("rwd", "Задний"), ("awd", "Полный")),
                  filter="multiselect"),
        FieldSpec(key="body", label="Тип кузова", type="enum_one", required=True,
                  options=BODY, filter="multiselect", post_format="{v}"),
        FieldSpec(key="color", label="Цвет", type="enum_one",
                  options=opts(("white", "Белый"), ("black", "Чёрный"),
                               ("silver", "Серебристый"), ("gray", "Серый"),
                               ("blue", "Синий"), ("red", "Красный"),
                               ("green", "Зелёный"), ("other", "Другой")),
                  filter="multiselect"),
        FieldSpec(key="condition", label="Состояние", type="enum_one", required=True,
                  options=opts(("new", "Новый"), ("used", "Б/у"),
                               ("crashed", "Аварийный"), ("parts", "На запчасти")),
                  filter="multiselect"),
        FieldSpec(key="customs", label="Растаможен", type="bool", required=True,
                  filter="checkbox", post_format="Растаможен"),
        FieldSpec(key="exchange", label="Обмен возможен", type="bool", filter="checkbox"),
    ])

car_rent = make_schema(
    "car_rent", "auto", "Аренда автомобилей", "🚙", order=2,
    title_template="Аренда: {brand} {model}",
    hashtags=["аренда_авто"], is_rent=True,
    price_label="Цена за сутки", price_unit="в сутки",
    specific=[
        FieldSpec(key="brand", label="Марка", type="enum_one", required=True,
                  options_ref="brands:cars", allow_other=True, filter="multiselect"),
        FieldSpec(key="model", label="Модель", type="enum_one", required=True,
                  options_ref="models:cars", depends_on="brand", allow_other=True,
                  filter="multiselect"),
        FieldSpec(key="year", label="Год выпуска", type="int", min=1990, max=2027,
                  filter="range", post_format="{v} г."),
        FieldSpec(key="transmission", label="Коробка передач", type="enum_one",
                  required=True, options=GEARBOX, filter="multiselect",
                  post_format="{v}"),
        FieldSpec(key="with_driver", label="С водителем", type="enum_one", required=True,
                  options=opts(("no", "Без водителя"), ("yes", "С водителем"),
                               ("both", "Оба варианта")),
                  filter="multiselect", post_format="{v}"),
        FieldSpec(key="deposit_amount", label="Залог, сомони", type="int", min=0,
                  hint="0 — если залог не нужен", filter="range"),
        FieldSpec(key="min_days", label="Минимальный срок, суток", type="int",
                  min=1, max=365),
        FieldSpec(key="mileage_limit", label="Лимит пробега в сутки, км", type="int",
                  min=0),
    ])

auto_service = make_schema(
    "auto_service", "auto", "Автоуслуги", "🛠", order=3,
    title_template="{name}",
    hashtags=["автоуслуги"], price_label="Цена от",
    specific=[
        FieldSpec(key="service_type", label="Тип услуги", type="enum_one", required=True,
                  options=opts(("sto", "СТО и ремонт"), ("tire", "Шиномонтаж"),
                               ("wash", "Автомойка"), ("tow", "Эвакуатор"),
                               ("electric", "Автоэлектрик"), ("body", "Кузовной ремонт"),
                               ("diag", "Диагностика"), ("tinting", "Тонировка"),
                               ("paint", "Автомаляр")),
                  filter="multiselect", post_format="{v}"),
        FieldSpec(key="name", label="Название сервиса", type="string", required=True,
                  min=2, max_len=120, searchable=True),
        FieldSpec(key="mobile", label="Выезд к клиенту", type="bool", filter="checkbox",
                  post_format="Выезд к клиенту"),
        FieldSpec(key="around_clock", label="Круглосуточно", type="bool",
                  filter="checkbox", post_format="Круглосуточно"),
        FieldSpec(key="schedule", label="График работы", type="string", max_len=80,
                  hint="Например: ежедневно 8:00–20:00"),
        FieldSpec(key="brands_spec", label="Специализация по маркам", type="enum_many",
                  options_ref="brands:cars", filter="multiselect"),
    ])

# ─────────────────────── Техника и электроника ──────────────────────

SECTIONS = opts(("phones", "Телефоны"), ("tablets", "Планшеты"),
                ("laptops", "Ноутбуки"), ("desktops", "Компьютеры"),
                ("tvs", "Телевизоры"), ("appliances", "Бытовая техника"),
                ("audio", "Аудио"), ("photo", "Фото и видео"),
                ("consoles", "Игровые приставки"), ("watches", "Умные часы"),
                ("other", "Прочее"))

# Раздел техники → область справочника брендов
SECTION_BRAND_AREA = {
    "phones": "phones", "tablets": "phones",
    "laptops": "computers", "desktops": "computers",
    "tvs": "tv_audio", "audio": "tv_audio",
    "appliances": "appliances",
    "photo": "electronics", "consoles": "electronics",
    "watches": "electronics", "other": "electronics",
}

device_sale = make_schema(
    "device_sale", "tech", "Продажа техники", "📱", order=1,
    title_template="{brand} {model}",
    hashtags=["техника"], negotiable=True,
    specific=[
        FieldSpec(key="section", label="Раздел", type="enum_one", required=True,
                  options=SECTIONS, filter="multiselect"),
        FieldSpec(key="imei", label="IMEI", type="identifier", identifier="imei",
                  visible_if={"section": ["phones", "tablets"]}, filter="exact",
                  hint="15 цифр — наберите *#06# на устройстве. Модель подтвердится "
                       "автоматически. Можно пропустить"),
        FieldSpec(key="brand", label="Бренд", type="enum_one", required=True,
                  options_ref="brands:@section", allow_other=True,
                  filter="multiselect"),
        FieldSpec(key="model", label="Модель", type="string", required=True,
                  min=1, max_len=80, searchable=True,
                  hint="Например: Galaxy A54 или iPhone 13"),
        FieldSpec(key="memory", label="Память", type="enum_one",
                  visible_if={"section": ["phones", "tablets"]},
                  options=opts(("64", "64 ГБ"), ("128", "128 ГБ"), ("256", "256 ГБ"),
                               ("512", "512 ГБ"), ("1024", "1 ТБ"), ("other", "Другое")),
                  filter="multiselect", post_format="{v}"),
        FieldSpec(key="year", label="Год выпуска", type="int", min=2000, max=2027,
                  filter="range"),
        FieldSpec(key="condition", label="Состояние", type="enum_one", required=True,
                  options=opts(("new", "Новое"), ("like_new", "Как новое"),
                               ("used", "Б/у"), ("parts", "На запчасти")),
                  filter="multiselect", post_format="{v}"),
        FieldSpec(key="kit", label="Комплектация", type="enum_one",
                  options=opts(("full", "Полный комплект"), ("device", "Только устройство"),
                               ("box", "С коробкой")),
                  filter="multiselect"),
        FieldSpec(key="warranty", label="Гарантия", type="enum_one",
                  options=opts(("none", "Нет"), ("shop", "Магазинная"),
                               ("official", "Официальная")),
                  filter="multiselect"),
        FieldSpec(key="exchange", label="Обмен возможен", type="bool", filter="checkbox"),
    ])

device_repair = make_schema(
    "device_repair", "tech", "Услуги ремонта", "🔩", order=2,
    title_template="{name}",
    hashtags=["ремонт"], price_label="Цена от",
    specific=[
        FieldSpec(key="service_type", label="Тип услуги", type="enum_one", required=True,
                  options=opts(("phone", "Ремонт телефонов"),
                               ("computer", "Ремонт ноутбуков и ПК"),
                               ("tv", "Ремонт телевизоров"),
                               ("appliance", "Ремонт бытовой техники"),
                               ("audio", "Ремонт аудиотехники"),
                               ("data", "Восстановление данных"),
                               ("firmware", "Прошивка и настройка"),
                               ("cleaning", "Чистка и профилактика")),
                  filter="multiselect", post_format="{v}"),
        FieldSpec(key="name", label="Название сервиса", type="string", required=True,
                  min=2, max_len=120, searchable=True),
        FieldSpec(key="mobile", label="Выезд к клиенту", type="bool", filter="checkbox",
                  post_format="Выезд к клиенту"),
        FieldSpec(key="urgent", label="Срочный ремонт", type="bool", filter="checkbox",
                  post_format="Срочный ремонт"),
        FieldSpec(key="warranty", label="Гарантия на работу", type="enum_one",
                  options=opts(("none", "Нет"), ("1m", "1 месяц"),
                               ("3m", "3 месяца"), ("6m", "6 месяцев")),
                  filter="multiselect"),
        FieldSpec(key="schedule", label="График работы", type="string", max_len=80),
    ])

# ─────────────────────── Запчасти и аксессуары ──────────────────────

auto_parts = make_parts_category(
    "auto_parts", "Автозапчасти", "🚗", order=1, brand_area="cars",
    hashtags=["автозапчасти"],
    part_types=[("engine", "Двигатель"), ("suspension", "Подвеска"),
                ("brakes", "Тормоза"), ("body", "Кузов"), ("optics", "Оптика"),
                ("electric", "Электрика"), ("interior", "Салон"),
                ("consumables", "Расходники"), ("tires_discs", "Шины и диски"),
                ("tuning", "Тюнинг")],
    size_for=["tires_discs"])

phone_parts = make_parts_category(
    "phone_parts", "Телефоны и планшеты", "📱", order=2, brand_area="phones",
    hashtags=["запчасти_телефоны"],
    part_types=[("display", "Дисплеи"), ("battery", "Аккумуляторы"),
                ("case", "Корпуса"), ("flex", "Шлейфы"), ("camera", "Камеры"),
                ("port", "Разъёмы зарядки"), ("speaker", "Динамики"),
                ("glass", "Защитные стёкла"), ("cover", "Чехлы"),
                ("charger", "Зарядные устройства")])

computer_parts = make_parts_category(
    "computer_parts", "Компьютеры и ноутбуки", "💻", order=3, brand_area="computers",
    hashtags=["запчасти_компьютеры"],
    part_types=[("screen", "Матрицы"), ("keyboard", "Клавиатуры"),
                ("battery", "Аккумуляторы"), ("mainboard", "Материнские платы"),
                ("cpu", "Процессоры"), ("ram", "Оперативная память"),
                ("storage", "Накопители"), ("gpu", "Видеокарты"),
                ("psu", "Блоки питания"), ("cooling", "Охлаждение")],
    size_for=["ram", "storage"])

appliance_parts = make_parts_category(
    "appliance_parts", "Бытовая техника", "🧺", order=4, brand_area="appliances",
    hashtags=["запчасти_бытовая"],
    part_types=[("heater", "ТЭНы"), ("pump", "Насосы"), ("bearing", "Подшипники"),
                ("shock", "Амортизаторы"), ("compressor", "Компрессоры"),
                ("thermostat", "Термостаты"), ("filter", "Фильтры"),
                ("belt", "Ремни"), ("board", "Платы управления")])

tv_parts = make_parts_category(
    "tv_parts", "Телевизоры и аудио", "📺", order=5, brand_area="tv_audio",
    hashtags=["запчасти_тв"],
    part_types=[("matrix", "Матрицы"), ("backlight", "Подсветка"),
                ("board", "Платы"), ("remote", "Пульты"),
                ("mount", "Кронштейны"), ("speaker", "Динамики")])

tool_parts = make_parts_category(
    "tool_parts", "Инструмент и садовая техника", "🪚", order=6, brand_area="tools",
    hashtags=["запчасти_инструмент"],
    part_types=[("brush", "Щётки"), ("battery", "Аккумуляторы"),
                ("gear", "Редукторы"), ("chain", "Цепи"), ("plug", "Свечи"),
                ("disc", "Диски"), ("line", "Лески")])

moto_parts = make_parts_category(
    "moto_parts", "Мото и велотехника", "🏍", order=7, brand_area="moto_bike",
    hashtags=["запчасти_мото"],
    part_types=[("chain", "Цепи"), ("sprocket", "Звёзды"), ("brakes", "Тормоза"),
                ("tube", "Камеры"), ("tire", "Покрышки"),
                ("shock", "Амортизаторы"), ("mirror", "Зеркала")])

electronics_parts = make_parts_category(
    "electronics_parts", "Прочая электроника", "🎧", order=8, brand_area="electronics",
    hashtags=["запчасти_электроника"],
    part_types=[("strap", "Ремешки"), ("battery", "Аккумуляторы"),
                ("glass", "Стёкла"), ("cable", "Кабели"), ("adapter", "Адаптеры"),
                ("propeller", "Пропеллеры"), ("lens", "Объективы")])

ALL_CATEGORIES: list[CategorySchema] = [
    rent_flat, sale_flat,
    car_sale, car_rent, auto_service,
    device_sale, device_repair,
    auto_parts, phone_parts, computer_parts, appliance_parts,
    tv_parts, tool_parts, moto_parts, electronics_parts,
]
