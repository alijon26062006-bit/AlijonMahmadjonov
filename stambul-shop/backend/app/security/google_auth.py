"""Проверка входа через Google.

Браузер получает от Google `id_token` и присылает его нам. Верить ему на
слово нельзя: токен нужно проверить у самого Google и убедиться, что он
выписан именно нашему приложению, а не чужому сайту с тем же кодом.

Проверяем через официальную точку `tokeninfo`. Разбирать подпись самим
было бы на один сетевой запрос быстрее, но потребовало бы держать у себя
ключи Google и следить за их сменой — на нашем потоке входов это лишнее.
"""
import httpx

from app.config import get_settings

TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleAuthError(Exception):
    pass


async def verify(id_token: str) -> dict:
    s = get_settings()
    if not s.google_client_id:
        raise GoogleAuthError("Вход через Google не настроен")
    if not id_token or len(id_token) > 4096:
        raise GoogleAuthError("Неверный токен Google")

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(TOKENINFO, params={"id_token": id_token})
    except httpx.HTTPError:
        raise GoogleAuthError("Google не отвечает, попробуйте ещё раз") from None
    if response.status_code != 200:
        raise GoogleAuthError("Google не подтвердил вход")

    claims = response.json()
    if claims.get("aud") != s.google_client_id:
        raise GoogleAuthError("Токен выписан другому приложению")
    if claims.get("iss") not in ISSUERS:
        raise GoogleAuthError("Неизвестный издатель токена")
    if not claims.get("sub"):
        raise GoogleAuthError("Google не назвал пользователя")
    # email_verified приходит строкой "true" — сравниваем как есть
    if str(claims.get("email_verified", "")).lower() not in ("true", "1"):
        claims.pop("email", None)
    return claims
