import time
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

RESULTS_PER_PAGE  = 30
CACHE_TTL_GLOBAL  = 120
CACHE_TTL_USER    = 30

_global_cache: TTLCache = TTLCache(maxsize=500,  ttl=CACHE_TTL_GLOBAL)
_user_cache:   TTLCache = TTLCache(maxsize=5000, ttl=CACHE_TTL_USER)


async def _get_user_waifus(user_id: int) -> list:
    key = f"u:{user_id}"
    if key in _user_cache:
        return _user_cache[key]
    doc = await collectiondb.find_one({"user_id": user_id})
    waifus = doc.get("waifus", []) if doc else []
    _user_cache[key] = waifus
    return waifus


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


def _is_valid_url(url: str | None) -> bool:
    """Only HTTP(S) URLs are accepted by Telegram for inline photo results."""
    if not url:
        return False
    return url.startswith("http://") or url.startswith("https://")


def _build_collection_caption(waifu: dict, owner_name: str, count: int) -> str:
    r        = waifu.get("rarity", "Common")
    emoji    = rarity_emoji(r)
    waifu_id = waifu.get("waifu_id", "N/A")
    anime    = waifu.get("anime_name") or waifu.get("event_tag", "Standard")
    return (
        f"<blockquote>"
        f"<b>🌸 {escape(owner_name)}'s Collection</b>"
        f"</blockquote>\n\n"
        f"<b>📛 Name :</b> {escape(waifu.get('name', '?'))}\n"
        f"<b>{emoji} Rarity :</b> {r}\n"
        f"<b>🎌 Anime :</b> {escape(anime)}\n"
        f"<b>🆔 ID :</b> <code>{waifu_id}</code>\n"
        f"<b>✖ Count :</b> ×{count}"
    )


def _build_global_caption(waifu: dict) -> str:
    r        = waifu.get("rarity", "Common")
    emoji    = rarity_emoji(r)
    waifu_id = waifu.get("waifu_id", "N/A")
    anime    = waifu.get("anime_name") or waifu.get("event_tag", "Standard")
    return (
        f"<blockquote>"
        f"<b>🌸 Waifu Info</b>"
        f"</blockquote>\n\n"
        f"<b>📛 Name :</b> {escape(waifu.get('name', '?'))}\n"
        f"<b>{emoji} Rarity :</b> {r}\n"
        f"<b>🎌 Anime :</b> {escape(anime)}\n"
        f"<b>🆔 ID :</b> <code>{waifu_id}</code>"
    )


def _dedupe_count(waifus: list) -> tuple[list, dict]:
    seen   = {}
    counts = {}
    for w in waifus:
        wid = w.get("waifu_id") or w.get("name", "")
        counts[wid] = counts.get(wid, 0) + 1
        if wid not in seen:
            seen[wid] = w
    return list(seen.values()), counts


def _empty_result(hint: str = "") -> list:
    desc = hint or "Type a name to search globally, or use col.<user_id> for a collection"
    return [
        InlineQueryResultArticle(
            title="🌸 Search waifus...",
            description=desc,
            input_message_content=InputTextMessageContent(
                "<blockquote><b>🌸 Use inline search to find waifus!</b></blockquote>",
                parse_mode=enums.ParseMode.HTML,
            ),
        )
    ]


@app.on_inline_query()
async def inline_handler(client: Client, query: InlineQuery):
    raw     = query.query.strip()
    offset  = int(query.offset) if query.offset else 0
    results = []
    next_offset = ""

    try:
        # ── col.<user_id> [optional search] → user's harem ───────────────────
        if raw.startswith("col."):
            parts      = raw.split(" ", 1)
            uid_part   = parts[0][4:]
            search_str = parts[1].lower() if len(parts) > 1 else ""

            if not uid_part.lstrip("-").isdigit():
                return await query.answer(_empty_result("Invalid harem link."), cache_time=5)

            user_id    = int(uid_part)
            all_waifus = await _get_user_waifus(user_id)

            if not all_waifus:
                return await query.answer(
                    _empty_result("This user has no waifus yet!"), cache_time=10
                )

            if search_str:
                all_waifus = [
                    w for w in all_waifus
                    if search_str in w.get("name", "").lower()
                    or search_str in w.get("rarity", "").lower()
                    or search_str in (w.get("anime_name") or w.get("event_tag", "")).lower()
                ]

            unique, counts = _dedupe_count(all_waifus)

            # Only include waifus with a valid public HTTP URL in inline results
            # (Telegram file_ids are served by spawns/harem, not inline queries)
            # Filter FIRST, then paginate so offsets are correct
            url_valid   = [w for w in unique if _is_valid_url(w.get("img_url"))]
            page        = url_valid[offset: offset + RESULTS_PER_PAGE]
            next_offset = str(offset + len(page)) if len(page) == RESULTS_PER_PAGE else ""

            try:
                user       = await client.get_users(user_id)
                owner_name = user.first_name
            except Exception:
                owner_name = "User"

            for w in page:
                wid     = w.get("waifu_id") or w.get("name", "")
                count   = counts.get(wid, 1)
                caption = _build_collection_caption(w, owner_name, count)
                results.append(
                    InlineQueryResultPhoto(
                        photo_url=w["img_url"],
                        thumb_url=w["img_url"],
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        title=w.get("name", "?"),
                        description=f"{w.get('rarity', '')} · ×{count}",
                    )
                )

            if not results and offset == 0:
                results     = _empty_result("No waifus with shareable images in this collection.")
                next_offset = ""

        # ── non-empty query → global search ──────────────────────────────────
        elif raw:
            waifus      = await _search_global(raw)
            # Filter valid HTTP URLs FIRST, then paginate
            valid       = [w for w in waifus if _is_valid_url(w.get("img_url"))]
            page        = valid[offset: offset + RESULTS_PER_PAGE]
            next_offset = str(offset + len(page)) if len(page) == RESULTS_PER_PAGE else ""

            for w in page:
                caption = _build_global_caption(w)
                r       = w.get("rarity", "")
                results.append(
                    InlineQueryResultPhoto(
                        photo_url=w["img_url"],
                        thumb_url=w["img_url"],
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        title=w.get("name", "?"),
                        description=f"{rarity_emoji(r)} {r} · {w.get('anime_name') or w.get('event_tag', 'Standard')}",
                    )
                )

            if not results and offset == 0:
                results     = _empty_result(f'No results for "{raw}".')
                next_offset = ""

        # ── empty query → browse global pool ─────────────────────────────────
        else:
            waifus      = await _get_all_global()
            # Filter valid HTTP URLs FIRST, then paginate
            valid       = [w for w in waifus if _is_valid_url(w.get("img_url"))]
            page        = valid[offset: offset + RESULTS_PER_PAGE]
            next_offset = str(offset + len(page)) if len(page) == RESULTS_PER_PAGE else ""

            for w in page:
                caption = _build_global_caption(w)
                r       = w.get("rarity", "")
                results.append(
                    InlineQueryResultPhoto(
                        photo_url=w["img_url"],
                        thumb_url=w["img_url"],
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        title=w.get("name", "?"),
                        description=f"{rarity_emoji(r)} {r}",
                    )
                )

            if not results and offset == 0:
                results     = _empty_result()
                next_offset = ""

        await query.answer(
            results,
            cache_time=5,
            next_offset=next_offset,
            is_personal=raw.startswith("col."),
        )

    except Exception as exc:
        log.error(f"inline_handler error for query={raw!r}: {exc}", exc_info=True)
        try:
            await query.answer(_empty_result(), cache_time=5)
        except Exception:
            pass
