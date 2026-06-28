"""
Owner-only admin commands:
  /givewaifu <user_id> <waifu_name>   — give a waifu from the API to any user
  /givecoin  <user_id> <amount>        — give coins
  /rmcoin    <user_id> <amount>        — remove coins
  /premium   <user_id> <days>          — grant /name premium for N days
  /unpremium <user_id>                 — revoke premium
"""
from datetime import datetime, timezone, timedelta
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import balancedb, collectiondb, premiumdb
from YUKIWAFUS.utils.api import find_waifu
from YUKIWAFUS.utils.rarity import rarity_emoji

_OWNER_ONLY = [config.OWNER_ID]
_SUDO_ALL   = config.SUDO_USERS + [config.OWNER_ID]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _resolve_user(client, message: Message) -> tuple[int | None, str]:
    """Return (user_id, display_name) from reply or first arg."""
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, escape(u.first_name)
    if len(message.command) > 1:
        try:
            uid  = int(message.command[1])
            user = await client.get_users(uid)
            return uid, escape(user.first_name)
        except Exception:
            pass
    return None, ""


# ── /givewaifu ────────────────────────────────────────────────────────────────

@app.on_message(filters.command("givewaifu") & filters.user(_OWNER_ONLY))
async def givewaifu_handler(client: Client, message: Message):
    # Usage: /givewaifu <user_id> <waifu name>
    # Or reply to user: /givewaifu <waifu name>
    args = message.command[1:]

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id   = message.reply_to_message.from_user.id
        target_name = escape(message.reply_to_message.from_user.first_name)
        waifu_query = " ".join(args).strip()
    elif len(args) >= 2:
        try:
            target_id = int(args[0])
            u         = await client.get_users(target_id)
            target_name = escape(u.first_name)
        except Exception:
            return await message.reply_text(
                "❌ <b>Invalid user_id.</b>\n<code>/givewaifu &lt;user_id&gt; &lt;waifu name&gt;</code>",
                parse_mode=enums.ParseMode.HTML,
            )
        waifu_query = " ".join(args[1:]).strip()
    else:
        return await message.reply_text(
            "<blockquote>⚠️ <b>Usage:</b>\n"
            "Reply to user: <code>/givewaifu &lt;waifu name&gt;</code>\n"
            "Or: <code>/givewaifu &lt;user_id&gt; &lt;waifu name&gt;</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if not waifu_query:
        return await message.reply_text("❌ Provide a waifu name!", parse_mode=enums.ParseMode.HTML)

    proc = await message.reply_text(f"🔍 Searching for <b>{escape(waifu_query)}</b>...", parse_mode=enums.ParseMode.HTML)
    results = await find_waifu(waifu_query)

    if not results:
        return await proc.edit_text(f"❌ No waifu found for <b>{escape(waifu_query)}</b>.", parse_mode=enums.ParseMode.HTML)

    waifu  = results[0]
    rarity = waifu.get("rarity", "Common")
    rem    = rarity_emoji(rarity)

    await collectiondb.update_one(
        {"user_id": target_id},
        {"$set": {"user_id": target_id, "first_name": target_name}, "$push": {"waifus": waifu}},
        upsert=True,
    )

    await proc.edit_text(
        f"<blockquote>✅ <b>Waifu Given!</b></blockquote>\n\n"
        f"<b>To:</b> <a href='tg://user?id={target_id}'>{target_name}</a>\n"
        f"<b>Waifu:</b> {escape(waifu.get('name','?'))}\n"
        f"<b>{rem} Rarity:</b> {rarity}",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /givecoin ─────────────────────────────────────────────────────────────────

@app.on_message(filters.command("givecoin") & filters.user(_OWNER_ONLY))
async def givecoin_handler(client: Client, message: Message):
    args = message.command[1:]

    if message.reply_to_message and message.reply_to_message.from_user and len(args) >= 1:
        target_id   = message.reply_to_message.from_user.id
        target_name = escape(message.reply_to_message.from_user.first_name)
        amount_str  = args[0]
    elif len(args) >= 2:
        target_id   = None
        target_name = ""
        try:
            target_id   = int(args[0])
            u           = await client.get_users(target_id)
            target_name = escape(u.first_name)
            amount_str  = args[1]
        except Exception:
            return await message.reply_text("❌ Invalid usage.", parse_mode=enums.ParseMode.HTML)
    else:
        return await message.reply_text(
            "<code>/givecoin &lt;user_id&gt; &lt;amount&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    try:
        amount = int(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.reply_text("❌ Amount must be a positive integer.", parse_mode=enums.ParseMode.HTML)

    doc = await balancedb.find_one_and_update(
        {"user_id": target_id},
        {"$inc": {"coins": amount}},
        upsert=True,
        return_document=True,
    )
    new_bal = (doc or {}).get("coins", amount)

    await message.reply_text(
        f"<blockquote>🌸 <b>Coins Given!</b></blockquote>\n\n"
        f"<b>To:</b> <a href='tg://user?id={target_id}'>{target_name}</a>\n"
        f"<b>Given:</b> +{amount:,} 🌸\n"
        f"<b>New Balance:</b> {new_bal:,} 🌸",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /rmcoin ───────────────────────────────────────────────────────────────────

@app.on_message(filters.command("rmcoin") & filters.user(_OWNER_ONLY))
async def rmcoin_handler(client: Client, message: Message):
    args = message.command[1:]

    if message.reply_to_message and message.reply_to_message.from_user and len(args) >= 1:
        target_id   = message.reply_to_message.from_user.id
        target_name = escape(message.reply_to_message.from_user.first_name)
        amount_str  = args[0]
    elif len(args) >= 2:
        try:
            target_id   = int(args[0])
            u           = await client.get_users(target_id)
            target_name = escape(u.first_name)
            amount_str  = args[1]
        except Exception:
            return await message.reply_text("❌ Invalid usage.", parse_mode=enums.ParseMode.HTML)
    else:
        return await message.reply_text(
            "<code>/rmcoin &lt;user_id&gt; &lt;amount&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    try:
        amount = int(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.reply_text("❌ Amount must be a positive integer.", parse_mode=enums.ParseMode.HTML)

    doc = await balancedb.find_one_and_update(
        {"user_id": target_id},
        {"$inc": {"coins": -amount}},
        upsert=True,
        return_document=True,
    )
    new_bal = (doc or {}).get("coins", 0)

    await message.reply_text(
        f"<blockquote>💸 <b>Coins Removed!</b></blockquote>\n\n"
        f"<b>From:</b> <a href='tg://user?id={target_id}'>{target_name}</a>\n"
        f"<b>Removed:</b> -{amount:,} 🌸\n"
        f"<b>New Balance:</b> {max(new_bal,0):,} 🌸",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /premium ──────────────────────────────────────────────────────────────────

@app.on_message(filters.command("premium") & filters.user(_OWNER_ONLY))
async def premium_handler(client: Client, message: Message):
    # Usage: /premium <user_id> <days>  OR reply + /premium <days>
    args = message.command[1:]

    if message.reply_to_message and message.reply_to_message.from_user and len(args) >= 1:
        target_id   = message.reply_to_message.from_user.id
        target_name = escape(message.reply_to_message.from_user.first_name)
        days_str    = args[0]
    elif len(args) >= 2:
        try:
            target_id   = int(args[0])
            u           = await client.get_users(target_id)
            target_name = escape(u.first_name)
            days_str    = args[1]
        except Exception:
            return await message.reply_text("❌ Invalid usage.", parse_mode=enums.ParseMode.HTML)
    else:
        return await message.reply_text(
            "<code>/premium &lt;user_id&gt; &lt;days&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    try:
        days = int(days_str)
        if days <= 0:
            raise ValueError
    except ValueError:
        return await message.reply_text("❌ Days must be a positive integer.", parse_mode=enums.ParseMode.HTML)

    expires_at = _now() + timedelta(days=days)

    await premiumdb.update_one(
        {"user_id": target_id},
        {"$set": {
            "user_id":    target_id,
            "expires_at": expires_at,
            "daily_uses": 15,
            "granted_by": message.from_user.id,
        }},
        upsert=True,
    )

    await message.reply_text(
        f"<blockquote>💎 <b>Premium Granted!</b></blockquote>\n\n"
        f"<b>User:</b> <a href='tg://user?id={target_id}'>{target_name}</a>\n"
        f"<b>Duration:</b> {days} day(s)\n"
        f"<b>Expires:</b> {expires_at.strftime('%d %b %Y %H:%M UTC')}\n"
        f"<b>Benefit:</b> 15 /name uses per day",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /unpremium ────────────────────────────────────────────────────────────────

@app.on_message(filters.command("unpremium") & filters.user(_OWNER_ONLY))
async def unpremium_handler(client: Client, message: Message):
    target_id, target_name = await _resolve_user(client, message)
    if not target_id:
        return await message.reply_text(
            "<code>/unpremium &lt;user_id&gt;</code>", parse_mode=enums.ParseMode.HTML
        )

    result = await premiumdb.delete_one({"user_id": target_id})

    if result.deleted_count:
        await message.reply_text(
            f"✅ Premium removed from <a href='tg://user?id={target_id}'>{target_name}</a>.",
            parse_mode=enums.ParseMode.HTML,
        )
    else:
        await message.reply_text(
            f"⚠️ <a href='tg://user?id={target_id}'>{target_name}</a> has no active premium.",
            parse_mode=enums.ParseMode.HTML,
        )
