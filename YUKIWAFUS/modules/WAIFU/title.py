import uuid
from datetime import datetime
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    Message,
)

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import balancedb, collectiondb, titlesdb
from YUKIWAFUS.utils.helpers import sc
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled, edit_styled_caption

TITLES_PER_PAGE = 5

_TIERS = [
    (5000, "🟡", "Legendary"),
    (2000, "🟣", "Epic"),
    (500,  "🔵", "Rare"),
    (0,    "⚪", "Common"),
]

def get_tier(price: int) -> tuple[str, str]:
    for threshold, emoji, name in _TIERS:
        if price >= threshold:
            return emoji, name
    return "⚪", "Common"


async def get_all_titles() -> list:
    cursor = titlesdb.find({"type": "catalog"}).sort("price", 1)
    return await cursor.to_list(length=None)

async def get_title(title_id: str) -> dict | None:
    return await titlesdb.find_one({"type": "catalog", "title_id": title_id})

async def get_balance(user_id: int) -> int:
    doc = await balancedb.find_one({"user_id": user_id})
    return doc.get("coins", 0) if doc else 0

async def deduct_coins(user_id: int, amount: int) -> int:
    result = await balancedb.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"coins": -amount}},
        upsert=True,
        return_document=True,
    )
    return (result or {}).get("coins", 0)

async def get_owned_titles(user_id: int) -> list:
    doc = await collectiondb.find_one({"user_id": user_id})
    return doc.get("owned_titles", []) if doc else []

async def get_equipped_title(user_id: int) -> str | None:
    doc = await collectiondb.find_one({"user_id": user_id})
    return doc.get("equipped_title") if doc else None


def _titles_nav_kb(page: int, total_pages: int, user_id: int) -> list:
    nav = []
    if page > 0:
        nav.append(btn("◀️", callback_data=f"tp:{page-1}:{user_id}", style="primary", emoji_id="5238162283368035495"))
    if page < total_pages - 1:
        nav.append(btn("▶️", callback_data=f"tp:{page+1}:{user_id}", style="primary", emoji_id="5253539825360843975"))

    rows = []
    if nav:
        rows.append(nav)
    rows.append([btn(f"🎭 {sc('My Titles')}", callback_data=f"mytitles_cb:{user_id}", style="success", emoji_id="6291837599254322363")])
    return rows


