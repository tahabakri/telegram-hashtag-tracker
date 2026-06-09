"""
Telegram Hashtag Tracking Bot
=============================
Watches a Telegram group for campaign hashtags (in plain text AND photo
captions), logs every matching message to a CSV file (and, optionally, a
Google Sheet), and replies with a short randomised message to encourage
participation.

Built for a single time-boxed community campaign: simple, reliable, no
database. Configure the tracked hashtags and replies in the CONFIG block.

Quick start
-----------
  1. pip install -r requirements.txt
  2. Create a bot with @BotFather and copy the token.
  3. In BotFather: /setprivacy -> Disable   (so the bot can read all messages)
  4. Copy .env.example to .env and paste your token into BOT_TOKEN.
  5. Add the bot to your group as an ADMIN.
  6. python bot.py

See README.md for Google Sheets and 24/7 hosting notes.
"""

import os
import csv
import random
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

load_dotenv()

# =====================================================================
# CONFIG
# =====================================================================

# Telegram bot token — read from the environment (.env). Never hard-code it.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Group chat ID — only needed for the optional /stats command.
# How to find it: add the bot to the group, post any tracked hashtag, and
# look at the "Message Link" in entries.csv. Take the number after /c/ and
# prefix it with -100.  Example:  .../c/2515871/45  ->  -1002515871
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "0"))

# Hashtags to track (lowercase). EDIT THESE for your campaign.
TRACKED_HASHTAGS = ["#entry", "#proof", "#prediction"]

# Fun replies per hashtag — the bot picks one at random so it doesn't feel
# robotic. EDIT THESE freely; each hashtag can have any number of replies.
REPLIES = {
    "#entry": [
        "You're in! 🎉 logged ✅",
        "Entry counted 🙌 keep 'em coming!",
        "Nice one — that's logged 🚀",
    ],
    "#proof": [
        "Got it 💪 you're all set",
        "Locked in ✅ good luck out there!",
    ],
    "#prediction": [
        "Prediction's in 🎯 let's see if you nailed it",
        "Bold call 👀 logged — good luck!",
    ],
}

# Local backup file — always written, even when Google Sheets is enabled.
CSV_FILE = os.environ.get("CSV_FILE", "entries.csv")

# Google Sheets (optional). Enable by setting USE_GOOGLE_SHEETS=true in .env,
# placing your service-account key next to this file as creds.json, and
# sharing the sheet with the service-account email.
USE_GOOGLE_SHEETS = os.environ.get("USE_GOOGLE_SHEETS", "false").lower() == "true"
GSHEET_NAME = os.environ.get("GSHEET_NAME", "Campaign Entries")
GOOGLE_CREDS_FILE = os.environ.get("GOOGLE_CREDS_FILE", "creds.json")

CSV_HEADERS = [
    "Timestamp (UTC)", "Username", "User ID", "Full Name",
    "Hashtags", "Message Text", "Message Link", "Has Image",
]

# =====================================================================
# Logging
# =====================================================================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Set in main(): the Google Sheet worksheet handle (or None for CSV-only).
gsheet = None

# Remember processed message IDs so edits / re-sends aren't double-counted.
processed_messages = set()


# =====================================================================
# Pure helpers (no Telegram needed — these are unit-tested)
# =====================================================================
def find_hashtags(text, tracked=None):
    """Return the tracked hashtags that appear as WHOLE words in `text`.

    Whole-word, case-insensitive matching: "#entry" matches "#Entry" and
    "#ENTRY" but NOT "#entryfinal", so lookalike tags never count by accident.
    Trailing punctuation is ignored, and repeats are de-duplicated.
    """
    if tracked is None:
        tracked = TRACKED_HASHTAGS
    if not text:
        return []
    found = []
    for raw in text.split():
        token = raw.strip(".,!?;:()[]{}\"'").lower()
        if token in tracked and token not in found:
            found.append(token)
    return found


