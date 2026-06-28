"""
/premiumwaifu  — show the buyable premium waifu catalogue (paginated)
/buywaifu <id> — purchase a waifu from the catalogue with Sakura coins
"""
import asyncio
import math
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import CallbackQuery, Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import balancedb, collectiondb, gbansdb
from YUKIWAFUS.utils.api import find_waifu
from YUKIWAFUS.utils.rarity import rarity_emoji
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled

# ── NewsEmoji IDs ─────────────────────────────────────────────────────────────
E_SHOP    = "5231005931550030290"   # 💸
E_CROWN   = "5217822164362739968"   # 👑
E_STAR    = "5438496463044752972"   # ⭐️
E_CHECK   = "5206607081334906820"   # ✔️
E_CROSS   = "5210952531676504517"   # ❌
E_WARNING = "5447644880824181073"   # ⚠️
E_COINS   = "5233326571099534068"   # 💸
E_SPARKLE = "5325547803936572038"   # ✨

# ── Premium Waifu Catalogue ───────────────────────────────────────────────────
PREMIUM_SHOP = [
    # ─ Re:Zero ─
    {"id": "rem",          "name": "Rem",             "anime": "Re:Zero",            "price": 1500},
    {"id": "emilia",       "name": "Emilia",          "anime": "Re:Zero",            "price": 1300},
    {"id": "beatrice",     "name": "Beatrice",        "anime": "Re:Zero",            "price": 1300},
    # ─ Darling in the FranXX ─
    {"id": "zero two",     "name": "Zero Two",        "anime": "Darling in the FranXX", "price": 1500},
    # ─ Sword Art Online ─
    {"id": "asuna",        "name": "Asuna",           "anime": "Sword Art Online",   "price": 1300},
    {"id": "sinon",        "name": "Sinon",           "anime": "Sword Art Online",   "price": 1200},
    {"id": "alice",        "name": "Alice",           "anime": "SAO: Alicization",   "price": 1400},
    # ─ Attack on Titan ─
    {"id": "mikasa",       "name": "Mikasa",          "anime": "Attack on Titan",    "price": 1300},
    # ─ Demon Slayer ─
    {"id": "nezuko",       "name": "Nezuko",          "anime": "Demon Slayer",       "price": 1400},
    {"id": "mitsuri",      "name": "Mitsuri",         "anime": "Demon Slayer",       "price": 1300},
    # ─ Naruto ─
    {"id": "hinata",       "name": "Hinata",          "anime": "Naruto",             "price": 1200},
    # ─ Chainsaw Man ─
    {"id": "power",        "name": "Power",           "anime": "Chainsaw Man",       "price": 1400},
    {"id": "makima",       "name": "Makima",          "anime": "Chainsaw Man",       "price": 1500},
    # ─ Jujutsu Kaisen ─
    {"id": "nobara",       "name": "Nobara",          "anime": "Jujutsu Kaisen",     "price": 1200},
    # ─ My Hero Academia ─
    {"id": "toga",         "name": "Toga",            "anime": "My Hero Academia",   "price": 1200},
    {"id": "ochako",       "name": "Ochako",          "anime": "My Hero Academia",   "price": 1200},
    # ─ One Piece ─
    {"id": "nami",         "name": "Nami",            "anime": "One Piece",          "price": 1300},
    {"id": "robin",        "name": "Robin",           "anime": "One Piece",          "price": 1300},
    # ─ Fairy Tail ─
    {"id": "erza",         "name": "Erza",            "anime": "Fairy Tail",         "price": 1300},
    {"id": "lucy",         "name": "Lucy",            "anime": "Fairy Tail",         "price": 1200},
    # ─ Overlord ─
    {"id": "albedo",       "name": "Albedo",          "anime": "Overlord",           "price": 1400},
    {"id": "shalltear",    "name": "Shalltear",       "anime": "Overlord",           "price": 1300},
    # ─ KonoSuba ─
    {"id": "aqua",         "name": "Aqua",            "anime": "KonoSuba",           "price": 1200},
    {"id": "megumin",      "name": "Megumin",         "anime": "KonoSuba",           "price": 1400},
    # ─ Date A Live ─
    {"id": "tohka",        "name": "Tohka",           "anime": "Date A Live",        "price": 1300},
    # ─ No Game No Life ─
    {"id": "shiro",        "name": "Shiro",           "anime": "No Game No Life",    "price": 1300},
    # ─ Toradora ─
    {"id": "taiga",        "name": "Taiga",           "anime": "Toradora",           "price": 1200},
    # ─ Quintessential Quintuplets ─
    {"id": "miku nakano",  "name": "Miku Nakano",     "anime": "5-Toubun no Hanayome","price": 1300},
    {"id": "ichika",       "name": "Ichika",          "anime": "5-Toubun no Hanayome","price": 1200},
    # ─ Violet Evergarden ─
    {"id": "violet",       "name": "Violet Evergarden","anime": "Violet Evergarden", "price": 1400},
    # ─ Fullmetal Alchemist ─
    {"id": "winry",        "name": "Winry",           "anime": "Fullmetal Alchemist","price": 1200},
    # ─ Bleach ─
    {"id": "orihime",      "name": "Orihime",         "anime": "Bleach",             "price": 1200},
    {"id": "yoruichi",     "name": "Yoruichi",        "anime": "Bleach",             "price": 1300},
    # ─ Neon Genesis Evangelion ─
    {"id": "rei ayanami",  "name": "Rei Ayanami",     "anime": "Evangelion",         "price": 1400},
    {"id": "asuka langley","name": "Asuka Langley",   "anime": "Evangelion",         "price": 1400},
    # ─ Black Clover ─
    {"id": "noelle",       "name": "Noelle",          "anime": "Black Clover",       "price": 1200},
    # ─ Fire Force ─
    {"id": "tamaki",       "name": "Tamaki",          "anime": "Fire Force",         "price": 1200},
    # ─ Tokyo Ghoul ─
    {"id": "touka",        "name": "Touka",           "anime": "Tokyo Ghoul",        "price": 1200},
    # ─ High School DxD ─
    {"id": "rias",         "name": "Rias",            "anime": "High School DxD",    "price": 1400},
    {"id": "akeno",        "name": "Akeno",           "anime": "High School DxD",    "price": 1300},
    # ─ Fate ─
    {"id": "saber",        "name": "Saber",           "anime": "Fate/Stay Night",    "price": 1400},
    {"id": "rin tohsaka",  "name": "Rin Tohsaka",     "anime": "Fate/Stay Night",    "price": 1300},
    # ─ Kaguya-sama ─
    {"id": "kaguya",       "name": "Kaguya",          "anime": "Kaguya-sama",        "price": 1300},
    # ─ Spy x Family ─
    {"id": "yor",          "name": "Yor",             "anime": "Spy x Family",       "price": 1300},
    # ─ Dungeon ni Deai ─
    {"id": "hestia",       "name": "Hestia",          "anime": "DanMachi",           "price": 1300},
    # ─ Dragon Maid ─
    {"id": "tohru",        "name": "Tohru",           "anime": "Miss Kobayashi's Dragon Maid","price": 1200},
    # ─ Madoka Magica ─
    {"id": "homura",       "name": "Homura",          "anime": "Madoka Magica",      "price": 1300},
    # ─ Frieren ─
    {"id": "frieren",      "name": "Frieren",         "anime": "Frieren",            "price": 1400},
    # ─ Mushoku Tensei ─
    {"id": "eris",         "name": "Eris",            "anime": "Mushoku Tensei",     "price": 1200},
    {"id": "roxy",         "name": "Roxy",            "anime": "Mushoku Tensei",     "price": 1300},
    # ─ Oshi No Ko ─
    {"id": "ruby",         "name": "Ruby",            "anime": "Oshi No Ko",         "price": 1200},
    # ─ Solo Leveling ─
    {"id": "cha hae-in",   "name": "Cha Hae-In",      "anime": "Solo Leveling",      "price": 1300},
    # ─ Goblin Slayer ─
    {"id": "priestess",    "name": "Priestess",       "anime": "Goblin Slayer",      "price": 1200},
    # ─ Rosario + Vampire ─
    {"id": "moka",         "name": "Moka",            "anime": "Rosario+Vampire",    "price": 1200},
    # ─ Made in Abyss ─
    {"id": "riko",         "name": "Riko",            "anime": "Made in Abyss",      "price": 1200},
    # ─ Danganronpa ─
    {"id": "junko",        "name": "Junko Enoshima",  "anime": "Danganronpa",        "price": 1300},
    # ─ Tower of God ─
    {"id": "yuri",         "name": "Yuri Ha-Yoon",    "anime": "Tower of God",       "price": 1200},
    # ─ The Eminence in Shadow ─
    {"id": "alpha",        "name": "Alpha",           "anime": "The Eminence in Shadow","price": 1300},
    # ─ Black Butler ─
    {"id": "elizabeth",    "name": "Elizabeth",       "anime": "Black Butler",       "price": 1200},
]

