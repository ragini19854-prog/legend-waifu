"""
/name command — identify a spawned waifu from its message.

Usage: Reply to a waifu spawn message with /name

Free tier : 1 use per day
Paid tier  : 100 coins per extra use   OR   1 500 coins for 15 uses/day (premium)
"""
from datetime import datetime, timezone
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import namedb, balancedb, premiumdb
from YUKIWAFUS.utils.rarity import rarity_emoji

FREE_DAILY      = 1
PREMIUM_USES    = 15
PREMIUM_COST    = 1500
COIN_PER_EXTRA  = 100

# ── NewsEmoji IDs ─────────────────────────────────────────────────────────────
E_SEARCH   = "5231012545799666522"   # 🔍
E_SPARKLE  = "5325547803936572038"   # ✨
E_STAR     = "5438496463044752972"   # ⭐️
E_FREE     = "5406756500108501710"   # 🆓
E_PREMIUM  = "5427168083074628963"   # 💎
E_WARNING  = "5447644880824181073"   # ⚠️
E_COINS    = "5233326571099534068"   # 💸
E_CROSS    = "5210952531676504517"   # ❌
E_CHECK    = "5206607081334906820"   # ✔️
E_FIRE     = "5424972470023104089"   # 🔥
E_INFO     = "5334544901428229844"   # ℹ️
E_LOCK     = "5296369303661067030"   # 🔒
E_CROWN    = "5217822164362739968"   # 👑


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


def _waifu_detail_text(waifu: dict) -> str:
    name     = waifu.get("name", "?")
    anime    = waifu.get("anime_name") or waifu.get("event_tag", "Standard")
    rarity   = waifu.get("rarity", "Common")
    emoji    = rarity_emoji(rarity)
    waifu_id = waifu.get("waifu_id", "N/A")
    return (
        f"<blockquote>"
        f"<emoji id='{E_SEARCH}'>🔍</emoji> <b>Waifu Identified!</b>"
        f"</blockquote>\n\n"
        f"<emoji id='{E_SPARKLE}'>✨</emoji> <b>Name</b>\n"
        f"<code>{escape(name)}</code>\n\n"
        f"<emoji id='{E_STAR}'>⭐️</emoji> <b>Anime</b>\n"
        f"<code>{escape(anime)}</code>\n\n"
        f"<b>{emoji} Rarity :</b> {rarity}\n"
        f"<b><emoji id='{E_INFO}'>ℹ️</emoji> ID :</b> <code>{waifu_id}</code>\n\n"
        f"<i>Tap the name or anime to copy it!</i>"
    )


async def _active_premium_uses(user_id: int) -> int:
    """Return extra daily uses from owner-granted premium subscription, or 0."""
    from datetime import timezone as _tz
    doc = await premiumdb.find_one({"user_id": user_id})
    if not doc:
        return 0
    exp = doc.get("expires_at")
    if exp:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=_tz.utc)
        from datetime import datetime as _dt
        if _dt.now(_tz.utc) > exp:
            await premiumdb.delete_one({"user_id": user_id})
            return 0
    return int(doc.get("daily_uses", PREMIUM_USES))


@app.on_message(filters.command("name"))
async def name_handler(client: Client, message: Message):
    user    = message.from_user
    user_id = user.id

    if not message.reply_to_message:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{E_WARNING}'>⚠️</emoji> <b>Usage:</b> Reply to a spawned waifu message with /name"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    chat_id = message.chat.id
    msg_id  = message.reply_to_message.id

    from YUKIWAFUS.modules.WAIFU.spawn import spawn_message_map
    waifu = spawn_message_map.get((chat_id, msg_id))

    if not waifu:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{E_CROSS}'>❌</emoji> <b>Waifu not found!</b>\n"
            f"This doesn't seem to be a waifu spawn message, or it has already expired."
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    # ── Owner: unlimited, free forever ───────────────────────────────────────
    if user_id == config.OWNER_ID:
        detail = _waifu_detail_text(waifu)
        return await message.reply_text(
            detail + f"\n\n<emoji id='{E_CROWN}'>👑</emoji> <i>Owner — unlimited access</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    usage = await _get_usage(user_id)

    if usage["free_used"] < FREE_DAILY:
        usage["free_used"] += 1
        await _save_usage(user_id, usage)
        detail = _waifu_detail_text(waifu)
        return await message.reply_text(
            detail + f"\n\n<emoji id='{E_FREE}'>🆓</emoji> <i>Free use today: {usage['free_used']}/{FREE_DAILY}</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    # Check owner-granted premium subscription
    sub_uses = await _active_premium_uses(user_id)
    if sub_uses > 0:
        # Use from subscription pool (just notify, don't decrement — subscription is daily reset)
        detail = _waifu_detail_text(waifu)
        return await message.reply_text(
            detail + f"\n\n<emoji id='{E_PREMIUM}'>💎</emoji> <i>Premium subscription active — {sub_uses} uses/day</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    if usage.get("premium_uses", 0) > 0:
        usage["premium_uses"] -= 1
        await _save_usage(user_id, usage)
        detail = _waifu_detail_text(waifu)
        return await message.reply_text(
            detail + f"\n\n<emoji id='{E_PREMIUM}'>💎</emoji> <i>Premium uses left today: {usage['premium_uses']}</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    bal = await _coins(user_id)
    return await message.reply_text(
        f"<blockquote>"
        f"<emoji id='{E_LOCK}'>🔒</emoji> <b>Daily /name limit reached!</b>"
        f"</blockquote>\n\n"
        f"You've used your <b>{FREE_DAILY} free</b> /name for today.\n\n"
        f"<b><emoji id='{E_INFO}'>ℹ️</emoji> Options:</b>\n"
        f"  • <code>/namepay</code> — <emoji id='{E_COINS}'>💸</emoji> <b>{COIN_PER_EXTRA} 🌸</b> for 1 extra use\n"
        f"  • <code>/namepremium</code> — <emoji id='{E_FIRE}'>🔥</emoji> <b>{PREMIUM_COST:,} 🌸</b> for {PREMIUM_USES} uses today\n\n"
        f"<b>Your balance:</b> {bal:,} 🌸",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(filters.command("namepay"))
async def namepay_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if not message.reply_to_message:
        return await message.reply_text(
            f"<blockquote><emoji id='{E_WARNING}'>⚠️</emoji> Reply to a waifu spawn message with /namepay</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    chat_id = message.chat.id
    msg_id  = message.reply_to_message.id

    from YUKIWAFUS.modules.WAIFU.spawn import spawn_message_map
    waifu = spawn_message_map.get((chat_id, msg_id))
    if not waifu:
        return await message.reply_text(
            f"<blockquote><emoji id='{E_CROSS}'>❌</emoji> Waifu not found or expired.</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    bal = await _coins(user_id)
    if bal < COIN_PER_EXTRA:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{E_CROSS}'>❌</emoji> <b>Not enough coins!</b>\n"
            f"Need <b>{COIN_PER_EXTRA} 🌸</b> · You have <b>{bal:,} 🌸</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    new_bal = await _deduct(user_id, COIN_PER_EXTRA)
    detail  = _waifu_detail_text(waifu)
    await message.reply_text(
        detail + f"\n\n<emoji id='{E_COINS}'>💸</emoji> <i>Spent {COIN_PER_EXTRA} 🌸 · Balance: {new_bal:,} 🌸</i>",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(filters.command("namepremium"))
async def namepremium_handler(client: Client, message: Message):
    user_id = message.from_user.id
    bal     = await _coins(user_id)

    if bal < PREMIUM_COST:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{E_CROSS}'>❌</emoji> <b>Not enough coins!</b>\n"
            f"Premium pack costs <b>{PREMIUM_COST:,} 🌸</b> for <b>{PREMIUM_USES} uses/day</b>.\n"
            f"Your balance: <b>{bal:,} 🌸</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    usage = await _get_usage(user_id)
    usage["premium_uses"] = usage.get("premium_uses", 0) + PREMIUM_USES
    await _save_usage(user_id, usage)
    new_bal = await _deduct(user_id, PREMIUM_COST)

    await message.reply_text(
        f"<blockquote>"
        f"<emoji id='{E_PREMIUM}'>💎</emoji> <b>Premium /name pack activated!</b>"
        f"</blockquote>\n\n"
        f"<emoji id='{E_CHECK}'>✔️</emoji> <b>{PREMIUM_USES} extra /name uses</b> added for today.\n"
        f"<emoji id='{E_COINS}'>💸</emoji> Spent: <b>{PREMIUM_COST:,} 🌸</b>\n"
        f"<emoji id='{E_STAR}'>⭐️</emoji> Balance: <b>{new_bal:,} 🌸</b>",
        parse_mode=enums.ParseMode.HTML,
    )
