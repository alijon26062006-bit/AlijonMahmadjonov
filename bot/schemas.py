"""JSON-схемы инструментов, которые получает Claude.

Схемы намеренно НЕ помечены strict: речь после распознавания бывает неполной,
и лучше принять запись с пропущенными полями и почистить её в Python
(см. tools.clean_*), чем получить отказ модели от вызова.
"""

from __future__ import annotations

from typing import Any

_DIRECTION = {
    "type": "string",
    "enum": ["out", "in"],
    "description": "out — деньги ушли от пользователя; in — деньги пришли пользователю.",
}
_KIND = {
    "type": "string",
    "enum": ["transfer", "payment", "debt", "income"],
    "description": "transfer — перевод человеку; payment — оплата за товар/услугу; "
                   "debt — долг (взял или дал в долг); income — приход денег.",
}
_DATE = {"type": "string", "description": "Дата в формате ГГГГ-ММ-ДД."}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "save_transaction",
        "description": (
            "Сохранить новую денежную операцию: перевод, оплату, долг или приход. "
            "Вызывай, когда пользователь РАССКАЗЫВАЕТ о состоявшемся действии "
            "(«отправил», «оплатил», «дал в долг», «получил»), а не спрашивает о прошлом. "
            "Заполняй только то, что реально прозвучало; ничего не выдумывай."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": _DIRECTION,
                "kind": _KIND,
                "counterparty": {"type": "string", "description": "Кому или от кого. Имя как произнёс пользователь."},
                "amount": {"type": "number", "description": "Сумма числом. «500 тысяч» = 500000."},
                "currency": {"type": "string", "description": "Код валюты: TJS (сомони), KZT (тенге), RUB, USD, UZS, KGS, EUR."},
                "item": {"type": "string", "description": "За что: «сумки», «мебель», «женская обувь»."},
                "quantity": {"type": "number", "description": "Количество. «четыре места» = 4."},
                "unit": {"type": "string", "description": "Единица: «мест», «шт», «кг»."},
                "happened_on": dict(_DATE, description="Когда операция произошла (ГГГГ-ММ-ДД). «Сегодня» — сегодняшняя дата."),
                "due_date": dict(_DATE, description="Срок, к которому нужно отдать/получить. «Через 10 дней» — посчитай дату."),
                "note": {"type": "string", "description": "Короткое уточнение, если что-то важное не влезло в поля."},
                "raw_text": {"type": "string", "description": "Точные слова пользователя об этой операции."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_transactions",
        "description": (
            "Найти сохранённые операции и получить их полный список с итогами по валютам. "
            "Вызывай на любой вопрос о прошлом: «когда я отправил X», «какие деньги я отправил X», "
            "«сколько я оплатил за сумки». "
            "В text клади ТОЛЬКО ключевые слова предмета («сумки», «женская обувь»), "
            "а не весь вопрос целиком — иначе найдётся лишнее. "
            "Имя человека клади в counterparty, а не в text. "
            "Если ничего не нашлось — попробуй ещё раз с другим написанием имени "
            "(распознавание речи часто искажает имена) или без фильтров."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Ключевые слова о товаре или услуге."},
                "counterparty": {"type": "string", "description": "Имя человека или организации."},
                "date_from": dict(_DATE, description="Начало периода (ГГГГ-ММ-ДД)."),
                "date_to": dict(_DATE, description="Конец периода (ГГГГ-ММ-ДД)."),
                "direction": _DIRECTION,
                "kind": _KIND,
                "limit": {"type": "integer", "description": "Максимум записей, по умолчанию 60."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_transaction",
        "description": (
            "Исправить уже сохранённую операцию. Вызывай, когда пользователь поправляет себя: "
            "«там было не 500, а 400 тысяч», «это был не Абубакр, а Салим». "
            "Если не знаешь id — сначала найди запись через search_transactions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "integer", "description": "id операции."},
                "direction": _DIRECTION,
                "kind": _KIND,
                "counterparty": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "item": {"type": "string"},
                "quantity": {"type": "number"},
                "unit": {"type": "string"},
                "happened_on": _DATE,
                "due_date": _DATE,
                "note": {"type": "string"},
            },
            "required": ["transaction_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "delete_transaction",
        "description": "Удалить ошибочную операцию. Вызывай только при явной просьбе удалить.",
        "input_schema": {
            "type": "object",
            "properties": {"transaction_id": {"type": "integer"}},
            "required": ["transaction_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "describe_document",
        "description": (
            "Подписать загруженное фото: что это за документ и к какому товару он относится. "
            "Вызывай, когда в контексте есть неподписанное фото, а пользователь говорит, что это: "
            "«это накладная от женской обуви», «это чек за мебель». "
            "В description пиши так, чтобы потом легко было найти по словам: тип документа и товар."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "integer", "description": "id фото из контекста."},
                "description": {"type": "string", "description": "Например: «накладная на женскую обувь, 4 места»."},
                "doc_kind": {"type": "string", "description": "накладная, чек, договор, квитанция, фото."},
                "transaction_id": {"type": "integer", "description": "id операции, к которой относится документ, если понятно."},
            },
            "required": ["document_id", "description"],
            "additionalProperties": False,
        },
    },
    {
        "name": "find_documents",
        "description": (
            "Найти сохранённые фото документов по описанию: «накладная от женской обуви», «чек за мебель». "
            "В text клади ключевые слова товара и тип документа."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "date_from": _DATE,
                "date_to": _DATE,
                "limit": {"type": "integer"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "send_documents",
        "description": (
            "Отправить пользователю найденные фото. Вызывай сразу после find_documents, "
            "когда пользователь просит прислать накладную или чек. "
            "Сами файлы уйдут пользователю автоматически — в ответе просто скажи, что отправляешь."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "document_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "id фото из результата find_documents.",
                }
            },
            "required": ["document_ids"],
            "additionalProperties": False,
        },
    },
    {
        "name": "build_report",
        "description": (
            "Построить PDF-отчёт за период и отправить его пользователю файлом. "
            "Вызывай на просьбы «дай отчёт с … по …», «сколько я потратил за месяц в PDF». "
            "Файл уйдёт автоматически — в ответе кратко назови итоги."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": dict(_DATE, description="Начало периода, обязательно."),
                "date_to": dict(_DATE, description="Конец периода, обязательно."),
                "counterparty": {"type": "string", "description": "Ограничить одним человеком."},
                "direction": _DIRECTION,
                "text": {"type": "string", "description": "Ограничить товаром или услугой."},
            },
            "required": ["date_from", "date_to"],
            "additionalProperties": False,
        },
    },
]
