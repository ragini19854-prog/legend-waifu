import asyncio
import time
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import (
    Message,
)

from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb, balancedb, game_statsdb
from YUKIWAFUS.utils.helpers import sc
from YUKIWAFUS.utils.styled_buttons import btn, row, to_pyrogram, inject_styled

from YUKIWAFUS.modules.WAIFU.spawn import active_spawns, _blocked_users

guessed_chats: set  = set()
cooldowns:     dict = {}

COOLDOWN_SEC  = 10
COINS_REWARD  = 40
WAIFU_TIMEOUT = 120

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}


def _on_cooldown(user_id: int) -> bool:
    return (time.time() - cooldowns.get(user_id, 0)) < COOLDOWN_SEC

def _remaining_cd(user_id: int) -> int:
    return max(0, int(COOLDOWN_SEC - (time.time() - cooldowns.get(user_id, 0))))

def _set_cooldown(user_id: int):
    cooldowns[user_id] = time.time()


def _spam_blocked(chat_id: int, user_id: int) -> int:
    key     = (chat_id, user_id)
    unblock = _blocked_users.get(key)
    if unblock:
        remaining = unblock - time.time()
        if remaining > 0:
            return int(remaining)
        _blocked_users.pop(key, None)
    return 0


def _normalize(s: str) -> str:
    return s.lower().strip().replace("-", " ").replace("_", " ")

def _is_correct(guess: str, correct: str) -> bool:
    g = _normalize(guess)
    c = _normalize(correct)
    if g == c:
        return True
    g_parts = g.split()
    c_parts = c.split()
    if sorted(g_parts) == sorted(c_parts):
        return True
    if len(c_parts) > 1 and g == c_parts[0]:
        return True
    if len(g_parts) >= 2 and all(p in c_parts for p in g_parts):
        return True
    return False


async def _add_to_collection(user_id: int, username: str, first_name: str, waifu: dict):
    await collectiondb.update_one(
        {"user_id": user_id},
        {
            "$set":  {"username": username, "first_name": first_name},
            "$push": {"waifus": waifu},
        },
        upsert=True,
    )

async def _add_coins(user_id: int, amount: int) -> int:
    result = await balancedb.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"coins": amount}},
        upsert=True,
        return_document=True,
    )
    return (result or {}).get("coins", amount)

async def _inc_guesses(user_id: int):
    await game_statsdb.update_one(
        {"user_id": user_id},
        {"$inc": {"total_guesses": 1}},
        upsert=True,
    )


@app.on_message(filters.command(["guess", "grab", "hunt", "collect", "protecc"]))
async def guess_handler(client: Client, message: Message):
    chat_id = message.chat.id
    user    = message.from_user
    user_id = user.id

    mention = f"<a href='tg://user?id={user_id}'>{escape(user.first_name)}</a>"

    block_remaining = _spam_blocked(chat_id, user_id)
    if block_remaining:
        mins     = block_remaining // 60
        secs     = block_remaining % 60
        time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>🚫</emoji> "
            f"<b>{sc('You are blocked from guessing')}!</b>\n\n"
            f"{sc('Reason')} : {sc('Spamming messages in this group')}.\n"
            f"{sc('Unblocks in')} : <b>{time_str}</b>\n\n"
            f"<i>{sc('Stop spamming and wait for the timer to expire')}.</i>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if _on_cooldown(user_id):
        return await message.reply_text(
            f"<blockquote>"
            f"⏳ <b>{sc('Cooldown')}!</b> "
            f"{sc('Wait')} <b>{_remaining_cd(user_id)}s</b> {sc('before guessing again')}."
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if chat_id not in active_spawns:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('No waifu is active right now')}!</b>\n"
            f"<i>{sc('Wait for one to spawn')}~</i>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if chat_id in guessed_chats:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('This waifu was already claimed')}!</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    guess = " ".join(message.command[1:]).strip()
    if not guess:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('Usage')} :</b> <code>/guess &lt;name&gt;</code>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    waifu        = active_spawns[chat_id]
    correct_name = waifu.get("name", "")
    rarity       = waifu.get("rarity", "Common")
    emoji        = RARITY_EMOJI.get(rarity, "◈")
    waifu_id     = waifu.get("waifu_id", "N/A")

    _set_cooldown(user_id)

    if _is_correct(guess, correct_name):
        guessed_chats.add(chat_id)
        active_spawns.pop(chat_id, None)

        time_taken  = int(time.time() - waifu.get("timestamp", time.time()))
        new_balance = await _add_coins(user_id, COINS_REWARD)

        await _add_to_collection(
            user_id,
            user.username or "",
            user.first_name,
            {**waifu, "timestamp": time.time()},
        )
        await _inc_guesses(user_id)

        raw_kb = [row(btn(f"🌸 {sc('My Harem')}", switch_current=f"col.{user_id}", style="success", emoji_id="6291837599254322363"))]

        msg = await message.reply_photo(
            photo=waifu["img_url"],
            caption=(
                f"<blockquote>"
                f"<emoji id='6291837599254322363'>🎊</emoji> "
                f"<b>{mention} {sc('guessed correctly')}!</b>"
                f"</blockquote>\n\n"
                f"<b>📛 {sc('Name')} :</b> {escape(correct_name)}\n"
                f"<b>{emoji} {sc('Rarity')} :</b> {rarity}\n"
                f"<b>🏷 {sc('Tag')} :</b> {waifu.get('event_tag', 'Standard')}\n"
                f"<b>🆔 {sc('ID')} :</b> <code>{waifu_id}</code>\n\n"
                f"<b>🌸 +{COINS_REWARD} {sc('Sakura')} →</b> "
                f"<b>{new_balance:,} 🌸</b>\n"
                f"<b>⏱ {sc('Time')} :</b> <b>{time_taken}s</b>"
            ),
            parse_mode=enums.ParseMode.HTML,
            reply_markup=to_pyrogram(raw_kb),
        )
        await inject_styled(msg.chat.id, msg.id, raw_kb)

    else:
        msg_id   = waifu.get("message_id")
        raw_kb   = None
        if msg_id:
            safe_cid = str(chat_id).replace("-100", "")
            raw_kb   = [row(btn(f"👀 {sc('View Waifu')}", url=f"https://t.me/c/{safe_cid}/{msg_id}", style="primary", emoji_id="5249244862359812334"))]

        msg = await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('Wrong')}!</b> "
            f"{sc('Try again')}~ 🕵️"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
            reply_markup=to_pyrogram(raw_kb) if raw_kb else None,
        )
        if raw_kb:
            await inject_styled(msg.chat.id, msg.id, raw_kb)
