"""
/propose — randomly propose to a waifu. 50/50 chance. One try per day.

Success → waifu photo + [✅ Accept | ❌ Reject] buttons
Failure → text message
"""
import random
from datetime import datetime, timezone
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    Message,
)

from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import proposedb, collectiondb, balancedb
from YUKIWAFUS.utils.api import get_random_waifu
from YUKIWAFUS.utils.rarity import rarity_emoji
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _used_today(user_id: int) -> bool:
    doc = await proposedb.find_one({"user_id": user_id})
    return bool(doc and doc.get("date") == _today())


async def _mark_used(user_id: int):
    await proposedb.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "date": _today()}},
        upsert=True,
    )


# ── /propose ──────────────────────────────────────────────────────────────────

@app.on_message(filters.command("propose"))
async def propose_handler(client: Client, message: Message):
    user    = message.from_user
    user_id = user.id

    if await _used_today(user_id):
        return await message.reply_text(
            "<blockquote>"
            "💔 <b>You've already proposed today!</b>\n\n"
            "Come back tomorrow to try your luck again~"
            "</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    await _mark_used(user_id)

    # ── 50 / 50 ───────────────────────────────────────────────────────────────
    luck = random.random()

    if luck < 0.5:
        # ── Failure ───────────────────────────────────────────────────────────
        fails = [
            "💨 <b>Your crush ran away!</b>\n<i>Better luck next time~</i>",
            "😔 <b>Rejected!</b> She said she only likes anime boys.",
            "🏃 <b>She vanished!</b> Maybe she wasn't real after all...",
            "💔 <b>Your heart got broken today.</b> Try again tomorrow!",
            "🌧 <b>No luck today!</b> The waifu gods weren't on your side.",
        ]
        return await message.reply_text(
            f"<blockquote>{random.choice(fails)}</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    # ── Success — fetch a waifu ───────────────────────────────────────────────
    processing = await message.reply_text("💌 Sending your proposal...")

    waifu = await get_random_waifu()
    if not waifu:
        return await processing.edit_text("❌ Could not find a waifu right now. Try again!")

    await processing.delete()

    rarity  = waifu.get("rarity", "Common")
    emoji   = rarity_emoji(rarity)
    name    = waifu.get("name", "Mystery Waifu")
    anime   = waifu.get("anime_name") or waifu.get("event_tag", "Unknown")
    img     = waifu.get("img_url", "")
    wid     = waifu.get("waifu_id", "N/A")

    caption = (
        f"<blockquote>"
        f"💕 <b>A waifu accepted your proposal!</b>"
        f"</blockquote>\n\n"
        f"<b>📛 Name :</b> {escape(name)}\n"
        f"<b>🎌 Anime :</b> {escape(anime)}\n"
        f"<b>{emoji} Rarity :</b> {rarity}\n\n"
        f"<i>Will you accept her? 💍</i>"
    )

    raw_kb = [row(
        btn("✅ Accept", callback_data=f"propose_accept:{user_id}:{wid}", style="success"),
        btn("❌ Reject", callback_data=f"propose_reject:{user_id}",       style="danger"),
    )]

    if img:
        msg = await message.reply_photo(
            photo=img,
            caption=caption,
            reply_markup=to_pyrogram(raw_kb),
            parse_mode=enums.ParseMode.HTML,
        )
    else:
        msg = await message.reply_text(
            caption,
            reply_markup=to_pyrogram(raw_kb),
            parse_mode=enums.ParseMode.HTML,
        )
    await inject_styled(msg.chat.id, msg.id, raw_kb)


# ── Accept / Reject callbacks ─────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^propose_accept:"))
async def propose_accept_cb(client: Client, cq: CallbackQuery):
    parts   = cq.data.split(":")
    user_id = int(parts[1])
    wid     = parts[2] if len(parts) > 2 else ""

    if cq.from_user.id != user_id:
        return await cq.answer("This is not your proposal! 😤", show_alert=True)

    await cq.answer("💍 You accepted! She's now yours forever~", show_alert=True)
    try:
        await cq.message.edit_caption(
            (cq.message.caption or "") + "\n\n✅ <b>Accepted! 💍 Congratulations!</b>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^propose_reject:"))
async def propose_reject_cb(client: Client, cq: CallbackQuery):
    parts   = cq.data.split(":")
    user_id = int(parts[1])

    if cq.from_user.id != user_id:
        return await cq.answer("This is not your proposal! 😤", show_alert=True)

    await cq.answer("💔 You rejected her. There are more waifus in the sea~", show_alert=True)
    try:
        await cq.message.edit_caption(
            (cq.message.caption or "") + "\n\n❌ <b>Rejected. Maybe tomorrow will be better~</b>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass
