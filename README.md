# Telegram Hashtag Tracking Bot

A simple, reliable Telegram bot for running a community campaign or giveaway. It watches a group for your campaign hashtags — in plain text **and photo captions** — logs every entry to a spreadsheet, and replies with a fun message to keep people participating.

Built for one time-boxed campaign at a time: no database, no fuss. Point it at a group, set your hashtags, and run.

## What it does

- Watches the group for your hashtags (e.g. `#entry`, `#proof`, `#prediction`) in **text and photo captions**
- Logs each entry to `entries.csv` — time (UTC), username, user ID, name, hashtag(s), message, link, and whether it had an image
- Replies with a random, friendly message per hashtag so it never feels robotic
- **Ignores admins**, so mods posting examples don't pollute the data
- Allows **unlimited entries** per person — every hashtag message is a new logged row
- Optional: also writes to a **Google Sheet** (with the CSV as an always-on backup)
- Optional: an admin-only `/stats` command (in a private DM) for quick totals

## How it works

Telegram delivers every group message to the bot (once Group Privacy is **off**). For each message the bot reads `message.text` or, for photos, `message.caption`, and scans it for your tracked hashtags using **whole-word, case-insensitive** matching — so `#entry` matches `#Entry` and `#ENTRY` but never counts a lookalike like `#entryfinal`. If the sender is a group admin, the message is skipped. Otherwise the bot appends one row to the CSV (and the Google Sheet, if enabled) and replies once with a random message for the matched hashtag. Processed message IDs are remembered so an edited message is never counted twice. Everything is written to the local CSV first, so even a Google Sheets outage never loses an entry.

## Setup (about 10 minutes)

### 1. Install
```
pip install -r requirements.txt
```

### 2. Create the bot
- Open Telegram, message **@BotFather**
- Send `/newbot`, follow the prompts, copy the **token**
- Send `/setprivacy` → pick your bot → **Disable** *(this lets the bot read all group messages — required)*

### 3. Add your token
```
cp .env.example .env
```
Open `.env` and paste your token into `BOT_TOKEN`.

### 4. Add the bot to your group
- Add the bot to the Telegram group
- Make it an **Admin** (required to read messages)

### 5. Run
```
python bot.py
```
Entries start saving to `entries.csv`.

## Customising

Set your campaign in the environment (in `.env`) — no code changes needed:
- `TRACKED_HASHTAGS` — comma-separated hashtags to watch, e.g. `#entry,#proof,#prediction` (case-insensitive)
- `REPLIES_JSON` — optional one-line JSON mapping each hashtag to a list of replies; leave it blank for the built-in defaults

Both fall back to sensible defaults, so the bot runs out of the box. The defaults live in the **CONFIG** block of `bot.py` if you'd rather edit them there.

## Optional: Google Sheets

To mirror entries into a live Google Sheet:
1. In the [Google Cloud Console](https://console.cloud.google.com/): create a project, enable the **Google Sheets API** and **Google Drive API**
2. Create a **Service Account**, add a key (JSON), and download it as `creds.json` next to `bot.py`
3. Create a Google Sheet and **share it** with the service-account email (it ends in `gserviceaccount.com`)
4. In `.env`, set `USE_GOOGLE_SHEETS=true` and `GSHEET_NAME` to your sheet's name
5. Run again — rows now go to both the Sheet and the CSV backup

## Optional: the `/stats` command

`/stats` works **only in a private DM with the bot**, and **only for group admins** — regular members never see it.
- Set `GROUP_CHAT_ID` in `.env`. To find it: run the bot, post a tracked hashtag in the group, open `entries.csv`, take the number after `/c/` in the Message Link, and prefix it with `-100` (e.g. `.../c/2515871/45` → `-1002515871`).
- The admin must have sent the bot `/start` in a DM at least once.

## Keeping it running 24/7

A laptop will miss entries when it sleeps. Use an always-on host:
- **Railway / Replit** — easiest, with free always-on tiers
- **A small VPS** with a process manager so it auto-restarts on crash:
  ```
  # quick option with screen:
  screen -S bot
  python bot.py
  # press Ctrl+A then D to detach; the bot keeps running
  ```
  For production, run it under `systemd` or `pm2` so it restarts automatically if it ever crashes.

## Testing

The hashtag matcher (the part most likely to cause silent mistakes) has unit tests:
```
python -m pytest
```

## Notes

- `entries.csv` is your source of truth and backup — it's never lost, even if Google Sheets fails.
- Any trading data, verification, or reward logic is intentionally **not** handled here — this bot only tracks participation by username + hashtag. Fill in the rest manually at reward time.
- `.env` and `creds.json` hold your secrets and are git-ignored — never commit them.

## License

MIT — see [LICENSE](LICENSE). Free to use, modify, and run for anything.
