# YUKIWAFUS — Telegram Waifu Collection Bot

## Project Overview
YUKIWAFUS is a Telegram bot for group chats where users guess, collect, trade, and battle anime characters (waifus). Built with Python using the Pyrogram framework and MongoDB for data storage.

## Running the Bot
The bot runs as a console process via the **Start application** workflow:
```
python3 -m YUKIWAFUS
```

## Required Configuration (Secrets)
The bot requires these secrets to be set before it can start:
- `API_ID` — Telegram API ID (from my.telegram.org)
- `API_HASH` — Telegram API Hash (from my.telegram.org)
- `BOT_TOKEN` — Bot token from @BotFather
- `MONGO_DB_URI` — MongoDB connection string (MongoDB Atlas or self-hosted)

## Optional Configuration
- `OWNER_ID` — Telegram user ID of the bot owner
- `SUDO_USERS` — Space-separated Telegram user IDs with sudo access
- `LOG_CHANNEL` — Telegram channel ID for bot logs (e.g., -100xxxxxxxxxx)
- `SUPPORT_CHAT` — URL to support chat (e.g., https://t.me/yourchat)
- `UPDATE_CHANNEL` — URL to update channel (e.g., https://t.me/yourchannel)
- `WAIFU_API_URL` — Waifu API URL (default: https://wafus.vercel.app)
- `WAIFU_API_KEY` — API key for waifu service
- `GUESS_COINS` — Coins awarded per correct guess (default: 40)
- `BATTLE_REWARD` — Coins awarded per battle win (default: 100)
- `CLAIM_COOLDOWN` — Seconds between daily claims (default: 86400)

## Configuration Notes
- Config is loaded from the `Simple.env` file OR environment secrets
- The bot reads secrets at startup — restart the workflow after changing secrets
- `SUPPORT_CHAT` and `UPDATE_CHANNEL` must be valid `https://` URLs if set

## User Preferences
