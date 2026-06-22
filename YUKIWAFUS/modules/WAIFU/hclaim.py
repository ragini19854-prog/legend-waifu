import asyncio
from datetime import datetime
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb, balancedb
from YUKIWAFUS.utils.api import get_random_waifu
from YUKIWAFUS.utils.helpers import sc
from YUKIWAFUS.utils.safe_photo import safe_reply_photo
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled

CLAIM_COOLDOWN = config.CLAIM_COOLDOWN
CLAIM_COINS    = 50

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

claim_lock: set = set()


def format_time(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    parts  = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}s")
    return " ".join(parts) or "0s"


async def get_last_claim(user_id: int) -> datetime | None:
    user = await collectiondb.find_one({"user_id": user_id})
    return user.get("last_claim") if user else None


async def set_last_claim(user_id: int, username: str, first_name: str, waifu: dict):
    await collectiondb.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "username":   username,
                "first_name": first_name,
                "last_claim": datetime.utcnow(),
            },
            "$push": {"waifus": waifu},
        },
        upsert=True,
    )


async def add_coins(user_id: int, amount: int) -> int:
    result = await balancedb.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"coins": amount}},
        upsert=True,
        return_document=True,
    )
    return (result or {}).get("coins", amount)


@app.on_message(filters.command(["hclaim", "claim", "daily"]))
async def hclaim_handler(client: Client, message: Message):
    user_id  = message.from_user.id
    username = message.from_user.username or ""
    name     = message.from_user.first_name
    mention  = f"<a href='tg://user?id={user_id}'>{escape(name)}</a>"

    if user_id in claim_lock:
        return await message.reply_text(f"⏳ {sc('Your claim is being processed...')}")

    claim_lock.add(user_id)

    try:
        last_claim = await get_last_claim(user_id)
        if last_claim:
            diff = (datetime.utcnow() - last_claim).total_seconds()
            if diff < CLAIM_COOLDOWN:
                remaining = int(CLAIM_COOLDOWN - diff)
                raw_kb    = [[btn(
                    f"⏰ {sc('Come back in')} {format_time(remaining)}",
                    callback_data="claim_cooldown",
                    style="primary",
                    emoji_id="6294063539069917326",
                )]]
                msg = await message.reply_text(
                    f"<blockquote>⏳ <b>{mention} {sc('already claimed today')}!</b></blockquote>\n\n"
                    f"🕐 {sc('Next claim in')}: <b>{format_time(remaining)}</b>",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=to_pyrogram(raw_kb),
                )
                await inject_styled(msg.chat.id, msg.id, raw_kb)
                return

        processing = await message.reply_text(f"🎴 {sc('Fetching your daily waifu')}...")
        waifu = await get_random_waifu()

        if not waifu:
            await processing.delete()
            return await message.reply_text(f"❌ {sc('No waifu available right now. Try again later!')}")

        await set_last_claim(user_id, username, name, waifu)
        new_balance = await add_coins(user_id, CLAIM_COINS)
        await processing.delete()

        rarity = waifu.get("rarity", "Common")
        emoji  = RARITY_EMOJI.get(rarity, "◈")

        raw_kb = [row(
            btn(f"🌸 {sc('My Harem')}", switch_current=f"col.{user_id}", style="success", emoji_id="6291837599254322363"),
            btn(f"⚔️ {sc('Battle')}",  switch_current=f"battle.{user_id}", style="danger", emoji_id="6294023338176028117"),
        )]

        sent = await safe_reply_photo(
            message,
            photo=waifu["img_url"],
            caption=(
                f"<blockquote>🎊 <b>{sc('Daily Claim')}!</b></blockquote>\n\n"
                f"🎉 {mention} {sc('got a new waifu')}!\n\n"
                f"📛 <b>{sc('Name')}:</b> {escape(waifu['name'])}\n"
                f"{emoji} <b>{sc('Rarity')}:</b> {rarity}\n"
                f"🏷 <b>{sc('Tag')}:</b> {waifu.get('event_tag', 'Standard')}\n\n"
                f"🪙 <b>+{CLAIM_COINS} {sc('coins')}</b> → {sc('Balance')}: <b>{new_balance}</b>\n\n"
                f"<i>{sc('Come back tomorrow for another claim')}~</i>"
            ),
            reply_markup=to_pyrogram(raw_kb),
        )
        if sent:
            await inject_styled(sent.chat.id, sent.id, raw_kb)

    except Exception:
        await message.reply_text(f"❌ {sc('Something went wrong. Try again!')}")

    finally:
        claim_lock.discard(user_id)


@app.on_callback_query(filters.regex("^claim_cooldown$"))
async def claim_cooldown_cb(client, cq):
    await cq.answer(sc("You already claimed today! Come back later."), show_alert=True)
