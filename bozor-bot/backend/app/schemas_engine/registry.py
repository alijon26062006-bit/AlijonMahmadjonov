"""Реестр категорий и работа со схемами: справочники, заголовки, сериализация."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas_engine.categories import ALL_CATEGORIES, SECTION_BRAND_AREA
from app.schemas_engine.fields import DIRECTIONS, CategorySchema, FieldSpec

REGISTRY: dict[str, CategorySchema] = {c.slug: c for c in ALL_CATEGORIES}

OTHER = "__other__"


def get_schema(slug: str) -> CategorySchema | None:
    return REGISTRY.get(slug)


def categories_tree() -> list[dict]:
    """Дерево направлений с категориями — для меню бота и Mini App."""
    tree = []
    for d in sorted(DIRECTIONS, key=lambda x: x.order):
        cats = sorted((c for c in ALL_CATEGORIES if c.parent == d.slug),
                      key=lambda c: c.order)
        tree.append({
            "slug": d.slug, "title": d.title, "emoji": d.emoji,
            "categories": [
                {"slug": c.slug, "title": c.title, "emoji": c.emoji,
                 "is_rent": c.is_rent}
                for c in cats
            ],
        })
    return tree


async def resolve_options(session: AsyncSession, spec: FieldSpec,
                          values: dict) -> list[tuple[str, str]]:
    """Список (value, label) для поля выбора: статичный или из справочника."""
    from app.db.models import Brand, City, District, VehicleModel

    if spec.options:
        out = [(o.value, o.label) for o in spec.options]
    elif spec.options_ref:
        ref, _, area = spec.options_ref.partition(":")
        if area == "@section":       # область зависит от выбранного раздела техники
            area = SECTION_BRAND_AREA.get(str(values.get("section")), "electronics")
        if ref == "cities":
            rows = (await session.scalars(
                select(City).where(City.is_active).order_by(City.sort_order))).all()
            out = [(str(c.id), c.name) for c in rows]
        elif ref == "districts":
            city_id = values.get("city_id")
            if not city_id:
                return []
            rows = (await session.scalars(
                select(District).where(District.city_id == int(city_id))
                .order_by(District.name))).all()
            out = [(str(d.id), d.name) for d in rows]
        elif ref == "brands":
            rows = (await session.scalars(
                select(Brand).where(Brand.areas.any(area))
                .order_by(Brand.sort_order, Brand.name))).all()
            out = [(b.name, b.name) for b in rows]
        elif ref == "models":
            brand = values.get(spec.depends_on or "brand")
            rows = (await session.scalars(
                select(VehicleModel).join(Brand)
                .where(Brand.name == str(brand), VehicleModel.area == area)
                .order_by(VehicleModel.sort_order))).all()
            out = [(m.name, m.name) for m in rows]
        else:
            out = []
    else:
        out = []

    if spec.allow_other:
        out.append((OTHER, "✍️ Другое"))
    return out


def option_label(spec: FieldSpec, value) -> str:
    """Отображаемое значение: для enum — подпись варианта, иначе само значение."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, list):
        return ", ".join(option_label(spec, v) for v in value)
    if spec.options:
        for o in spec.options:
            if o.value == str(value):
                return o.label
    return str(value)


def render_title(schema: CategorySchema, values: dict, labels: dict) -> str:
    """Заголовок объявления по шаблону категории; пропуски убираются аккуратно."""
    out = schema.title_template
    for spec in schema.fields:
        token = "{" + spec.key + "}"
        if token in out:
            out = out.replace(token, labels.get(spec.key) or str(values.get(spec.key) or ""))
    # схлопываем следы пропущенных значений
    out = " ".join(out.split()).strip(" ,·—-")
    return (out or schema.title)[:140]


def serialize_schema(schema: CategorySchema,
                     resolved: dict[str, list[tuple[str, str]]]) -> dict:
    """Схема для фронтенда: форма подачи и фильтры строятся из этого JSON."""
    return {
        "slug": schema.slug,
        "parent": schema.parent,
        "title": schema.title,
        "emoji": schema.emoji,
        "is_rent": schema.is_rent,
        "fields": [
            {
                "key": f.key, "label": f.label, "type": f.type,
                "required": f.required, "stored": f.stored,
                "min": f.min, "max": f.max, "max_len": f.max_len,
                "options": resolved.get(f.key)
                    or ([(o.value, o.label) for o in f.options] if f.options else None),
                "options_ref": f.options_ref, "depends_on": f.depends_on,
                "allow_other": f.allow_other, "visible_if": f.visible_if,
                "filter": f.filter, "unit": f.unit, "hint": f.hint,
                "identifier": f.identifier,
            }
            for f in schema.fields
        ],
    }
