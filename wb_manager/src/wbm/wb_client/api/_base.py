"""Общее для обёрток над методами WB: проверка ответа по схеме."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError

from wbm.wb_client.endpoints import Endpoint
from wbm.wb_client.errors import WBInvalidResponseError


class WBModel(BaseModel):
    """Модель ответа WB: лишние поля игнорируем — WB добавляет их без предупреждения."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)


def parse_model[M: BaseModel](model: type[M], data: object, endpoint: Endpoint) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "<корень>"
        raise WBInvalidResponseError(
            f"{endpoint.name}: ответ WB не совпадает с ожидаемой схемой "
            f"(ошибок: {exc.error_count()}, первая — поле «{location}»: {first['msg']})"
        ) from None