SHOP_PAGE_SIZE = 10
_shop_cache: dict = {}   # id → img_url, populated lazily


def _shop_id_to_entry(shop_id: str) -> dict | None:
    shop_id = shop_id.strip().lower()
    for e in PREMIUM_SHOP:
        if e["id"] == shop_id or e["name"].lower() == shop_id:
            return e
    return None


async def _fetch_img(name: str) -> str:
    """Fetch image URL for a waifu name from the API (cached)."""
    key = name.lower()
    if key in _shop_cache:
        return _shop_cache[key]
    try:
        results = await find_waifu(name)
        if results:
            url = results[0].get("img_url", "")
            _shop_cache[key] = url
            return url
    except Exception:
        pass
    return ""


def _shop_page_text(page: int) -> tuple[str, int]:
    total  = len(PREMIUM_SHOP)
    pages  = max(1, math.ceil(total / SHOP_PAGE_SIZE))
    page   = max(0, min(page, pages - 1))
    start  = page * SHOP_PAGE_SIZE
    items  = PREMIUM_SHOP[start: start + SHOP_PAGE_SIZE]

    text = (
        f"<blockquote>"
        f"<emoji id='{E_CROWN}'>👑</emoji> <b>Premium Waifu Shop</b>\n"
        f"Page {page+1}/{pages} · {total} waifus available"
        f"</blockquote>\n\n"
        f"<emoji id='{E_WARNING}'>⚠️</emoji> <i>Prices: 1200–1500 🌸</i>\n"
        f"<i>Buy with:</i> <code>/buywaifu &lt;id&gt;</code>\n\n"
    )

    for i, entry in enumerate(items, start + 1):
        img = _shop_cache.get(entry["name"].lower(), "")
        img_link = f"<a href='{img}'>{escape(entry['name'])}</a>" if img else escape(entry["name"])
        text += (
            f"<b>{i}.</b> {img_link}\n"
            f"   🎌 {escape(entry['anime'])} · 💰 {entry['price']:,} 🌸\n"
            f"   <code>{entry['id']}</code>\n\n"
        )

    return text, pages


