"""Декларативное описание поля категории.

Из FieldSpec автоматически строятся: шаг мастера в боте, поле веб-формы,
фильтр каталога, строка карточки и строка поста в канале.
"""
from typing import Literal

from pydantic import BaseModel, Field

FieldType = Literal[
    "int", "decimal", "money", "string", "text",
    "enum_one", "enum_many", "bool", "geo", "photos", "identifier",
]
FilterKind = Literal["range", "multiselect", "checkbox", "exact", "none"]


class Option(BaseModel):
    value: str
    label: str


class FieldSpec(BaseModel):
    key: str
    label: str
    type: FieldType
    required: bool = False
    # Куда пишется значение: имя физической колонки Listing или "attrs"
    stored: str = "attrs"

    # Валидация
    min: float | None = None
    max: float | None = None
    max_len: int | None = None

    # Варианты выбора: статичные или ссылка на справочник
    options: list[Option] | None = None
    # "brands:<area>" | "models:<area>" | "cities" | "districts"
    options_ref: str | None = None
    depends_on: str | None = None          # ключ поля, от которого зависит справочник
    allow_other: bool = False              # пункт «Другое» с ручным вводом

    # Условная видимость: {"ключ_поля": ["значения", ...]}
    visible_if: dict[str, list[str]] | None = None

    # Каталог
    filter: FilterKind = "none"
    searchable: bool = False

    # Вывод
    unit: str | None = None
    card_format: str | None = None         # например "Этаж {v} из {total_floors}"
    post_format: str | None = None         # строка в посте канала

    # Идентификаторы: vin | vin_or_frame | imei | part_number | serial
    identifier: str | None = None

    # Подсказка в мастере под вопросом
    hint: str | None = None


class CategorySchema(BaseModel):
    slug: str
    parent: str                            # slug направления
    title: str
    emoji: str
    order: int = 100
    # Шаблон заголовка объявления, подстановки из значений: "{brand} {model}, {year}"
    title_template: str
    hashtags: list[str] = Field(default_factory=list)
    is_rent: bool = False                  # включает жизненный цикл «занято/свободно»
    fields: list[FieldSpec]

    def field(self, key: str) -> FieldSpec | None:
        return next((f for f in self.fields if f.key == key), None)

    def filterable(self) -> list[FieldSpec]:
        return [f for f in self.fields if f.filter != "none"]

    def visible(self, spec: FieldSpec, values: dict) -> bool:
        if not spec.visible_if:
            return True
        return all(str(values.get(k)) in allowed for k, allowed in spec.visible_if.items())


class DirectionInfo(BaseModel):
    slug: str
    title: str
    emoji: str
    order: int


DIRECTIONS = [
    DirectionInfo(slug="realty", title="Недвижимость", emoji="🏠", order=1),
    DirectionInfo(slug="auto", title="Авто", emoji="🚗", order=2),
    DirectionInfo(slug="tech", title="Техника и электроника", emoji="📱", order=3),
    DirectionInfo(slug="parts", title="Запчасти и аксессуары", emoji="🔧", order=4),
]
