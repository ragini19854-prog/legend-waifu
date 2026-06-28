"""
/marry — propose to a waifu. One attempt per day.
  ✅ Marry   → stores marriage in DB
  🏃 Run Away → blocked from /marry for RUN_AWAY_DAYS days
  👑 Owner   → no limits at all
"""
import random
from datetime import datetime, timezone, timedelta
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import CallbackQuery, Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import marriagedb, gbansdb, usersdb
from YUKIWAFUS.utils.api import get_random_waifu
from YUKIWAFUS.utils.rarity import rarity_emoji
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled

RUN_AWAY_DAYS = 3   # days blocked if user runs away

# ── NewsEmoji IDs ─────────────────────────────────────────────────────────────
E_RING    = "5461151367559141950"   # 🎉
E_STAR    = "5438496463044752972"   # ⭐️
E_SPARKLE = "5325547803936572038"   # ✨
E_CROWN   = "5217822164362739968"   # 👑
E_CROSS   = "5210952531676504517"   # ❌
E_CHECK   = "5206607081334906820"   # ✔️
E_WARNING = "5447644880824181073"   # ⚠️
E_MUSIC   = "5463107823946717464"   # 🎵
E_SNOW    = "5449449325434266744"   # ❄️
E_FIRE    = "5424972470023104089"   # 🔥
E_LOCK    = "5296369303661067030"   # 🔒
E_HEART   = "5406756500108501710"   # 🆓 (repurposed for heart feel)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _is_gbanned(user_id: int) -> bool:
    return bool(await gbansdb.find_one({"user_id": user_id}))


async def _get_marriage(user_id: int) -> dict | None:
    return await marriagedb.find_one({"user_id": user_id})


async def _save_marriage(doc: dict):
    await marriagedb.update_one(
        {"user_id": doc["user_id"]},
        {"$set": doc},
        upsert=True,
    )


async def _delete_marriage(user_id: int):
    await marriagedb.delete_one({"user_id": user_id})


