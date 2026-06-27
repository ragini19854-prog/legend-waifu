"""
/propose — randomly propose to a waifu. 50/50 chance. One try per day.

Success → waifu photo + [✅ Accept | ❌ Reject] buttons
Failure → text message
"""
import random
from datetime import datetime, timezone
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import CallbackQuery, Message

from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import proposedb
from YUKIWAFUS.utils.api import get_random_waifu
from YUKIWAFUS.utils.rarity import rarity_emoji
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled

# ── NewsEmoji IDs ─────────────────────────────────────────────────────────────
E_PARTY    = "5461151367559141950"   # 🎉
E_CROSS    = "5210952531676504517"   # ❌
E_CHECK    = "5206607081334906820"   # ✔️
E_THUMBSUP = "5337080053119336309"   # 👍
E_THUMBDN  = "5449875686837726134"   # 👎
E_CROWN    = "5217822164362739968"   # 👑
E_SPARKLE  = "5325547803936572038"   # ✨
E_STAR     = "5438496463044752972"   # ⭐️
E_FIRE     = "5424972470023104089"   # 🔥
E_PREMIUM  = "5427168083074628963"   # 💎
E_WARNING  = "5447644880824181073"   # ⚠️
E_RAIN     = "5399913388845322366"   # 🌧
E_SNOW     = "5449449325434266744"   # ❄️
E_LOVE     = "5461151367559141950"   # 🎉 (reuse for love/celebrate)
E_MUSIC    = "5463107823946717464"   # 🎵


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


@app.on_message(filters.command("propose"))
async def propose_handler(client: Client, message: Message):
    user    = message.from_user
    user_id = user.id

    if await _used_today(user_id):
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{E_WARNING}'>⚠️</emoji> <b>You've already proposed today!</b>\n\n"
            f"<emoji id='{E_SNOW}'>❄️</emoji> Come back tomorrow to try your luck again~"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    await _mark_used(user_id)

    # ── 50 / 50 ───────────────────────────────────────────────────────────────
    if random.random() < 0.5:
        # ── Failure ───────────────────────────────────────────────────────────
        fails = [
            (E_CROSS,   "Your crush ran away! <i>Better luck next time~</i>"),
            (E_RAIN,    "Rejected! She said she only likes anime boys."),
            (E_CROSS,   "She vanished! Maybe she wasn't real after all..."),
            (E_SNOW,    "Your heart got broken today. Try again tomorrow!"),
            (E_RAIN,    "No luck today! The waifu gods weren't on your side."),
            (E_THUMBDN, "She ghosted you. Ouch. 💀"),
        ]
        eid, text = random.choice(fails)
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{eid}'>💔</emoji> <b>{text}</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    # ── Success — fetch a waifu ───────────────────────────────────────────────
    processing = await message.reply_text(
        f"<emoji id='{E_MUSIC}'>🎵</emoji> <i>Sending your proposal...</i>",
        parse_mode=enums.ParseMode.HTML,
    )

    waifu = await get_random_waifu()
    if not waifu:
        return await processing.edit_text(
            f"<emoji id='{E_CROSS}'>❌</emoji> Could not find a waifu right now. Try again!",
            parse_mode=enums.ParseMode.HTML,
        )

    await processing.delete()

    rarity  = waifu.get("rarity", "Common")
    r_emoji = rarity_emoji(rarity)
    name    = waifu.get("name", "Mystery Waifu")
    anime   = waifu.get("anime_name") or waifu.get("event_tag", "Unknown")
    img     = waifu.get("img_url", "")
    wid     = waifu.get("waifu_id", "N/A")

    caption = (
        f"<blockquote>"
        f"<emoji id='{E_PARTY}'>🎉</emoji> <b>A waifu accepted your proposal!</b>"
        f"</blockquote>\n\n"
        f"<emoji id='{E_SPARKLE}'>✨</emoji> <b>Name :</b> {escape(name)}\n"
        f"<emoji id='{E_STAR}'>⭐️</emoji> <b>Anime :</b> {escape(anime)}\n"
        f"<b>{r_emoji} Rarity :</b> {rarity}\n\n"
        f"<emoji id='{E_CROWN}'>👑</emoji> <i>Will you accept her? 💍</i>"
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

    if cq.from_user.id != user_id:
        return await cq.answer("This is not your proposal! 😤", show_alert=True)

    await cq.answer("💍 You accepted! She's yours forever~", show_alert=True)
    try:
        old = cq.message.caption or cq.message.text or ""
        new_text = (
            old + f"\n\n"
            f"<emoji id='{E_CHECK}'>✔️</emoji> <b>Accepted! 💍 Congratulations!</b>\n"
            f"<emoji id='{E_FIRE}'>🔥</emoji> <i>May your harem grow strong!</i>"
        )
        if cq.message.photo:
            await cq.message.edit_caption(new_text, parse_mode=enums.ParseMode.HTML)
        else:
            await cq.message.edit_text(new_text, parse_mode=enums.ParseMode.HTML)
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
        old = cq.message.caption or cq.message.text or ""
        new_text = (
            old + f"\n\n"
            f"<emoji id='{E_THUMBDN}'>👎</emoji> <b>Rejected.</b>\n"
            f"<emoji id='{E_RAIN}'>🌧</emoji> <i>Maybe tomorrow will be better~</i>"
        )
        if cq.message.photo:
            await cq.message.edit_caption(new_text, parse_mode=enums.ParseMode.HTML)
        else:
            await cq.message.edit_text(new_text, parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass
