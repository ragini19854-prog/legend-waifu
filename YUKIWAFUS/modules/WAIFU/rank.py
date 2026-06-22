import html

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    Message,
)

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import (
    balancedb,
    collectiondb,
    chatsdb,
    game_statsdb,
)
from YUKIWAFUS.utils.helpers import sc
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled, edit_styled_caption

TOP_LIMIT = 10
MEDALS    = ["🥇", "🥈", "🥉"]

TAB_WAIFUS   = "waifus"
TAB_COINS    = "coins"
TAB_GUESSERS = "guessers"
TAB_GROUPS   = "groups"


def _medal(i: int) -> str:
    return MEDALS[i] if i < 3 else f"<b>{i + 1}.</b>"


async def _fetch_waifus() -> str:
    pipeline = [
        {"$project": {"user_id": 1, "first_name": 1, "waifu_count": {"$size": {"$ifNull": ["$waifus", []]}}}},
        {"$sort":  {"waifu_count": -1}},
        {"$limit": TOP_LIMIT},
    ]
    data = await collectiondb.aggregate(pipeline).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>"
        f"<emoji id='6291837599254322363'>🌸</emoji> "
        f"<b>{sc('Top Waifu Collectors')}</b>"
        f"</blockquote>\n\n"
    )
    if not data:
        return text + f"<i>{sc('No data yet')}~</i>"

    for i, doc in enumerate(data):
        uid   = doc.get("user_id", 0)
        name  = html.escape(doc.get("first_name", str(uid)))[:18]
        count = doc.get("waifu_count", 0)
        text += f"{_medal(i)} <a href='tg://user?id={uid}'><b>{name}</b></a> — {count} 🌸\n"

    return text


async def _fetch_coins() -> str:
    data = await balancedb.find({}, {"user_id": 1, "coins": 1}).sort("coins", -1).limit(TOP_LIMIT).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>🪙 <b>{sc('Top Sakura Holders')}</b></blockquote>\n\n"
    )
    if not data:
        return text + f"<i>{sc('No data yet')}~</i>"

    for i, doc in enumerate(data):
        uid     = doc.get("user_id", 0)
        coins   = doc.get("coins", 0)
        col_doc = await collectiondb.find_one({"user_id": uid}, {"first_name": 1})
        name    = html.escape(col_doc.get("first_name", str(uid)) if col_doc else str(uid))[:18]
        text   += f"{_medal(i)} <a href='tg://user?id={uid}'><b>{name}</b></a> — {coins:,} 🪙\n"

    return text


async def _fetch_guessers() -> str:
    data = await game_statsdb.find({}, {"user_id": 1, "total_guesses": 1}).sort("total_guesses", -1).limit(TOP_LIMIT).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>🎯 <b>{sc('Top Guessers')}</b></blockquote>\n\n"
    )
    if not data:
        return text + f"<i>{sc('No data yet')}~</i>"

    for i, doc in enumerate(data):
        uid     = doc.get("user_id", 0)
        guesses = doc.get("total_guesses", 0)
        col_doc = await collectiondb.find_one({"user_id": uid}, {"first_name": 1})
        name    = html.escape(col_doc.get("first_name", str(uid)) if col_doc else str(uid))[:18]
        text   += f"{_medal(i)} <a href='tg://user?id={uid}'><b>{name}</b></a> — {guesses} 🎯\n"

    return text


async def _fetch_groups() -> str:
    data = await chatsdb.find(
        {"guess_count": {"$exists": True, "$gt": 0}},
        {"chat_id": 1, "title": 1, "guess_count": 1},
    ).sort("guess_count", -1).limit(TOP_LIMIT).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>🏘 <b>{sc('Top Groups')}</b></blockquote>\n\n"
    )
    if not data:
        return text + f"<i>{sc('Groups ranked after first correct guess')}~</i>"

    for i, doc in enumerate(data):
        name  = html.escape(doc.get("title", "Group"))[:20]
        count = doc.get("guess_count", 0)
        text += f"{_medal(i)} <b>{name}</b> — {count} 🎯\n"

    return text


