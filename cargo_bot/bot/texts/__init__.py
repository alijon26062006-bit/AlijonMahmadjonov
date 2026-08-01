"""Тексты интерфейса.

Мультиязычность: тексты хранятся по языкам (ru — основной).
Чтобы добавить таджикский или китайский — создайте tj.py / cn.py
по образцу ru.py и добавьте язык в LEXICONS.
"""
from . import ru

LEXICONS = {"ru": ru.TEXTS}


def t(key: str, lang: str = "ru", **kwargs) -> str:
    lex = LEXICONS.get(lang, LEXICONS["ru"])
    text = lex.get(key) or LEXICONS["ru"].get(key, key)
    return text.format(**kwargs) if kwargs else text
