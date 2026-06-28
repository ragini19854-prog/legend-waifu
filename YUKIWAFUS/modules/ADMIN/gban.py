"""
/gban   — globally ban a user from the bot (sudo + owner)
/ungban — remove global ban
/gbanned — list all globally banned users
"""
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import gbansdb
from YUKIWAFUS.utils.helpers import sc

_SUDO_OWNER = config.SUDO_USERS + [config.OWNER_ID]


async def is_gbanned(user_id: int) -> bool:
    return bool(await gbansdb.find_one({"user_id": user_id}))


async def gban_user(user_id: int, reason: str = "No reason provided", banned_by: int = 0):
    await gbansdb.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "reason": reason, "banned_by": banned_by}},
        upsert=True,
    )


async def ungban_user(user_id: int):
    await gbansdb.delete_one({"user_id": user_id})


def _get_target(message: Message) -> tuple[int | None, str]:
    """Extract (user_id, reason) from reply or args."""
    reason = "No reason provided"
    user_id = None

    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
        args    = message.command[1:]
        if args:
            reason = " ".join(args)
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            if len(message.command) > 2:
                reason = " ".join(message.command[2:])
        except ValueError:
            pass
    return user_id, reason


# ── /gban ──────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("gban") & filters.user(_SUDO_OWNER))
async def gban_handler(client: Client, message: Message):
    user_id, reason = _get_target(message)

    if not user_id:
        return await message.reply_text(
            "<blockquote>⚠️ <b>Usage:</b> Reply to a user or provide a user_id.\n"
            "<code>/gban &lt;user_id&gt; [reason]</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if user_id == config.OWNER_ID:
        return await message.reply_text("❌ Cannot gban the owner!", parse_mode=enums.ParseMode.HTML)

    if user_id in config.SUDO_USERS:
        return await message.reply_text("❌ Cannot gban a sudo user!", parse_mode=enums.ParseMode.HTML)

    if await is_gbanned(user_id):
        return await message.reply_text(
            f"<blockquote>⚠️ <code>{user_id}</code> is already gbanned.</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    try:
        user = await client.get_users(user_id)
        name = f"<a href='tg://user?id={user_id}'>{escape(user.first_name)}</a>"
    except Exception:
        name = f"<code>{user_id}</code>"

    await gban_user(user_id, reason, message.from_user.id)

    await message.reply_text(
        f"<blockquote>🚫 <b>User Globally Banned!</b></blockquote>\n\n"
        f"<b>User:</b> {name}\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Reason:</b> {escape(reason)}\n"
        f"<b>Banned by:</b> <a href='tg://user?id={message.from_user.id}'>{escape(message.from_user.first_name)}</a>",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /ungban ───────────────────────────────────────────────────────────────────

@app.on_message(filters.command("ungban") & filters.user(_SUDO_OWNER))
async def ungban_handler(client: Client, message: Message):
    user_id, _ = _get_target(message)

    if not user_id:
        return await message.reply_text(
            "<blockquote>⚠️ <b>Usage:</b> <code>/ungban &lt;user_id&gt;</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if not await is_gbanned(user_id):
        return await message.reply_text(
            f"<blockquote>⚠️ <code>{user_id}</code> is not gbanned.</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    await ungban_user(user_id)

    try:
        user = await client.get_users(user_id)
        name = f"<a href='tg://user?id={user_id}'>{escape(user.first_name)}</a>"
    except Exception:
        name = f"<code>{user_id}</code>"

    await message.reply_text(
        f"<blockquote>✅ <b>Global ban removed!</b></blockquote>\n\n"
        f"<b>User:</b> {name} is now free to use the bot.",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /gbanned ──────────────────────────────────────────────────────────────────

@app.on_message(filters.command("gbanned") & filters.user(_SUDO_OWNER))
async def gbanned_list_handler(client: Client, message: Message):
    docs = await gbansdb.find({}).to_list(length=200)

    if not docs:
        return await message.reply_text(
            "<blockquote>✅ <b>No globally banned users.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    text = "<blockquote>🚫 <b>Globally Banned Users</b></blockquote>\n\n"
    for i, doc in enumerate(docs, 1):
        uid    = doc.get("user_id", "?")
        reason = doc.get("reason", "N/A")
        text  += f"{i}. <code>{uid}</code> — {escape(reason)}\n"

    text += f"\n<b>Total:</b> {len(docs)}"
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
