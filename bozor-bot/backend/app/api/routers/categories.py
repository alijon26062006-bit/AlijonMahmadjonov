"""Дерево категорий и схемы полей для формы и фильтров."""
from fastapi import APIRouter, HTTPException

from app.api.deps import Db
from app.schemas_engine.registry import (
    categories_tree, get_schema, resolve_options, serialize_schema,
)

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
async def tree():
    return {"directions": categories_tree()}


@router.get("/{slug}/schema")
async def schema(slug: str, session: Db):
    s = get_schema(slug)
    if not s:
        raise HTTPException(404, "not_found")
    resolved = {}
    for f in s.fields:
        # справочники без зависимостей резолвим сразу; зависимые фронт дотянет
        if f.options_ref and not f.depends_on and "@" not in f.options_ref:
            resolved[f.key] = await resolve_options(session, f, {})
    return serialize_schema(s, resolved)