async def _send_titles_page(target, page: int, user_id: int, edit: bool):
    all_t = await get_all_titles()

    if not all_t:
        text = (
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('No titles in shop yet')}!</b>"
            f"</blockquote>\n\n"
            f"<i>{sc('Ask an admin to add some')}~</i>"
        )
        if edit:
            await target.message.edit_text(text, parse_mode=enums.ParseMode.HTML)
            await target.answer()
        else:
            await target.reply_text(text, parse_mode=enums.ParseMode.HTML)
        return

    total       = len(all_t)
    total_pages = max(1, -(-total // TITLES_PER_PAGE))
    page        = max(0, min(page, total_pages - 1))
    page_items  = all_t[page * TITLES_PER_PAGE : (page + 1) * TITLES_PER_PAGE]

    owned    = await get_owned_titles(user_id)
    equipped = await get_equipped_title(user_id)

    caption = (
        f"<blockquote>"
        f"<emoji id='6291837599254322363'>🌸</emoji> "
        f"<b>{sc('Title Shop')} — {sc('Page')} {page + 1}/{total_pages}</b>"
        f"</blockquote>\n\n"
    )

    for t in page_items:
        emoji, rarity = get_tier(t["price"])
        tags = ""
        if t["title_id"] == equipped:
            tags += " <b>⚡ Equipped</b>"
        elif t["title_id"] in owned:
            tags += " <b>✅ Owned</b>"
        caption += (
            f"{emoji} <b>✦ {escape(t['name'])} ✦</b>{tags}\n"
            f"   🆔 <code>{t['title_id']}</code>  ·  "
            f"🌟 {rarity}  ·  "
            f"🪙 <b>{t['price']:,}</b> 🌸\n"
            f"   📝 {escape(t.get('description', '—'))}\n\n"
        )

    caption += f"<i>{sc('Use')} <code>/buytitle &lt;id&gt;</code> {sc('to purchase')}~</i>"

    raw_kb = _titles_nav_kb(page, total_pages, user_id)

    if edit:
        await edit_styled_caption(
            target.message.chat.id,
            target.message.id,
            caption,
            raw_kb,
        )
        await target.answer()
    else:
        msg = await target.reply_photo(
            photo        = config.WAIFU_PICS[0],
            caption      = caption,
            parse_mode   = enums.ParseMode.HTML,
            reply_markup = to_pyrogram(raw_kb),
            has_spoiler  = True,
        )
        await inject_styled(msg.chat.id, msg.id, raw_kb)


@app.on_message(filters.command(["titles", "titleshop", "titlemenu"]))
async def titles_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    await _send_titles_page(message, page=0, user_id=user_id, edit=False)


@app.on_callback_query(filters.regex(r"^tp:(\d+):(\d+)$"))
async def titles_page_cb(client: Client, cq: CallbackQuery):
    _, page, uid = cq.data.split(":")
    page = int(page)
    uid  = int(uid)

    if cq.from_user.id != uid:
        return await cq.answer(sc("Not your menu!"), show_alert=True)

    await _send_titles_page(cq, page=page, user_id=uid, edit=True)


@app.on_message(filters.command("buytitle"))
async def buytitle_cmd(client: Client, message: Message):
    user_id = message.from_user.id

    if len(message.command) < 2:
        return await message.reply_text(
            f"<blockquote><emoji id='6001602353843672777'>⚠️</emoji> <b>{sc('Usage')} :</b> <code>/buytitle &lt;title_id&gt;</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    title_id = message.command[1].strip().upper()
    title    = await get_title(title_id)

    if not title:
        return await message.reply_text(
            f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('Title not found')}!</b></blockquote>\n\n"
            f"<i>{sc('Use')} /titles {sc('to browse the shop')}~</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    owned = await get_owned_titles(user_id)
    if title_id in owned:
        return await message.reply_text(
            f"<blockquote><emoji id='6001602353843672777'>⚠️</emoji> <b>{sc('You already own this title')}!</b></blockquote>\n\n"
            f"<i>{sc('Use')} <code>/equipt {title_id}</code> {sc('to equip it')}~</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    bal   = await get_balance(user_id)
    price = title["price"]
    emoji, rarity = get_tier(price)

    if bal < price:
        return await message.reply_text(
            f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('Insufficient balance')}!</b></blockquote>\n\n"
            f"<b>🪙 {sc('Your Balance')} :</b> {bal:,} 🌸\n"
            f"<b>💸 {sc('Required')} :</b> {price:,} 🌸",
            parse_mode=enums.ParseMode.HTML,
        )

    raw_kb = [row(
        btn(f"✅ {sc('Confirm')}", callback_data=f"tbuy:{title_id}:{user_id}", style="success", emoji_id="6001483331709966655"),
        btn(f"❌ {sc('Cancel')}",  callback_data=f"tcancel:{user_id}",         style="danger",  emoji_id="5998834801472182366"),
    )]

    msg = await message.reply_photo(
        photo=config.WAIFU_PICS[0],
        caption=(
            f"<blockquote><emoji id='6291837599254322363'>🌸</emoji> <b>{sc('Confirm Purchase')}?</b></blockquote>\n\n"
            f"{emoji} <b>✦ {escape(title['name'])} ✦</b>\n"
            f"🌟 {sc('Rarity')} : <b>{rarity}</b>\n"
            f"📝 {escape(title.get('description', '—'))}\n\n"
            f"🪙 {sc('Price')} : <b>{price:,} 🌸</b>\n"
            f"💰 {sc('Your Balance')} : <b>{bal:,} 🌸</b>"
        ),
        parse_mode   = enums.ParseMode.HTML,
        reply_markup = to_pyrogram(raw_kb),
        has_spoiler  = True,
    )
    await inject_styled(msg.chat.id, msg.id, raw_kb)


@app.on_callback_query(filters.regex(r"^tbuy:([A-Z0-9]+):(\d+)$"))
async def title_buy_confirm_cb(client: Client, cq: CallbackQuery):
    parts    = cq.data.split(":")
    title_id = parts[1]
    uid      = int(parts[2])

    if cq.from_user.id != uid:
        return await cq.answer(sc("Not your purchase!"), show_alert=True)

    title = await get_title(title_id)
    if not title:
        return await cq.answer(sc("Title no longer available!"), show_alert=True)

    owned = await get_owned_titles(uid)
    if title_id in owned:
        return await cq.answer(sc("You already own this!"), show_alert=True)

    bal = await get_balance(uid)
    if bal < title["price"]:
        return await cq.answer(sc("Insufficient balance!"), show_alert=True)

    new_bal = await deduct_coins(uid, title["price"])
    await collectiondb.update_one(
        {"user_id": uid},
        {"$addToSet": {"owned_titles": title_id}},
        upsert=True,
    )

    emoji, rarity = get_tier(title["price"])

    await edit_styled_caption(
        cq.message.chat.id,
        cq.message.id,
        (
            f"<blockquote><emoji id='6001483331709966655'>✅</emoji> <b>{sc('Title Purchased')}!</b></blockquote>\n\n"
            f"{emoji} <b>✦ {escape(title['name'])} ✦</b>\n"
            f"🌟 {sc('Rarity')} : <b>{rarity}</b>\n\n"
            f"🪙 {sc('Remaining Balance')} : <b>{new_bal:,} 🌸</b>\n\n"
            f"<i>{sc('Use')} <code>/equipt {title_id}</code> {sc('to equip it')}~</i>"
        ),
        [],
    )
    await cq.answer(f"🎉 {sc('Title purchased')}!")


@app.on_callback_query(filters.regex(r"^tcancel:(\d+)$"))
async def title_buy_cancel_cb(client: Client, cq: CallbackQuery):
    uid = int(cq.data.split(":")[1])
    if cq.from_user.id != uid:
        return await cq.answer(sc("Not your action!"), show_alert=True)

    await edit_styled_caption(
        cq.message.chat.id,
        cq.message.id,
        f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('Purchase cancelled')}.</b></blockquote>",
        [],
    )
    await cq.answer()


@app.on_message(filters.command("equipt"))
async def equipt_cmd(client: Client, message: Message):
    user_id = message.from_user.id

    if len(message.command) < 2:
        return await message.reply_text(
            f"<blockquote><emoji id='6001602353843672777'>⚠️</emoji> <b>{sc('Usage')} :</b> <code>/equipt &lt;title_id&gt;</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    title_id = message.command[1].strip().upper()
    owned    = await get_owned_titles(user_id)

    if title_id not in owned:
        return await message.reply_text(
            f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('You do not own this title')}!</b></blockquote>\n\n"
            f"<i>{sc('Use')} /titles {sc('to browse & purchase')}~</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    title = await get_title(title_id)
    if not title:
        return await message.reply_text(
            f"<blockquote>❌ <b>{sc('Title data not found')}!</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    await collectiondb.update_one(
        {"user_id": user_id},
        {"$set": {"equipped_title": title_id}},
        upsert=True,
    )

    emoji, rarity = get_tier(title["price"])

    await message.reply_photo(
        photo=config.WAIFU_PICS[0],
        caption=(
            f"<blockquote><emoji id='6001483331709966655'>✅</emoji> <b>{sc('Title Equipped')}!</b></blockquote>\n\n"
            f"⚡ {emoji} <b>✦ {escape(title['name'])} ✦</b>\n"
            f"🌟 {sc('Rarity')} : <b>{rarity}</b>\n\n"
            f"<i>{sc('This now shows on your')} /profile {sc('card')}~</i>"
        ),
        parse_mode  = enums.ParseMode.HTML,
        has_spoiler = True,
    )


@app.on_message(filters.command("unequipt"))
async def unequipt_cmd(client: Client, message: Message):
    user_id  = message.from_user.id
    equipped = await get_equipped_title(user_id)

    if not equipped:
        return await message.reply_text(
            f"<blockquote><emoji id='6001602353843672777'>⚠️</emoji> <b>{sc('No title equipped')}!</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    await collectiondb.update_one(
        {"user_id": user_id},
        {"$unset": {"equipped_title": ""}},
    )

    await message.reply_text(
        f"<blockquote><emoji id='6001483331709966655'>✅</emoji> <b>{sc('Title unequipped')}.</b></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(filters.command("mytitles"))
async def mytitles_cmd(client: Client, message: Message):
    user_id  = message.from_user.id
    name     = message.from_user.first_name
    owned    = await get_owned_titles(user_id)
    equipped = await get_equipped_title(user_id)

    if not owned:
        return await message.reply_text(
            f"<blockquote><emoji id='6001602353843672777'>⚠️</emoji> <b>{sc('You own no titles yet')}!</b></blockquote>\n\n"
            f"<i>{sc('Visit')} /titles {sc('to browse the shop')}~</i>",
            parse_mode=enums.ParseMode.HTML,
        )

    caption = (
        f"<blockquote><emoji id='6291837599254322363'>🌸</emoji> <b>{escape(name)}'s {sc('Titles')}</b></blockquote>\n\n"
    )

    for tid in owned:
        t = await get_title(tid)
        if not t:
            continue
        emoji, _ = get_tier(t["price"])
        equip_tag = " <b>⚡</b>" if tid == equipped else ""
        caption += (
            f"  {emoji} <b>✦ {escape(t['name'])} ✦</b>{equip_tag}\n"
            f"     <code>/equipt {tid}</code>\n\n"
        )

    if equipped:
        t = await get_title(equipped)
        if t:
            emoji, _ = get_tier(t["price"])
            caption += (
                f"\n⚡ <b>{sc('Currently Equipped')} :</b>\n"
                f"   {emoji} <b>✦ {escape(t['name'])} ✦</b>"
            )

    await message.reply_photo(
        photo       = config.WAIFU_PICS[0],
        caption     = caption,
        parse_mode  = enums.ParseMode.HTML,
        has_spoiler = True,
    )


@app.on_callback_query(filters.regex(r"^mytitles_cb:(\d+)$"))
async def mytitles_cb(client: Client, cq: CallbackQuery):
    uid = int(cq.data.split(":")[1])
    if cq.from_user.id != uid:
        return await cq.answer(sc("Not your menu!"), show_alert=True)

    owned    = await get_owned_titles(uid)
    equipped = await get_equipped_title(uid)

    if not owned:
        return await cq.answer(sc("You own no titles yet!"), show_alert=True)

    text = (
        f"<blockquote><emoji id='6291837599254322363'>🌸</emoji> <b>{sc('My Titles')}</b></blockquote>\n\n"
    )
    for tid in owned:
        t = await get_title(tid)
        if not t:
            continue
        emoji, _ = get_tier(t["price"])
        equip_tag = " ⚡" if tid == equipped else ""
        text += f"  {emoji} <b>✦ {escape(t['name'])} ✦</b>{equip_tag}\n"

    await cq.message.reply_text(text, parse_mode=enums.ParseMode.HTML)
    await cq.answer()


@app.on_message(
    filters.command("addtitle")
    & filters.user(config.SUDO_USERS + [config.OWNER_ID])
)
async def addtitle_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            f"<b>{sc('Usage')} :</b>\n<code>/addtitle Name | Price | Description</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    raw   = " ".join(message.command[1:])
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) < 2:
        return await message.reply_text(
            f"<blockquote>⚠️ <b>{sc('Format')} :</b></blockquote>\n<code>/addtitle Name | Price | Description</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    name = parts[0]
    try:
        price = int(parts[1])
        if price <= 0:
            raise ValueError
    except ValueError:
        return await message.reply_text(
            f"<blockquote>❌ <b>{sc('Price must be a positive number')}!</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    description = parts[2] if len(parts) > 2 else ""

    if await titlesdb.find_one(
        {"type": "catalog", "name": {"$regex": f"^{name}$", "$options": "i"}}
    ):
        return await message.reply_text(
            f"<blockquote>⚠️ <b>{sc('A title with this name already exists')}!</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    title_id = str(uuid.uuid4())[:8].upper()

    await titlesdb.insert_one({
        "type":        "catalog",
        "title_id":    title_id,
        "name":        name,
        "price":       price,
        "description": description,
        "created_at":  datetime.utcnow(),
        "created_by":  message.from_user.id,
    })

    emoji, rarity = get_tier(price)

    await message.reply_text(
        f"<blockquote><emoji id='6001483331709966655'>✅</emoji> <b>{sc('Title Added')}!</b></blockquote>\n\n"
        f"{emoji} <b>✦ {escape(name)} ✦</b>\n"
        f"🆔 ID : <code>{title_id}</code>\n"
        f"🌟 {sc('Rarity')} : <b>{rarity}</b>\n"
        f"🪙 {sc('Price')} : <b>{price:,} 🌸</b>\n"
        f"📝 {escape(description)}",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(
    filters.command("deltitle")
    & filters.user(config.SUDO_USERS + [config.OWNER_ID])
)
async def deltitle_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            f"<b>{sc('Usage')} :</b> <code>/deltitle &lt;title_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    title_id = message.command[1].strip().upper()
    result   = await titlesdb.delete_one({"type": "catalog", "title_id": title_id})

    if result.deleted_count:
        await message.reply_text(
            f"<blockquote><emoji id='6001483331709966655'>✅</emoji> <b>{sc('Title Deleted')}!</b></blockquote>\n\n"
            f"🆔 <code>{title_id}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
    else:
        await message.reply_text(
            f"<blockquote><emoji id='5998834801472182366'>❌</emoji> <b>{sc('Title not found')}!</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
