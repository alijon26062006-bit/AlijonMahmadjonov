"""Базовые схемы и общий «хвост» полей, наследуемый всеми категориями."""
from app.schemas_engine.fields import CategorySchema, FieldSpec, Option


def opts(*pairs: tuple[str, str]) -> list[Option]:
    return [Option(value=v, label=l) for v, l in pairs]


YES_NO = opts(("yes", "Да"), ("no", "Нет"))

WARRANTY = opts(("none", "Нет"), ("7d", "7 дней"), ("1m", "1 месяц"),
                ("3m", "3 месяца"), ("6m", "6 месяцев"), ("1y", "1 год"))

DELIVERY = opts(("pickup", "Самовывоз"), ("city", "По городу"), ("country", "По стране"))


def common_tail(*, price_label: str = "Цена", price_unit: str | None = None,
                negotiable: bool = False, geo_required: bool = False) -> list[FieldSpec]:
    """Поля, завершающие любую категорию: цена, место, описание, фото, контакт."""
    tail: list[FieldSpec] = [
        FieldSpec(key="price", label=price_label, type="money", required=True,
                  stored="price", min=1, unit=price_unit, filter="range",
                  hint="Например: 45000 или 4200$ — знак $ переключит валюту"),
    ]
    if negotiable:
        tail.append(FieldSpec(key="is_negotiable", label="Торг уместен", type="bool",
                              stored="is_negotiable", filter="checkbox"))
    tail += [
        FieldSpec(key="city_id", label="Город", type="enum_one", required=True,
                  stored="city_id", options_ref="cities", filter="exact"),
        FieldSpec(key="district_id", label="Район", type="enum_one",
                  stored="district_id", options_ref="districts",
                  depends_on="city_id", filter="multiselect"),
        FieldSpec(key="address", label="Адрес или ориентир", type="string",
                  stored="address", max_len=255,
                  hint="Например: рядом с рынком Корвон"),
        FieldSpec(key="geo", label="Точка на карте", type="geo",
                  required=geo_required, stored="geo",
                  hint="Отправьте геолокацию — объявление появится на карте"),
        FieldSpec(key="description", label="Описание", type="text", required=True,
                  stored="description", max_len=1000, searchable=True,
                  hint="До 1000 символов. Без ссылок и телефонов — контакт укажете отдельно"),
        FieldSpec(key="photos", label="Фотографии", type="photos", required=True,
                  stored="photos", max=10,
                  hint="От 1 до 10 фото. Можно отправить альбомом"),
        FieldSpec(key="contact_mode", label="Как с вами связаться", type="enum_one",
                  required=True, stored="contact_mode",
                  options=opts(("telegram", "Написать в Telegram"),
                               ("phone", "Позвонить по телефону"),
                               ("both", "Telegram и телефон"))),
    ]
    return tail


def make_schema(slug: str, parent: str, title: str, emoji: str, *,
                title_template: str, hashtags: list[str],
                specific: list[FieldSpec], order: int = 100,
                price_label: str = "Цена", price_unit: str | None = None,
                negotiable: bool = False, is_rent: bool = False,
                geo_required: bool = False) -> CategorySchema:
    return CategorySchema(
        slug=slug, parent=parent, title=title, emoji=emoji, order=order,
        title_template=title_template, hashtags=hashtags, is_rent=is_rent,
        fields=specific + common_tail(price_label=price_label, price_unit=price_unit,
                                      negotiable=negotiable, geo_required=geo_required),
    )


def make_parts_category(slug: str, title: str, emoji: str, *,
                        part_types: list[tuple[str, str]], brand_area: str,
                        order: int, hashtags: list[str],
                        size_for: list[str] | None = None) -> CategorySchema:
    """Категория запчастей: наследование базовой схемы «Товар» подменой двух справочников."""
    specific: list[FieldSpec] = [
        FieldSpec(key="part_type", label="Тип детали", type="enum_one", required=True,
                  options=opts(*part_types), filter="multiselect"),
        FieldSpec(key="name", label="Название", type="string", required=True,
                  min=3, max_len=120, searchable=True,
                  hint="Например: Передние тормозные колодки"),
        FieldSpec(key="brand_device", label="Для какой марки", type="enum_one",
                  options_ref=f"brands:{brand_area}", allow_other=True,
                  filter="multiselect", post_format="Для {v}"),
        FieldSpec(key="model_device", label="Модель устройства", type="string",
                  max_len=80, searchable=True),
        FieldSpec(key="part_number", label="Артикул (парт-номер)", type="identifier",
                  identifier="part_number", max_len=40, filter="exact",
                  hint="Номер с упаковки или детали — по нему вас найдут мастера"),
        FieldSpec(key="condition", label="Состояние", type="enum_one", required=True,
                  options=opts(("new", "Новое"), ("used", "Б/у"),
                               ("refurb", "Восстановленное")),
                  filter="multiselect", post_format="{v}"),
        FieldSpec(key="originality", label="Оригинальность", type="enum_one",
                  options=opts(("original", "Оригинал"), ("analog", "Аналог"),
                               ("copy", "Копия")),
                  filter="multiselect", post_format="{v}"),
        FieldSpec(key="warranty", label="Гарантия", type="enum_one",
                  options=WARRANTY, filter="multiselect"),
        FieldSpec(key="qty", label="Количество", type="int", min=1, max=9999),
        FieldSpec(key="delivery", label="Доставка", type="enum_one",
                  options=DELIVERY, filter="multiselect"),
    ]
    if size_for:
        specific.insert(2, FieldSpec(
            key="size", label="Размер", type="string", max_len=40,
            visible_if={"part_type": size_for},
            hint="Например: 195/65 R15", post_format="{v}"))
    return make_schema(
        slug, "parts", title, emoji, order=order,
        title_template="{name}", hashtags=hashtags,
        specific=specific, price_label="Цена за единицу", negotiable=True)
