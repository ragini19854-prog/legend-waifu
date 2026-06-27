"""
Inline query handler.

col.<user_id>          → user's harem (photo if HTTP URL, text card otherwise)
col.<user_id> <search> → filtered harem
<name>                 → global waifu search
(empty)                → browse global pool
"""
from html import escape

from cachetools import TTLCache
from pyrogram import Client, enums
from pyrogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InputTextMessageContent,
)

from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb
from YUKIWAFUS.logging import LOGGER
from YUKIWAFUS.utils.api import find_waifu, get_waifu_list
from YUKIWAFUS.utils.rarity import rarity_emoji

log = LOGGER(__name__)

RESULTS_PER_PAGE = 30
CACHE_TTL_GLOBAL = 120
CACHE_TTL_USER   = 30
CACHE_TTL_NAME   = 300          # cache owner display names 5 min

_global_cache: TTLCache = TTLCache(maxsize=500,  ttl=CACHE_TTL_GLOBAL)
_user_cache:   TTLCache = TTLCache(maxsize=5000, ttl=CACHE_TTL_USER)
_name_cache:   TTLCache = TTLCache(maxsize=5000, ttl=CACHE_TTL_NAME)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_user_waifus(user_id: int) -> list:
    key = f"u:{user_id}"
    if key in _user_cache:
        return _user_cache[key]
    doc    = await collectiondb.find_one({"user_id": user_id})
    waifus = doc.get("waifus", []) if doc else []
    _user_cache[key] = waifus
    return waifus


async def _get_owner_name(client: Client, user_id: int) -> str:
    """Return display name for owner — cached, never blocks the inline window."""
    key = f"name:{user_id}"
    if key in _name_cache:
        return _name_cache[key]
    # Try to pull the name from the collection doc first (no extra API call)
    doc  = await collectiondb.find_one({"user_id": user_id}, {"first_name": 1})
    name = (doc or {}).get("first_name", "") if doc else ""
    if not name:
        name = "User"
    _name_cache[key] = name
    return name


async def _search_global(name: str) -> list:
    key = f"g:{name.lower()}"
    if key in _global_cache:
        return _global_cache[key]
    results = await find_waifu(name) or []
    _global_cache[key] = results
    return results


async def _get_all_global() -> list:
    key = "g:all"
    if key in _global_cache:
        return _global_cache[key]
    results = await get_waifu_list(skip=0, limit=100) or []
    _global_cache[key] = results
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_http(url: str | None) -> bool:
    if not url:
        return False
    return url.startswith("http://") or url.startswith("https://")


def _dedupe_count(waifus: list) -> tuple[list, dict]:
    seen   = {}
    counts = {}
    for w in waifus:
        wid = w.get("waifu_id") or w.get("name", "")
        counts[wid] = counts.get(wid, 0) + 1
        if wid not in seen:
            seen[wid] = w
    return list(seen.values()), counts


def _collection_caption(waifu: dict, owner_name: str, count: int) -> str:
    r        = waifu.get("rarity", "Common")
    emoji    = rarity_emoji(r)
    waifu_id = waifu.get("waifu_id", "N/A")
    anime    = waifu.get("anime_name") or waifu.get("event_tag", "Standard")
    return (
        f"<blockquote><b>🌸 {escape(owner_name)}'s Collection</b></blockquote>\n\n"
        f"<b>📛 Name :</b> {escape(waifu.get('name', '?'))}\n"
        f"<b>{emoji} Rarity :</b> {r}\n"
        f"<b>🎌 Anime :</b> {escape(anime)}\n"
        f"<b>🆔 ID :</b> <code>{waifu_id}</code>\n"
        f"<b>✖ Count :</b> ×{count}"
    )


def _global_caption(waifu: dict) -> str:
    r        = waifu.get("rarity", "Common")
    emoji    = rarity_emoji(r)
    waifu_id = waifu.get("waifu_id", "N/A")
    anime    = waifu.get("anime_name") or waifu.get("event_tag", "Standard")
    return (
        f"<blockquote><b>🌸 Waifu Info</b></blockquote>\n\n"
        f"<b>📛 Name :</b> {escape(waifu.get('name', '?'))}\n"
        f"<b>{emoji} Rarity :</b> {r}\n"
        f"<b>🎌 Anime :</b> {escape(anime)}\n"
        f"<b>🆔 ID :</b> <code>{waifu_id}</code>"
    )


def _article(title: str, body: str, description: str = "") -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(
            body, parse_mode=enums.ParseMode.HTML
        ),
    )


