import random

from pyrogram import Client, filters, enums
from pyrogram.errors import RPCError
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import chatsdb, onoffdb
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled


async def _logger_on() -> bool:
    doc = await onoffdb.find_one({"key": "logger"})
    return doc.get("value", True) if doc else True


@app.on_message(filters.new_chat_members, group=2)
async def join_watcher(client: Client, message: Message):
    bot_me = await client.get_me()

    for member in message.new_chat_members:
        if member.id != bot_me.id:
            continue

        chat = message.chat

        await chatsdb.update_one(
            {"chat_id": chat.id},
            {"$set": {"title": chat.title or ""}},
            upsert=True,
        )

        if not await _logger_on() or not config.LOG_CHANNEL:
            break

        count = 0
        try:
            count = await client.get_chat_members_count(chat.id)
        except RPCError:
            pass

        try:
            link = await client.export_chat_invite_link(chat.id)
        except RPCError:
            link = None

        username = f"@{chat.username}" if chat.username else "ᴘʀɪᴠᴀᴛᴇ ɢʀᴏᴜᴘ"
        added_by = (
            f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
            if message.from_user else "ᴜɴᴋɴᴏᴡɴ"
        )

        caption = (
            f"<blockquote>"
            f"<emoji id='6293940475371986355'>🎉</emoji> "
            f"<b>ʙᴏᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ɢʀᴏᴜᴘ!</b>"
            f"</blockquote>\n\n"
            f"<blockquote>"
            f"<emoji id='6294047505957003963'>📌</emoji> <b>ɴᴀᴍᴇ :</b> {chat.title}\n"
            f"<emoji id='6294118750874508525'>🆔</emoji> <b>ɪᴅ :</b> <code>{chat.id}</code>\n"
            f"<emoji id='6296339201721899681'>🔗</emoji> <b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username}\n"
            f"<emoji id='6293965450606812914'>👥</emoji> <b>ᴍᴇᴍʙᴇʀs :</b> {count}"
            f"</blockquote>\n\n"
            f"<blockquote>"
            f"<emoji id='6294023338176028117'>👤</emoji> <b>ᴀᴅᴅᴇᴅ ʙʏ :</b> {added_by}"
            f"</blockquote>"
        )

        raw_kb = (
            [row(btn("sᴇᴇ ɢʀᴏᴜᴘ 👀", url=link, style="primary", emoji_id="5249244862359812334"))]
            if link else None
        )

        try:
            msg = await app.send_photo(
                config.LOG_CHANNEL,
                photo=random.choice(config.WAIFU_PICS),
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                has_spoiler=True,
                reply_markup=to_pyrogram(raw_kb) if raw_kb else None,
            )
            if raw_kb:
                await inject_styled(config.LOG_CHANNEL, msg.id, raw_kb)
        except Exception:
            pass

        break


@app.on_message(filters.left_chat_member)
async def left_watcher(client: Client, message: Message):
    bot_me = await client.get_me()

    if message.left_chat_member.id != bot_me.id:
        return

    chat = message.chat

    await chatsdb.update_one(
        {"chat_id": chat.id},
        {"$set": {"active": False}},
    )

    if not await _logger_on() or not config.LOG_CHANNEL:
        return

    removed_by = (
        f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
        if message.from_user else "ᴜɴᴋɴᴏᴡɴ"
    )
    username = f"@{chat.username}" if chat.username else "ᴘʀɪᴠᴀᴛᴇ ɢʀᴏᴜᴘ"

    caption = (
        f"<blockquote>"
        f"<emoji id='5998834801472182366'>❌</emoji> "
        f"<b>ʙᴏᴛ ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ɢʀᴏᴜᴘ!</b>"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<emoji id='6294047505957003963'>📌</emoji> <b>ɴᴀᴍᴇ :</b> {chat.title}\n"
        f"<emoji id='6294118750874508525'>🆔</emoji> <b>ɪᴅ :</b> <code>{chat.id}</code>\n"
        f"<emoji id='6296339201721899681'>🔗</emoji> <b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username}"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"<emoji id='6294023338176028117'>👤</emoji> <b>ʀᴇᴍᴏᴠᴇᴅ ʙʏ :</b> {removed_by}"
        f"</blockquote>"
    )

    try:
        await app.send_photo(
            config.LOG_CHANNEL,
            photo=random.choice(config.WAIFU_PICS),
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
            has_spoiler=True,
        )
    except Exception:
        pass
