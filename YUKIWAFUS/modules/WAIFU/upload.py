"""
/upload — sudo-only waifu uploader.

Usage (inside the UPLOAD_LOGGER channel only):
  Reply to a photo:  /upload <name> | <anime_name> | <rarity_number>
  With photo caption: same format in the caption of a photo message

Only SUDO_USERS / OWNER can trigger this.
The bot logs every upload back to the same UPLOAD_LOGGER channel.
Uploaded waifus are stored in MongoDB (uploaddb) and are served
alternately with API waifus during spawns.
"""
import time
from datetime import datetime
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import uploaddb, sudoersdb
from YUKIWAFUS.logging import LOGGER
from YUKIWAFUS.utils.rarity import rarity_by_number, rarity_display_list, rarity_emoji

log = LOGGER(__name__)

_OWNER_ID = config.OWNER_ID


async def _is_sudo(user_id: int) -> bool:
    """Runtime sudo check — covers both config SUDO_USERS and DB-added sudoers."""
    if user_id == _OWNER_ID:
        return True
    if user_id in config.SUDO_USERS:
        return True
    return bool(await sudoersdb.find_one({"user_id": user_id}))


def _sudo_filter():
    async def _check(_, __, message):
        if not message.from_user:
            return False
        return await _is_sudo(message.from_user.id)
    return filters.create(_check)


_sudo_only = _sudo_filter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_args(text: str) -> tuple[str, str, int] | None:
    """
    Parse 'name | anime | rarity_number' from command args.
    Returns (name, anime, rarity_num) or None on bad input.
    """
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        return None
    name       = parts[0].strip()
    anime_name = parts[1].strip()
    try:
        rarity_num = int(parts[2].strip())
    except ValueError:
        return None
    if not name or not anime_name:
        return None
    return name, anime_name, rarity_num


