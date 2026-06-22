import asyncio
from datetime import datetime, timedelta
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    Message,
)

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb, giftdb
from YUKIWAFUS.utils.helpers import sc
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled, edit_styled_caption

GIFT_TIMEOUT = 3600

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

gift_lock: set = set()


def mention(user) -> str:
    return f"<a href='tg://user?id={user.id}'>{escape(user.first_name)}</a>"


async def get_waifu_from_collection(user_id: int, waifu_id: str) -> dict | None:
    user = await collectiondb.find_one({"user_id": user_id})
    if not user:
        return None
    for w in user.get("waifus", []):
        if str(w.get("_id", "")) == waifu_id or str(w.get("waifu_id", "")) == waifu_id:
            return w
    return None


async def remove_waifu_from_collection(user_id: int, waifu_id: str):
    await collectiondb.update_one(
        {"user_id": user_id},
        {"$pull": {"waifus": {"waifu_id": waifu_id}}},
    )


async def add_waifu_to_collection(user_id: int, username: str, first_name: str, waifu: dict):
    await collectiondb.update_one(
        {"user_id": user_id},
        {
            "$set":  {"username": username or "", "first_name": first_name},
            "$push": {"waifus": waifu},
        },
        upsert=True,
    )


def _gift_kb(sender_id: int, receiver_id: int, waifu_id: str) -> list:
    return [row(
        btn(f"✅ {sc('Confirm Gift')}",  callback_data=f"gift_confirm:{sender_id}:{receiver_id}:{waifu_id}", style="success", emoji_id="6001483331709966655"),
        btn(f"❌ {sc('Cancel')}",         callback_data=f"gift_cancel:{sender_id}",                          style="danger",  emoji_id="5998834801472182366"),
    )]


