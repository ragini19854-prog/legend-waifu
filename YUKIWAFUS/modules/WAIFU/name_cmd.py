"""
/name command — identify a spawned waifu from its message.

Usage: Reply to a waifu spawn message with /name

Free tier : 1 use per day
Paid tier  : 100 coins per extra use   OR   1 500 coins for 15 uses/day (premium)
"""
import time
from datetime import datetime, timezone
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import namedb, balancedb
from YUKIWAFUS.utils.rarity import rarity_emoji
from YUKIWAFUS.utils.helpers import sc

FREE_DAILY      = 1        # free /name uses per day
PREMIUM_USES    = 15       # uses per day in premium pack
PREMIUM_COST    = 1500     # coins for the premium pack (daily)
COIN_PER_EXTRA  = 100      # coins per extra use outside premium


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _get_usage(user_id: int) -> dict:
    doc = await namedb.find_one({"user_id": user_id})
    if not doc or doc.get("date") != _today_key():
        return {"free_used": 0, "premium_uses": 0, "date": _today_key()}
    return doc


async def _save_usage(user_id: int, doc: dict):
    await namedb.update_one(
        {"user_id": user_id},
        {"$set": {**doc, "user_id": user_id}},
        upsert=True,
    )


async def _coins(user_id: int) -> int:
    doc = await balancedb.find_one({"user_id": user_id})
    return (doc or {}).get("coins", 0)


async def _deduct(user_id: int, amount: int) -> int:
    doc = await balancedb.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"coins": -amount}},
        upsert=True,
        return_document=True,
    )
    return (doc or {}).get("coins", 0)


async def _add_coins(user_id: int, amount: int) -> int:
    doc = await balancedb.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"coins": amount}},
        upsert=True,
        return_document=True,
    )
    return (doc or {}).get("coins", 0)


def _waifu_detail_text(waifu: dict) -> str:
    name      = waifu.get("name", "?")
    anime     = waifu.get("anime_name") or waifu.get("event_tag", "Standard")
    rarity    = waifu.get("rarity", "Common")
    emoji     = rarity_emoji(rarity)
    waifu_id  = waifu.get("waifu_id", "N/A")
    return (
        f"<blockquote>"
        f"🔍 <b>Waifu Identified!</b>"
        f"</blockquote>\n\n"
        f"<b>📛 Name</b>\n"
        f"<code>{escape(name)}</code>\n\n"
        f"<b>🎌 Anime</b>\n"
        f"<code>{escape(anime)}</code>\n\n"
        f"<b>{emoji} Rarity :</b> {rarity}\n"
        f"<b>🆔 ID :</b> <code>{waifu_id}</code>\n\n"
        f"<i>Tap on the name or anime to copy it!</i>"
    )