def _shop_kb(page: int, total_pages: int) -> list:
    nav = []
    if page > 0:
        nav.append(btn("◀️", callback_data=f"shop_page:{page-1}", style="primary"))
    if page < total_pages - 1:
        nav.append(btn("▶️", callback_data=f"shop_page:{page+1}", style="primary"))
    rows = []
    if nav:
        rows.append(nav)
    return rows


async def _preload_page(page: int):
    """Eagerly fetch image URLs for the current page in the background."""
    start = page * SHOP_PAGE_SIZE
    items = PREMIUM_SHOP[start: start + SHOP_PAGE_SIZE]
    tasks = [_fetch_img(e["name"]) for e in items if e["name"].lower() not in _shop_cache]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


# ── /premiumwaifu ─────────────────────────────────────────────────────────────

@app.on_message(filters.command("premiumwaifu"))
async def premiumwaifu_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if await gbansdb.find_one({"user_id": user_id}):
        return

    proc = await message.reply_text(
        f"<emoji id='{E_SPARKLE}'>✨</emoji> <i>Loading premium waifu shop...</i>",
        parse_mode=enums.ParseMode.HTML,
    )

    await _preload_page(0)
    text, total_pages = _shop_page_text(0)
    raw_kb = _shop_kb(0, total_pages)

    await proc.edit_text(
        text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=to_pyrogram(raw_kb) if raw_kb else None,
        disable_web_page_preview=True,
    )
    if raw_kb:
        await inject_styled(proc.chat.id, proc.id, raw_kb)


