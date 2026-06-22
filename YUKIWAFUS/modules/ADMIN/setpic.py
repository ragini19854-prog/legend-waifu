import io
import os

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.logging import LOGGER

log = LOGGER(__name__)

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets")

_VALID_TYPES = {
    "start": os.path.join(_ASSETS, "start.png"),
    "ping":  os.path.join(_ASSETS, "ping.png"),
    "help":  os.path.join(_ASSETS, "help.png"),
}

_USAGE = (
    "<blockquote>"
    "<b>🖼 /setpic — Set Bot Images</b>\n\n"
    "<b>Usage:</b> Reply to a photo with\n"
    "<code>/setpic start</code> — start command image\n"
    "<code>/setpic ping</code>  — ping command image\n"
    "<code>/setpic help</code>  — help command image\n\n"
    "<b>Valid types:</b> start, ping, help"
    "</blockquote>"
)


@app.on_message(filters.command("setpic") & filters.user([config.OWNER_ID]))
async def setpic_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(_USAGE, parse_mode=enums.ParseMode.HTML)

    pic_type = message.command[1].lower().strip()

    if pic_type not in _VALID_TYPES:
        return await message.reply_text(
            f"<blockquote>❌ <b>Unknown type:</b> <code>{pic_type}</code>\n\n"
            f"Valid: <code>start</code> · <code>ping</code> · <code>help</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    photo_msg = None
    if message.reply_to_message and message.reply_to_message.photo:
        photo_msg = message.reply_to_message
    elif message.photo:
        photo_msg = message

    if not photo_msg:
        return await message.reply_text(
            "<blockquote>❌ <b>No photo found!</b>\n\n"
            "Reply to a photo with this command, or send the photo with the command as caption.</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    processing = await message.reply_text(
        f"<blockquote>⏳ <b>Saving {pic_type} image...</b></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    try:
        os.makedirs(_ASSETS, exist_ok=True)

        dest = _VALID_TYPES[pic_type]
        downloaded = await client.download_media(photo_msg.photo, in_memory=True)

        if isinstance(downloaded, io.BytesIO):
            with open(dest, "wb") as f:
                f.write(downloaded.getvalue())
        else:
            return await processing.edit_text(
                "<blockquote>❌ <b>Failed to download photo.</b></blockquote>",
                parse_mode=enums.ParseMode.HTML,
            )

        size_kb = os.path.getsize(dest) // 1024

        await processing.edit_text(
            f"<blockquote>"
            f"✅ <b>{pic_type.capitalize()} image updated!</b>\n\n"
            f"📁 Saved to: <code>assets/{pic_type}.png</code>\n"
            f"📦 Size: <b>{size_kb} KB</b>\n\n"
            f"<i>The new image will be used immediately — no restart needed.</i>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        log.info(f"Owner set {pic_type} image ({size_kb} KB)")

    except Exception as e:
        log.error(f"setpic failed for {pic_type}: {e}")
        await processing.edit_text(
            f"<blockquote>❌ <b>Failed to save image:</b> <code>{e}</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
