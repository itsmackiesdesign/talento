"""Thin Telegram Bot API client for control-plane calls (getMe / setWebhook / sendMessage).

Deliberately httpx-based rather than aiogram: these run inside request handlers and Celery
tasks where we want a plain call with an explicit timeout, not a Bot session lifecycle.
aiogram is used where it earns its keep — dispatching updates in ``app/bot``.
"""

from typing import Any

import httpx

API_ROOT = "https://api.telegram.org"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class TelegramError(RuntimeError):
    def __init__(self, description: str, code: int | None = None):
        super().__init__(description)
        self.description = description
        self.code = code


async def call(token: str, method: str, **params: Any) -> Any:
    url = f"{API_ROOT}/bot{token}/{method}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(url, json={k: v for k, v in params.items() if v is not None})
        except httpx.HTTPError as exc:
            # httpx exception strings may contain the request URL, and Telegram puts the
            # bot token inside that URL. Keep the cause for debugging without exposing it.
            raise TelegramError("Could not reach Telegram") from exc
    try:
        body = resp.json()
    except ValueError:
        raise TelegramError(f"Telegram returned a non-JSON response ({resp.status_code})") from None
    if not body.get("ok"):
        raise TelegramError(body.get("description", "Unknown Telegram error"), resp.status_code)
    return body.get("result")


async def get_me(token: str) -> dict[str, Any]:
    return await call(token, "getMe")


async def set_webhook(token: str, url: str, secret_token: str) -> bool:
    return await call(
        token,
        "setWebhook",
        url=url,
        secret_token=secret_token,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


async def delete_webhook(token: str) -> bool:
    return await call(token, "deleteWebhook", drop_pending_updates=True)


async def get_webhook_info(token: str) -> dict[str, Any]:
    return await call(token, "getWebhookInfo")


async def send_message(
    token: str, chat_id: int, text: str, parse_mode: str | None = "HTML", **kw: Any
) -> Any:
    return await call(
        token,
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        disable_web_page_preview=True,
        **kw,
    )


async def send_photo(
    token: str,
    chat_id: int,
    photo: str,
    caption: str,
    parse_mode: str | None = "HTML",
    **kw: Any,
) -> Any:
    """Send a photo by public URL with an optional inline keyboard."""
    return await call(
        token,
        "sendPhoto",
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        parse_mode=parse_mode,
        **kw,
    )


async def get_file_path(token: str, file_id: str) -> str:
    result = await call(token, "getFile", file_id=file_id)
    return result["file_path"]


async def download_file(token: str, file_path: str) -> bytes:
    url = f"{API_ROOT}/file/bot{token}/{file_path}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content