@app.on_message(filters.command("name"))
async def name_handler(client: Client, message: Message):
    user    = message.from_user
    user_id = user.id

    # ── Must reply to a waifu spawn message ──────────────────────────────────
    if not message.reply_to_message:
        return await message.reply_text(
            "<blockquote>"
            "⚠️ <b>Usage:</b> Reply to a spawned waifu message with /name"
            "</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    replied_msg = message.reply_to_message
    chat_id     = message.chat.id
    msg_id      = replied_msg.id

    # Look up waifu in the spawn message map
    from YUKIWAFUS.modules.WAIFU.spawn import spawn_message_map
    waifu = spawn_message_map.get((chat_id, msg_id))

    if not waifu:
        return await message.reply_text(
            "<blockquote>"
            "❌ <b>Waifu not found!</b>\n"
            "This doesn't seem to be a waifu spawn message, or it has expired."
            "</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    # ── Check daily usage ─────────────────────────────────────────────────────
    usage = await _get_usage(user_id)

    if usage["free_used"] < FREE_DAILY:
        # Free use
        usage["free_used"] += 1
        await _save_usage(user_id, usage)
        detail = _waifu_detail_text(waifu)
        return await message.reply_text(
            detail + f"\n\n<i>🆓 Free use today: {usage['free_used']}/{FREE_DAILY}</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    if usage.get("premium_uses", 0) > 0:
        # Premium use
        usage["premium_uses"] -= 1
        await _save_usage(user_id, usage)
        detail = _waifu_detail_text(waifu)
        return await message.reply_text(
            detail + f"\n\n<i>💎 Premium uses left today: {usage['premium_uses']}</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    # ── Out of free + premium — offer options ─────────────────────────────────
    bal = await _coins(user_id)
    mention = f"<a href='tg://user?id={user_id}'>{escape(user.first_name)}</a>"
    return await message.reply_text(
        f"<blockquote>"
        f"💰 <b>Daily /name limit reached!</b>"
        f"</blockquote>\n\n"
        f"You've used your <b>{FREE_DAILY} free</b> /name today.\n\n"
        f"<b>Options:</b>\n"
        f"  • <code>/namepay</code> — spend <b>{COIN_PER_EXTRA} 🌸</b> for 1 extra use\n"
        f"  • <code>/namepremium</code> — spend <b>{PREMIUM_COST} 🌸</b> for {PREMIUM_USES} uses today\n\n"
        f"<b>Your balance:</b> {bal:,} 🌸",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(filters.command("namepay"))
async def namepay_handler(client: Client, message: Message):
    """Pay COIN_PER_EXTRA coins for one extra /name use."""
    user_id = message.from_user.id

    if not message.reply_to_message:
        return await message.reply_text(
            "⚠️ Reply to a waifu spawn message with /namepay",
            parse_mode=enums.ParseMode.HTML,
        )

    replied_msg = message.reply_to_message
    chat_id     = message.chat.id
    msg_id      = replied_msg.id

    from YUKIWAFUS.modules.WAIFU.spawn import spawn_message_map
    waifu = spawn_message_map.get((chat_id, msg_id))
    if not waifu:
        return await message.reply_text("❌ Waifu not found or expired.")

    bal = await _coins(user_id)
    if bal < COIN_PER_EXTRA:
        return await message.reply_text(
            f"❌ Not enough coins! You need <b>{COIN_PER_EXTRA} 🌸</b> but have <b>{bal:,} 🌸</b>.",
            parse_mode=enums.ParseMode.HTML,
        )

    await _deduct(user_id, COIN_PER_EXTRA)
    detail = _waifu_detail_text(waifu)
    await message.reply_text(
        detail + f"\n\n<i>💰 Spent {COIN_PER_EXTRA} 🌸 · Balance: {bal - COIN_PER_EXTRA:,} 🌸</i>",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(filters.command("namepremium"))
async def namepremium_handler(client: Client, message: Message):
    """Buy a premium /name pack: PREMIUM_USES uses for PREMIUM_COST coins."""
    user_id = message.from_user.id
    bal     = await _coins(user_id)

    if bal < PREMIUM_COST:
        return await message.reply_text(
            f"❌ Not enough coins!\n"
            f"Premium pack costs <b>{PREMIUM_COST:,} 🌸</b> for <b>{PREMIUM_USES} uses/day</b>.\n"
            f"Your balance: <b>{bal:,} 🌸</b>",
            parse_mode=enums.ParseMode.HTML,
        )

    usage = await _get_usage(user_id)
    usage["premium_uses"] = usage.get("premium_uses", 0) + PREMIUM_USES
    await _save_usage(user_id, usage)
    await _deduct(user_id, PREMIUM_COST)

    await message.reply_text(
        f"✅ <b>Premium /name pack activated!</b>\n\n"
        f"💎 <b>{PREMIUM_USES} extra /name uses</b> added for today.\n"
        f"💰 Spent: <b>{PREMIUM_COST:,} 🌸</b> · Balance: <b>{bal - PREMIUM_COST:,} 🌸</b>",
        parse_mode=enums.ParseMode.HTML,
    )