# ── /marry ────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("marry"))
async def marry_handler(client: Client, message: Message):
    user    = message.from_user
    user_id = user.id
    is_owner = (user_id == config.OWNER_ID)

    if await _is_gbanned(user_id):
        return

    doc = await _get_marriage(user_id)

    # Already married?
    if doc and doc.get("married_to") and not doc.get("run_away_until"):
        waifu  = doc["married_to"]
        name   = waifu.get("name", "???")
        anime  = waifu.get("anime_name") or waifu.get("event_tag", "Unknown")
        rarity = waifu.get("rarity", "Common")
        rem    = rarity_emoji(rarity)
        since  = doc.get("married_at", "")
        since_str = since.strftime("%d %b %Y") if isinstance(since, datetime) else str(since)[:10]
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{E_RING}'>💍</emoji> <b>You're already married!</b>"
            f"</blockquote>\n\n"
            f"<emoji id='{E_SPARKLE}'>✨</emoji> <b>Spouse:</b> {escape(name)}\n"
            f"<emoji id='{E_STAR}'>⭐️</emoji> <b>Anime:</b> {escape(anime)}\n"
            f"<b>{rem} Rarity:</b> {rarity}\n\n"
            f"<i>💍 Married since: {since_str}</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    # Blocked from run-away?
    if doc and doc.get("run_away_until"):
        run_until = doc["run_away_until"]
        if isinstance(run_until, datetime) and _now() < run_until.replace(tzinfo=timezone.utc) if run_until.tzinfo is None else _now() < run_until:
            delta     = (run_until.replace(tzinfo=timezone.utc) if run_until.tzinfo is None else run_until) - _now()
            days      = delta.days
            hours     = delta.seconds // 3600
            time_str  = f"{days}d {hours}h" if days else f"{hours}h"
            if not is_owner:
                return await message.reply_text(
                    f"<blockquote>"
                    f"<emoji id='{E_LOCK}'>🔒</emoji> <b>You ran away!</b>\n\n"
                    f"You can't use /marry for another <b>{time_str}</b>.\n"
                    f"<i>Actions have consequences~</i>"
                    f"</blockquote>",
                    parse_mode=enums.ParseMode.HTML,
                )
        else:
            # Cooldown expired — clear it
            await marriagedb.update_one({"user_id": user_id}, {"$unset": {"run_away_until": ""}})

    # Fetch a random waifu
    processing = await message.reply_text(
        f"<emoji id='{E_MUSIC}'>🎵</emoji> <i>Looking for your soulmate...</i>",
        parse_mode=enums.ParseMode.HTML,
    )
    waifu = await get_random_waifu()
    if not waifu:
        return await processing.edit_text(
            f"<emoji id='{E_CROSS}'>❌</emoji> Could not find a waifu right now. Try again!",
            parse_mode=enums.ParseMode.HTML,
        )
    await processing.delete()

    rarity_str = waifu.get("rarity", "Common")
    r_emoji    = rarity_emoji(rarity_str)
    name       = waifu.get("name", "Mystery Waifu")
    anime      = waifu.get("anime_name") or waifu.get("event_tag", "Unknown")
    img        = waifu.get("img_url", "")
    wid        = waifu.get("waifu_id", "N/A")

    caption = (
        f"<blockquote>"
        f"<emoji id='{E_RING}'>💍</emoji> <b>A waifu wants to be yours!</b>"
        f"</blockquote>\n\n"
        f"<emoji id='{E_SPARKLE}'>✨</emoji> <b>Name:</b> {escape(name)}\n"
        f"<emoji id='{E_STAR}'>⭐️</emoji> <b>Anime:</b> {escape(anime)}\n"
        f"<b>{r_emoji} Rarity:</b> {rarity_str}\n\n"
        f"<emoji id='{E_CROWN}'>👑</emoji> <i>Do you accept her hand?</i>"
    )

    raw_kb = [row(
        btn("💍 Marry",    callback_data=f"marry_yes:{user_id}:{wid}", style="success"),
        btn("🏃 Run Away", callback_data=f"marry_no:{user_id}",        style="danger"),
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

    # Store pending marriage (will be confirmed/rejected via button)
    await _save_marriage({
        "user_id":    user_id,
        "pending":    waifu,
        "married_to": None,
        "married_at": None,
    })


# ── Marry confirm ─────────────────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^marry_yes:"))
async def marry_yes_cb(client: Client, cq: CallbackQuery):
    parts   = cq.data.split(":")
    user_id = int(parts[1])

    if cq.from_user.id != user_id:
        return await cq.answer("This isn't your proposal! 😤", show_alert=True)

    doc = await _get_marriage(user_id)
    if not doc or not doc.get("pending"):
        return await cq.answer("Proposal expired!", show_alert=True)

    waifu = doc["pending"]
    await _save_marriage({
        "user_id":       user_id,
        "pending":       None,
        "married_to":    waifu,
        "married_at":    _now(),
        "run_away_until": None,
    })

    await cq.answer("💍 Congratulations! You're now married~", show_alert=True)
    try:
        old = cq.message.caption or cq.message.text or ""
        new = (
            old + f"\n\n"
            f"<emoji id='{E_CHECK}'>✔️</emoji> <b>Married! 💍</b>\n"
            f"<emoji id='{E_FIRE}'>🔥</emoji> <i>May your bond last forever~</i>"
        )
        if cq.message.photo:
            await cq.message.edit_caption(new, parse_mode=enums.ParseMode.HTML)
        else:
            await cq.message.edit_text(new, parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass


# ── Run Away ──────────────────────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^marry_no:"))
async def marry_no_cb(client: Client, cq: CallbackQuery):
    parts   = cq.data.split(":")
    user_id = int(parts[1])

    if cq.from_user.id != user_id:
        return await cq.answer("This isn't your proposal! 😤", show_alert=True)

    unblock_at = _now() + timedelta(days=RUN_AWAY_DAYS)
    await _save_marriage({
        "user_id":        user_id,
        "pending":        None,
        "married_to":     None,
        "married_at":     None,
        "run_away_until": unblock_at,
    })

    await cq.answer(
        f"🏃 You ran away! /marry blocked for {RUN_AWAY_DAYS} days.",
        show_alert=True,
    )
    try:
        old = cq.message.caption or cq.message.text or ""
        new = (
            old + f"\n\n"
            f"<emoji id='{E_SNOW}'>❄️</emoji> <b>You ran away...</b>\n"
            f"<emoji id='{E_LOCK}'>🔒</emoji> <i>/marry blocked for {RUN_AWAY_DAYS} days.</i>"
        )
        if cq.message.photo:
            await cq.message.edit_caption(new, parse_mode=enums.ParseMode.HTML)
        else:
            await cq.message.edit_text(new, parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass


# ── /divorce ──────────────────────────────────────────────────────────────────

@app.on_message(filters.command("divorce"))
async def divorce_handler(client: Client, message: Message):
    user_id = message.from_user.id
    doc     = await _get_marriage(user_id)
    if not doc or not doc.get("married_to"):
        return await message.reply_text(
            f"<blockquote><emoji id='{E_WARNING}'>⚠️</emoji> You aren't married!</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
    await _delete_marriage(user_id)
    waifu = doc["married_to"]
    await message.reply_text(
        f"<blockquote>"
        f"<emoji id='{E_CROSS}'>❌</emoji> <b>Divorced from {escape(waifu.get('name','???'))}.</b>\n"
        f"<i>You're free again... for now~</i>"
        f"</blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /mymarriage ───────────────────────────────────────────────────────────────

@app.on_message(filters.command("mymarriage"))
async def mymarriage_handler(client: Client, message: Message):
    user_id = message.from_user.id
    doc     = await _get_marriage(user_id)
    if not doc or not doc.get("married_to"):
        return await message.reply_text(
            f"<blockquote><emoji id='{E_WARNING}'>⚠️</emoji> You aren't married yet! Try /marry~</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
    waifu  = doc["married_to"]
    name   = waifu.get("name", "???")
    anime  = waifu.get("anime_name") or waifu.get("event_tag", "Unknown")
    rarity = waifu.get("rarity", "Common")
    rem    = rarity_emoji(rarity)
    since  = doc.get("married_at", "")
    since_str = since.strftime("%d %b %Y") if isinstance(since, datetime) else str(since)[:10]
    await message.reply_text(
        f"<blockquote>"
        f"<emoji id='{E_RING}'>💍</emoji> <b>Your Marriage</b>"
        f"</blockquote>\n\n"
        f"<emoji id='{E_SPARKLE}'>✨</emoji> <b>Spouse:</b> {escape(name)}\n"
        f"<emoji id='{E_STAR}'>⭐️</emoji> <b>Anime:</b> {escape(anime)}\n"
        f"<b>{rem} Rarity:</b> {rarity}\n\n"
        f"<i>💍 Together since: {since_str}</i>",
        parse_mode=enums.ParseMode.HTML,
    )