# =====================================================================
# Storage
# =====================================================================
def ensure_csv():
    """Create the CSV with headers if it doesn't exist yet."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADERS)


def connect_sheets():
    """Connect to Google Sheets if enabled; return the worksheet or None."""
    if not USE_GOOGLE_SHEETS:
        return None
    try:
        import gspread  # imported lazily so CSV-only users don't need it
        gc = gspread.service_account(filename=GOOGLE_CREDS_FILE)
        ws = gc.open(GSHEET_NAME).sheet1
        if not ws.get_all_values():
            ws.append_row(CSV_HEADERS)
        logger.info("Google Sheets connected.")
        return ws
    except Exception as e:
        logger.error(f"Google Sheets setup failed — using CSV only: {e}")
        return None


def write_entry(row):
    """Always write to the CSV; also write to Sheets (with retries) if enabled."""
    # CSV mirror — always. This is the source of truth and the safety net.
    try:
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception as e:
        logger.error(f"CSV write failed: {e}")

    # Google Sheets — up to 3 retries, then give up (CSV already has it).
    if gsheet is not None:
        for attempt in range(3):
            try:
                gsheet.append_row(row)
                return
            except Exception as e:
                logger.warning(f"Sheets write attempt {attempt + 1} failed: {e}")
        logger.error("Sheets write failed after 3 tries — saved to CSV only.")


async def get_admin_ids(update, context):
    """Fetch and cache the group's admin user IDs (refreshed hourly)."""
    chat_id = update.effective_chat.id
    cache = context.chat_data.get("admins")
    now = datetime.now(timezone.utc).timestamp()
    if cache and (now - cache["ts"] < 3600):
        return cache["ids"]
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        ids = {a.user.id for a in admins}
        context.chat_data["admins"] = {"ids": ids, "ts": now}
        return ids
    except Exception as e:
        logger.warning(f"Could not fetch admins: {e}")
        return cache["ids"] if cache else set()


# =====================================================================
# Handlers
# =====================================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg is None:
        return

    # Hashtags live in .text (plain message) or .caption (photo with caption).
    text = msg.text or msg.caption or ""
    tags = find_hashtags(text)
    if not tags:
        return  # no tracked hashtag — ignore

    # Skip edits / re-processing of a message we've already logged.
    key = (update.effective_chat.id, msg.message_id)
    if key in processed_messages:
        return
    processed_messages.add(key)

    # Ignore admins (so mods posting examples don't pollute the data).
    user = msg.from_user
    admin_ids = await get_admin_ids(update, context)
    if user.id in admin_ids:
        logger.info(f"Skipped admin message from {user.full_name}")
        return

    # Build a message link (works for public @username groups and private ones).
    chat = update.effective_chat
    if chat.username:
        link = f"https://t.me/{chat.username}/{msg.message_id}"
    else:
        internal = str(chat.id).replace("-100", "")
        link = f"https://t.me/c/{internal}/{msg.message_id}"

    has_image = "Yes" if msg.photo else "No"
    username = f"@{user.username}" if user.username else "(no username)"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    row = [
        timestamp, username, user.id, user.full_name,
        ", ".join(tags), text, link, has_image,
    ]
    write_entry(row)
    logger.info(f"Logged {tags} from {username}")

    # Reply once, using a random message for the first matched hashtag.
    reply_pool = REPLIES.get(tags[0], ["Logged ✅"])
    try:
        await msg.reply_text(random.choice(reply_pool))
    except Exception as e:
        logger.warning(f"Reply failed: {e}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only /stats (private DM only): quick totals read from the CSV."""
    # Must be a private chat. Ignore if typed in the group.
    if update.effective_chat.type != "private":
        return

    if GROUP_CHAT_ID == 0:
        await update.message.reply_text(
            "Stats aren't configured yet. Set GROUP_CHAT_ID in your .env file."
        )
        return

    # Only group admins may see stats.
    try:
        admins = await context.bot.get_chat_administrators(GROUP_CHAT_ID)
        admin_ids = {a.user.id for a in admins}
    except Exception as e:
        await update.message.reply_text(f"Could not verify admin status: {e}")
        return
    if update.effective_user.id not in admin_ids:
        return  # silently ignore non-admins

    counts = {h: 0 for h in TRACKED_HASHTAGS}
    users = set()
    total = 0
    try:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                total += 1
                users.add(r["User ID"])
                stored = [t.strip() for t in r["Hashtags"].lower().split(",")]
                for h in TRACKED_HASHTAGS:
                    if h in stored:
                        counts[h] += 1
    except FileNotFoundError:
        await update.message.reply_text("No entries logged yet.")
        return
    except Exception as e:
        await update.message.reply_text(f"Could not read stats: {e}")
        return

    lines = ["📊 Campaign stats", f"Total entries: {total}", f"Unique users: {len(users)}", ""]
    for h, c in counts.items():
        lines.append(f"{h}: {c}")
    await update.message.reply_text("\n".join(lines))


# =====================================================================
# Entry point
# =====================================================================
def main():
    global gsheet

    if not BOT_TOKEN:
        raise SystemExit(
            "ERROR: BOT_TOKEN is not set. Copy .env.example to .env and add your token."
        )

    ensure_csv()
    gsheet = connect_sheets()

    app = Application.builder().token(BOT_TOKEN).build()

    # Catch text messages AND photos (with captions), in groups only.
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION | filters.PHOTO) & filters.ChatType.GROUPS,
        handle_message,
    ))
    app.add_handler(CommandHandler("stats", stats_command))

    logger.info("Bot starting…")
    # run_polling handles network hiccups internally. For crash auto-restart,
    # run this under a process manager (systemd / pm2 / screen) — see README.
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