async def _next_id() -> str:
    """Generate a sequential upload ID atomically using a counter document."""
    from YUKIWAFUS.database.Mangodb import mongodb
    counters = mongodb.counters
    doc = await counters.find_one_and_update(
        {"_id": "upload_waifu"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = doc.get("seq", 1)
    return f"UPL-{seq:04d}"


# ── /upload command ───────────────────────────────────────────────────────────

@app.on_message(
    filters.command("upload")
    & _sudo_only
)
async def upload_handler(client: Client, message: Message):
    # ── Gate: only allowed inside the UPLOAD_LOGGER channel ──────────────────
    if config.UPLOAD_LOGGER and message.chat.id != config.UPLOAD_LOGGER:
        return await message.reply_text(
            "⚠️ <b>/upload only works inside the designated upload logger channel.</b>",
            parse_mode=enums.ParseMode.HTML,
        )

    if not config.UPLOAD_LOGGER:
        return await message.reply_text(
            "❌ <b>UPLOAD_LOGGER</b> is not configured in config. "
            "Add the channel ID to your environment.",
            parse_mode=enums.ParseMode.HTML,
        )

    user      = message.from_user
    photo     = None
    args_raw  = ""

    # ── Resolve photo + args ──────────────────────────────────────────────────
    # Case 1: command sent as a caption on a photo message
    if message.photo:
        photo    = message.photo
        args_raw = " ".join(message.command[1:]).strip()

    # Case 2: command is a text reply to a photo message
    elif message.reply_to_message and message.reply_to_message.photo:
        photo    = message.reply_to_message.photo
        args_raw = " ".join(message.command[1:]).strip()

    else:
        return await message.reply_text(
            "<b>Usage:</b>\n"
            "1️⃣ Send a photo with caption:\n"
            "   <code>/upload Name | Anime Name | Rarity Number</code>\n\n"
            "2️⃣ Reply to a photo:\n"
            "   <code>/upload Name | Anime Name | Rarity Number</code>\n\n"
            "Use /rarity to see rarity numbers.",
            parse_mode=enums.ParseMode.HTML,
        )

    if not args_raw:
        return await message.reply_text(
            "❌ Missing arguments.\n"
            "<code>/upload Name | Anime Name | Rarity Number</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    parsed = _parse_args(args_raw)
    if not parsed:
        return await message.reply_text(
            "❌ Bad format. Use:\n"
            "<code>/upload Name | Anime Name | Rarity Number</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    name, anime_name, rarity_num = parsed

    rarity_info = rarity_by_number(rarity_num)
    if not rarity_info:
        return await message.reply_text(
            f"❌ Invalid rarity number <b>{rarity_num}</b>.\n"
            f"Use /rarity to see the list.",
            parse_mode=enums.ParseMode.HTML,
        )

    rarity_emoji_str, rarity_name = rarity_info

    # ── Download & forward photo to get a stable file_id ─────────────────────
    processing = await message.reply_text("⏳ Uploading waifu...")

    try:
        # Forward the photo to the logger channel to get a permanent file_id
        # We re-send as a new photo with caption so it's self-contained
        waifu_id   = await _next_id()
        now_ts     = time.time()
        now_str    = datetime.utcnow().strftime("%d %b %Y • %H:%M UTC")
        added_by   = user.first_name

        log_caption = (
            f"<blockquote>"
            f"🌸 <b>Waifu Uploaded!</b>"
            f"</blockquote>\n\n"
            f"📛 <b>Name:</b> {escape(name)}\n"
            f"🎌 <b>Anime:</b> {escape(anime_name)}\n"
            f"{rarity_emoji_str} <b>Rarity:</b> {rarity_name}\n"
            f"🆔 <b>ID:</b> <code>{waifu_id}</code>\n\n"
            f"<blockquote>"
            f"👤 <b>Uploaded by:</b> <a href='tg://user?id={user.id}'>{escape(added_by)}</a>\n"
            f"🕐 <b>Time:</b> {now_str}"
            f"</blockquote>"
        )

        # Send to UPLOAD_LOGGER and capture the file_id
        sent = await client.send_photo(
            chat_id=config.UPLOAD_LOGGER,
            photo=photo.file_id,
            caption=log_caption,
            parse_mode=enums.ParseMode.HTML,
        )
        stored_file_id = sent.photo.file_id

        # ── Save to MongoDB ───────────────────────────────────────────────────
        doc = {
            "waifu_id":   waifu_id,
            "name":       name,
            "anime_name": anime_name,
            "rarity":     rarity_name,
            "rarity_num": rarity_num,
            "img_url":    stored_file_id,   # Telegram file_id (works as photo)
            "event_tag":  anime_name,
            "added_by":   added_by,
            "added_by_id": user.id,
            "timestamp":  now_ts,
            "source":     "upload",
        }
        await uploaddb.insert_one(doc)

        await processing.edit_text(
            f"✅ <b>Waifu saved!</b>\n\n"
            f"📛 <b>{escape(name)}</b>\n"
            f"🎌 <b>Anime:</b> {escape(anime_name)}\n"
            f"{rarity_emoji_str} <b>Rarity:</b> {rarity_name}\n"
            f"🆔 <b>ID:</b> <code>{waifu_id}</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    except Exception as e:
        log.error(f"/upload failed: {e}")
        await processing.edit_text(f"❌ Upload failed: {e}")


# ── /dlupload command ─────────────────────────────────────────────────────────

@app.on_message(filters.command("dlupload") & _sudo_only)
async def dlupload_handler(client: Client, message: Message):
    """
    /dlupload <UPL-XXXX>
    Delete an incorrectly uploaded waifu from the database.
    """
    if len(message.command) < 2:
        return await message.reply_text(
            "<blockquote>⚠️ <b>Usage:</b> <code>/dlupload UPL-XXXX</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    waifu_id = message.command[1].strip().upper()

    doc = await uploaddb.find_one({"waifu_id": waifu_id})
    if not doc:
        return await message.reply_text(
            f"<blockquote>❌ <b>No waifu found with ID</b> <code>{waifu_id}</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    name       = doc.get("name", "?")
    anime_name = doc.get("anime_name", "?")
    rarity     = doc.get("rarity", "?")

    result = await uploaddb.delete_one({"waifu_id": waifu_id})

    if result.deleted_count:
        await message.reply_text(
            f"<blockquote>✅ <b>Waifu Deleted!</b></blockquote>\n\n"
            f"📛 <b>Name:</b> {escape(name)}\n"
            f"🎌 <b>Anime:</b> {escape(anime_name)}\n"
            f"✨ <b>Rarity:</b> {rarity}\n"
            f"🆔 <b>ID:</b> <code>{waifu_id}</code>\n\n"
            f"<i>Removed from spawn pool permanently.</i>",
            parse_mode=enums.ParseMode.HTML,
        )
        log.info(f"[dlupload] Deleted waifu {waifu_id} ({name}) by {message.from_user.id}")
    else:
        await message.reply_text(
            f"<blockquote>❌ <b>Failed to delete</b> <code>{waifu_id}</code>. Try again.</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )


# ── /rarity command ───────────────────────────────────────────────────────────

@app.on_message(
    filters.command("rarity")
    & _sudo_only
)
async def rarity_handler(client: Client, message: Message):
    """Show the full rarity list with numbers and emojis."""
    text = (
        "<blockquote>"
        "<b>🎭 Rarity List</b>"
        "</blockquote>\n\n"
        + rarity_display_list()
        + "\n\n"
        "<i>Use the number when uploading:\n"
        "<code>/upload Name | Anime | 3</code></i>"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