@app.on_message(filters.command("gift"))
async def gift_cmd(client: Client, message: Message):
    sender = message.from_user

    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('Reply to a user to gift them a waifu')}.</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('Usage')} :</b> <code>/gift &lt;waifu_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    receiver = message.reply_to_message.from_user

    if receiver.id == sender.id:
        return await message.reply_text(
            f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('You cannot gift yourself')}.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if receiver.is_bot:
        return await message.reply_text(
            f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('You cannot gift bots')}.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if len(message.command) < 2:
        return await message.reply_text(
            f"<blockquote><emoji id='6001602353843672777'>⚠️</emoji> <b>{sc('Provide a waifu ID')}.</b></blockquote>\n\n"
            f"<b>{sc('Usage')} :</b> <code>/gift &lt;waifu_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    waifu_id = message.command[1].strip()

    if sender.id in gift_lock:
        return await message.reply_text(
            f"<blockquote>⏳ <b>{sc('A gift is already pending from you')}.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    waifu = await get_waifu_from_collection(sender.id, waifu_id)
    if not waifu:
        return await message.reply_text(
            f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('Waifu not found in your collection')}.</b></blockquote>\n\n"
            f"<i>{sc('Check your harem with')} /harem~</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    rarity = waifu.get("rarity", "Common")
    emoji  = RARITY_EMOJI.get(rarity, "◈")

    await giftdb.update_one(
        {"sender_id": sender.id},
        {
            "$set": {
                "sender_id":   sender.id,
                "receiver_id": receiver.id,
                "waifu_id":    waifu_id,
                "waifu":       waifu,
                "created_at":  datetime.utcnow(),
            }
        },
        upsert=True,
    )

    gift_lock.add(sender.id)

    raw_kb = _gift_kb(sender.id, receiver.id, waifu_id)

    sent = await message.reply_photo(
        photo=waifu.get("img_url", config.WAIFU_PICS[0]),
        caption=(
            f"<blockquote>"
            f"<emoji id='6294023338176028117'>🎁</emoji> "
            f"<b>{sc('Gift Confirmation')}!</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('From')} :</b> {mention(sender)}\n"
            f"<b>{sc('To')} :</b>   {mention(receiver)}\n\n"
            f"📛 <b>{sc('Waifu')} :</b> {escape(waifu.get('name', 'Unknown'))}\n"
            f"{emoji} <b>{sc('Rarity')} :</b> {rarity}\n\n"
            f"<i>⏳ {sc('Auto-cancels in 1 hour')}~</i>"
        ),
        parse_mode=enums.ParseMode.HTML,
        reply_markup=to_pyrogram(raw_kb),
        has_spoiler=True,
    )
    await inject_styled(sent.chat.id, sent.id, raw_kb)

    asyncio.create_task(_auto_cancel_gift(sender.id, sent))


async def _auto_cancel_gift(sender_id: int, sent_msg):
    await asyncio.sleep(GIFT_TIMEOUT)
    doc = await giftdb.find_one({"sender_id": sender_id})
    if not doc:
        return
    await giftdb.delete_one({"sender_id": sender_id})
    gift_lock.discard(sender_id)
    try:
        await sent_msg.edit_caption(
            f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('Gift expired — auto cancelled after 1 hour')}.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^gift_confirm:"))
async def gift_confirm_cb(client: Client, cq: CallbackQuery):
    parts       = cq.data.split(":")
    sender_id   = int(parts[1])
    receiver_id = int(parts[2])
    waifu_id    = parts[3]

    if cq.from_user.id != sender_id:
        return await cq.answer(sc("This is not your gift!"), show_alert=True)

    doc = await giftdb.find_one({"sender_id": sender_id})
    if not doc:
        return await cq.answer(sc("Gift expired or already sent!"), show_alert=True)

    waifu = doc["waifu"]
    rarity      = waifu.get("rarity", "Common")
    emoji       = RARITY_EMOJI.get(rarity, "◈")

    try:
        receiver = await client.get_users(receiver_id)
    except Exception:
        return await cq.answer(sc("Could not find receiver!"), show_alert=True)

    try:
        sender = await client.get_users(sender_id)
    except Exception:
        sender = cq.from_user

    await remove_waifu_from_collection(sender_id, waifu_id)
    await add_waifu_to_collection(receiver_id, receiver.username or "", receiver.first_name, waifu)

    await giftdb.delete_one({"sender_id": sender_id})
    gift_lock.discard(sender_id)

    await edit_styled_caption(
        cq.message.chat.id,
        cq.message.id,
        (
            f"<blockquote><emoji id='6001483331709966655'>✅</emoji> <b>{sc('Gift Sent Successfully')}!</b></blockquote>\n\n"
            f"<b>{sc('From')} :</b> {mention(sender)}\n"
            f"<b>{sc('To')} :</b>   {mention(receiver)}\n\n"
            f"📛 <b>{sc('Waifu')} :</b> {escape(waifu.get('name', 'Unknown'))}\n"
            f"{emoji} <b>{sc('Rarity')} :</b> {rarity}"
        ),
        [],
    )
    await cq.answer(sc("Gift sent!"), show_alert=False)

    try:
        await client.send_message(
            receiver_id,
            f"<blockquote><emoji id='6294023338176028117'>🎁</emoji> <b>{sc('You received a waifu gift')}!</b></blockquote>\n\n"
            f"<b>{sc('From')} :</b> {mention(sender)}\n"
            f"📛 <b>{sc('Waifu')} :</b> {escape(waifu.get('name', 'Unknown'))}\n"
            f"{emoji} <b>{sc('Rarity')} :</b> {rarity}\n\n"
            f"<i>{sc('Check your harem with')} /harem~</i>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^gift_cancel:"))
async def gift_cancel_cb(client: Client, cq: CallbackQuery):
    sender_id = int(cq.data.split(":")[1])

    if cq.from_user.id != sender_id:
        return await cq.answer(sc("This is not your gift!"), show_alert=True)

    await giftdb.delete_one({"sender_id": sender_id})
    gift_lock.discard(sender_id)

    await edit_styled_caption(
        cq.message.chat.id,
        cq.message.id,
        f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('Gift cancelled')}.</b></blockquote>",
        [],
    )
    await cq.answer(sc("Gift cancelled."), show_alert=False)