@app.on_callback_query(filters.regex(r"^shop_page:"))
async def shop_page_cb(client: Client, cq: CallbackQuery):
    page = int(cq.data.split(":")[1])
    await _preload_page(page)
    text, total_pages = _shop_page_text(page)
    raw_kb = _shop_kb(page, total_pages)

    try:
        await cq.message.edit_text(
            text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=to_pyrogram(raw_kb) if raw_kb else None,
            disable_web_page_preview=True,
        )
        if raw_kb:
            await inject_styled(cq.message.chat.id, cq.message.id, raw_kb)
    except Exception:
        pass
    await cq.answer()


# ── /buywaifu ─────────────────────────────────────────────────────────────────

@app.on_message(filters.command("buywaifu"))
async def buywaifu_handler(client: Client, message: Message):
    user    = message.from_user
    user_id = user.id

    if await gbansdb.find_one({"user_id": user_id}):
        return

    if len(message.command) < 2:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{E_WARNING}'>⚠️</emoji> <b>Usage:</b> <code>/buywaifu &lt;id&gt;</code>\n"
            f"See the list with /premiumwaifu"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    shop_id = " ".join(message.command[1:]).strip().lower()
    entry   = _shop_id_to_entry(shop_id)

    if not entry:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{E_CROSS}'>❌</emoji> <b>Waifu not found in premium shop.</b>\n"
            f"Use /premiumwaifu to see available IDs."
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    price = entry["price"]

    # Check balance
    bal_doc = await balancedb.find_one({"user_id": user_id})
    bal     = (bal_doc or {}).get("coins", 0)

    if bal < price:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='{E_CROSS}'>❌</emoji> <b>Not enough coins!</b>\n\n"
            f"<b>{escape(entry['name'])}</b> costs <b>{price:,} 🌸</b>\n"
            f"Your balance: <b>{bal:,} 🌸</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    # Fetch waifu from API
    proc    = await message.reply_text(f"<emoji id='{E_SPARKLE}'>✨</emoji> <i>Processing...</i>", parse_mode=enums.ParseMode.HTML)
    results = await find_waifu(entry["name"])

    if not results:
        return await proc.edit_text(
            f"<emoji id='{E_CROSS}'>❌</emoji> Could not fetch waifu data right now. Try again!",
            parse_mode=enums.ParseMode.HTML,
        )

    waifu  = results[0]
    rarity = waifu.get("rarity", "Common")
    rem    = rarity_emoji(rarity)

    # Deduct coins & add waifu
    await balancedb.update_one({"user_id": user_id}, {"$inc": {"coins": -price}})
    await collectiondb.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "first_name": user.first_name}, "$push": {"waifus": waifu}},
        upsert=True,
    )

    new_bal = bal - price
    img     = waifu.get("img_url", "")

    success_caption = (
        f"<blockquote>"
        f"<emoji id='{E_CHECK}'>✔️</emoji> <b>Purchase Successful!</b>"
        f"</blockquote>\n\n"
        f"<emoji id='{E_SPARKLE}'>✨</emoji> <b>Waifu:</b> {escape(entry['name'])}\n"
        f"<emoji id='{E_STAR}'>⭐️</emoji> <b>Anime:</b> {escape(entry['anime'])}\n"
        f"<b>{rem} Rarity:</b> {rarity}\n\n"
        f"<emoji id='{E_COINS}'>💸</emoji> Spent: <b>{price:,} 🌸</b>\n"
        f"<b>Balance:</b> {new_bal:,} 🌸\n\n"
        f"<i>Check your harem with /harem~</i>"
    )

    await proc.delete()
    if img:
        await message.reply_photo(photo=img, caption=success_caption, parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text(success_caption, parse_mode=enums.ParseMode.HTML)