_TAB_FETCH = {
    TAB_WAIFUS:   _fetch_waifus,
    TAB_COINS:    _fetch_coins,
    TAB_GUESSERS: _fetch_guessers,
    TAB_GROUPS:   _fetch_groups,
}


def _build_raw_kb(active: str) -> list:
    def _b(label: str, tab: str) -> dict:
        prefix = "• " if tab == active else ""
        styles = {TAB_WAIFUS: "success", TAB_COINS: "primary", TAB_GUESSERS: "danger", TAB_GROUPS: "primary"}
        emojis = {TAB_WAIFUS: "6291837599254322363", TAB_COINS: "6001483331709966655", TAB_GUESSERS: "6294063539069917326", TAB_GROUPS: "6291835288561917135"}
        return btn(f"{prefix}{label}", callback_data=f"rank:{tab}", style=styles[tab], emoji_id=emojis[tab])

    return [
        row(_b("🌸 ᴡᴀɪғᴜs",   TAB_WAIFUS),   _b("🪙 ᴄᴏɪɴs",    TAB_COINS)),
        row(_b("🎯 ɢᴜᴇssᴇʀs", TAB_GUESSERS), _b("🏘 ɢʀᴏᴜᴘs",   TAB_GROUPS)),
    ]


@app.on_message(filters.command(["rank", "leaderboard", "top", "lb"]))
async def rank_cmd(client: Client, message: Message):
    loading = await message.reply_text(
        f"<blockquote>⏳ <b>{sc('Loading leaderboard')}...</b></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    text   = await _fetch_waifus()
    raw_kb = _build_raw_kb(TAB_WAIFUS)

    await loading.delete()

    msg = await message.reply_photo(
        photo        = config.WAIFU_PICS[0],
        caption      = text,
        parse_mode   = enums.ParseMode.HTML,
        reply_markup = to_pyrogram(raw_kb),
        has_spoiler  = True,
    )
    await inject_styled(msg.chat.id, msg.id, raw_kb)


@app.on_callback_query(filters.regex(r"^rank:(\w+)$"))
async def rank_tab_cb(client: Client, cq: CallbackQuery):
    tab   = cq.data.split(":")[1]
    fetch = _TAB_FETCH.get(tab)
    if not fetch:
        return await cq.answer()

    await cq.answer(f"⏳ {sc('Loading')}...")

    text   = await fetch()
    raw_kb = _build_raw_kb(tab)

    await edit_styled_caption(cq.message.chat.id, cq.message.id, text, raw_kb)


@app.on_message(filters.command("ctop") & filters.group)
async def ctop_cmd(client: Client, message: Message):
    chat_id = message.chat.id

    data = await game_statsdb.find(
        {}, {"user_id": 1, "total_guesses": 1}
    ).sort("total_guesses", -1).limit(TOP_LIMIT).to_list(TOP_LIMIT)

    text = (
        f"<blockquote>"
        f"🎯 <b>{sc('Group Top Guessers')}</b>\n"
        f"<b>{html.escape(message.chat.title or '')}</b>"
        f"</blockquote>\n\n"
    )

    if not data:
        text += f"<i>{sc('No guesses yet in this group')}~</i>"
    else:
        for i, doc in enumerate(data):
            uid     = doc.get("user_id", 0)
            guesses = doc.get("total_guesses", 0)
            col_doc = await collectiondb.find_one({"user_id": uid}, {"first_name": 1})
            name    = html.escape(col_doc.get("first_name", str(uid)) if col_doc else str(uid))[:18]
            text   += f"{_medal(i)} <a href='tg://user?id={uid}'><b>{name}</b></a> — {guesses} 🎯\n"

    await message.reply_photo(
        photo       = config.WAIFU_PICS[0],
        caption     = text,
        parse_mode  = enums.ParseMode.HTML,
        has_spoiler = True,
    )
