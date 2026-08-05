"""
Minimal Zadarma API client (https://zadarma.com/en/support/api/).
Auth scheme: Authorization: <key>:<signature>, where
  signature = base64(hmac_sha1(secret, path + sorted_params_string + md5(sorted_params_string)))
"""

import base64
import hashlib
import hmac
from urllib.parse import urlencode

import requests
from django.conf import settings


class ZadarmaError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.ZADARMA_API_KEY and settings.ZADARMA_API_SECRET)


def _signature(path: str, params: dict, secret: str) -> str:
    sorted_params = dict(sorted(params.items()))
    params_string = urlencode(sorted_params)
    md5_hash = hashlib.md5(params_string.encode()).hexdigest()
    auth_string = f"{path}{params_string}{md5_hash}"
    digest = hmac.new(secret.encode(), auth_string.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def request(path: str, params: dict | None = None, method: str = "GET") -> dict:
    if not is_configured():
        raise ZadarmaError("zadarma_not_configured")

    params = params or {}
    sign = _signature(path, params, settings.ZADARMA_API_SECRET)
    url = "https://api.zadarma.com" + path
    headers = {"Authorization": f"{settings.ZADARMA_API_KEY}:{sign}"}

    try:
        if method == "GET":
            resp = requests.get(url, params=params, headers=headers, timeout=15)
        else:
            resp = requests.post(url, data=params, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise ZadarmaError(f"zadarma_request_error: {e}") from e

    try:
        return resp.json()
    except ValueError as e:
        raise ZadarmaError(f"zadarma_invalid_response: {resp.text[:200]}") from e


def send_sms(phone_e164: str, message: str) -> bool:
    data = request("/v1/sms/send/", {"number": phone_e164.lstrip("+"), "message": message}, method="POST")
    if data.get("status") != "success":
        raise ZadarmaError(f"zadarma_sms_failed: {data.get('message', 'unknown')}")
    return True