def _empty_article(hint: str = "Type a name to search, or use the 🔍 button in /harem") -> list:
    return [_article("🌸 Search waifus...", "<blockquote><b>🌸 Use inline search to find waifus!</b></blockquote>", hint)]


def _waifu_to_result(waifu: dict, caption: str, desc: str) -> InlineQueryResultPhoto | InlineQueryResultArticle:
    """Return photo result if img_url is a public HTTP URL, text card otherwise."""
    url = waifu.get("img_url", "")
    if _is_http(url):
        return InlineQueryResultPhoto(
            photo_url=url,
            thumb_url=url,
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
            title=waifu.get("name", "?"),
            description=desc,
        )
    # Telegram file_id or missing URL → text card so the waifu still shows up
    return _article(
        title=waifu.get("name", "?"),
        body=caption,
        description=desc,
    )


# ── Main handler ──────────────────────────────────────────────────────────────

@app.on_inline_query()
async def inline_handler(client: Client, query: InlineQuery):
    raw     = query.query.strip()
    offset  = int(query.offset) if query.offset else 0
    results = []
    next_offset = ""

    try:
        # ── col.<user_id> [search] → user harem ──────────────────────────────
        if raw.startswith("col."):
            parts      = raw.split(" ", 1)
            uid_part   = parts[0][4:]
            search_str = parts[1].lower() if len(parts) > 1 else ""

            if not uid_part.lstrip("-").isdigit():
                return await query.answer(_empty_article("Invalid harem link."), cache_time=5)

            user_id    = int(uid_part)
            all_waifus = await _get_user_waifus(user_id)

            if not all_waifus:
                return await query.answer(
                    _empty_article("This user has no waifus yet!"), cache_time=10
                )

            if search_str:
                all_waifus = [
                    w for w in all_waifus
                    if search_str in w.get("name", "").lower()
                    or search_str in w.get("rarity", "").lower()
                    or search_str in (w.get("anime_name") or w.get("event_tag", "")).lower()
                ]

            unique, counts = _dedupe_count(all_waifus)
            page        = unique[offset: offset + RESULTS_PER_PAGE]
            next_offset = str(offset + len(page)) if len(page) == RESULTS_PER_PAGE else ""

            # Owner name from DB — no extra Telegram API call
            owner_name = await _get_owner_name(client, user_id)

            for w in page:
                wid     = w.get("waifu_id") or w.get("name", "")
                count   = counts.get(wid, 1)
                caption = _collection_caption(w, owner_name, count)
                r       = w.get("rarity", "")
                desc    = f"{rarity_emoji(r)} {r} · ×{count}"
                results.append(_waifu_to_result(w, caption, desc))

            if not results and offset == 0:
                results = _empty_article("No waifus found in this collection.")

        # ── non-empty query → global search ──────────────────────────────────
        elif raw:
            waifus      = await _search_global(raw)
            # Filter to HTTP URLs first so pagination offsets are correct
            valid       = [w for w in waifus if _is_http(w.get("img_url"))]
            page        = valid[offset: offset + RESULTS_PER_PAGE]
            next_offset = str(offset + len(page)) if len(page) == RESULTS_PER_PAGE else ""

            for w in page:
                caption = _global_caption(w)
                r       = w.get("rarity", "")
                anime   = w.get("anime_name") or w.get("event_tag", "Standard")
                desc    = f"{rarity_emoji(r)} {r} · {anime}"
                results.append(_waifu_to_result(w, caption, desc))

            if not results and offset == 0:
                results = _empty_article(f'No results for "{raw}".')

        # ── empty query → browse global pool ─────────────────────────────────
        else:
            waifus      = await _get_all_global()
            valid       = [w for w in waifus if _is_http(w.get("img_url"))]
            page        = valid[offset: offset + RESULTS_PER_PAGE]
            next_offset = str(offset + len(page)) if len(page) == RESULTS_PER_PAGE else ""

            for w in page:
                caption = _global_caption(w)
                r       = w.get("rarity", "")
                desc    = f"{rarity_emoji(r)} {r}"
                results.append(_waifu_to_result(w, caption, desc))

            if not results and offset == 0:
                results = _empty_article()

        await query.answer(
            results,
            cache_time=5,
            next_offset=next_offset,
            is_personal=raw.startswith("col."),
        )

    except Exception as exc:
        log.error(f"inline_handler error query={raw!r}: {exc}", exc_info=True)
        try:
            await query.answer(_empty_article(), cache_time=5)
        except Exception:
            pass
