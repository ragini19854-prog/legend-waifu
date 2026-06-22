import aiohttp
import config
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


async def _bot_api(method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/{method}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload) as resp:
                return await resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def btn(
    text: str,
    callback_data: str = None,
    url: str = None,
    switch_current: str = None,
    style: str = None,
    emoji_id: str = None,
) -> dict | None:
    b = {"text": text}
    if callback_data:
        b["callback_data"] = callback_data
    elif switch_current is not None:
        b["switch_inline_query_current_chat"] = switch_current
    elif url:
        u = str(url).strip()
        if not u.startswith(("http", "tg://")):
            u = f"https://t.me/{u.lstrip('@')}"
        if u in ("https://t.me/", "https://t.me", "http://t.me/"):
            return None
        b["url"] = u
    else:
        return None
    if style in ("primary", "success", "danger"):
        b["style"] = style
    if emoji_id:
        b["icon_custom_emoji_id"] = str(emoji_id)
    return b


def row(*buttons) -> list:
    return [b for b in buttons if b is not None]


def to_pyrogram(raw_kb: list) -> InlineKeyboardMarkup | None:
    rows = []
    for raw_row in raw_kb:
        r = []
        for b in raw_row:
            if b.get("callback_data"):
                r.append(InlineKeyboardButton(b["text"], callback_data=b["callback_data"]))
            elif b.get("url"):
                r.append(InlineKeyboardButton(b["text"], url=b["url"]))
            elif b.get("switch_inline_query_current_chat") is not None:
                r.append(InlineKeyboardButton(
                    b["text"],
                    switch_inline_query_current_chat=b["switch_inline_query_current_chat"],
                ))
        if r:
            rows.append(r)
    return InlineKeyboardMarkup(rows) if rows else None


async def inject_styled(chat_id: int, message_id: int, raw_kb: list) -> None:
    if not raw_kb:
        return
    try:
        await _bot_api("editMessageReplyMarkup", {
            "chat_id":      chat_id,
            "message_id":   message_id,
            "reply_markup": {"inline_keyboard": raw_kb},
        })
    except Exception:
        pass


async def edit_styled_caption(
    chat_id: int, message_id: int, caption: str, raw_kb: list
) -> dict:
    return await _bot_api("editMessageCaption", {
        "chat_id":      chat_id,
        "message_id":   message_id,
        "caption":      caption,
        "parse_mode":   "HTML",
        "reply_markup": {"inline_keyboard": raw_kb},
    })


async def edit_styled_text(
    chat_id: int, message_id: int, text: str, raw_kb: list
) -> dict:
    return await _bot_api("editMessageText", {
        "chat_id":      chat_id,
        "message_id":   message_id,
        "text":         text,
        "parse_mode":   "HTML",
        "reply_markup": {"inline_keyboard": raw_kb},
    })


async def edit_styled_markup(
    chat_id: int, message_id: int, raw_kb: list
) -> dict:
    return await _bot_api("editMessageReplyMarkup", {
        "chat_id":      chat_id,
        "message_id":   message_id,
        "reply_markup": {"inline_keyboard": raw_kb},
    })
