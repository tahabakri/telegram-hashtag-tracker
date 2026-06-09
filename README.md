# Telegram Hashtag Tracking Bot

A simple, reliable Telegram bot for running a community campaign, contest, or giveaway. It watches a group for your campaign hashtags — in plain text **and photo captions** — logs every entry to a Google Sheet (with a CSV backup), and replies with a fun message to keep people participating.

Built for one time-boxed campaign at a time: no database, no dashboard, no fuss. Configure it entirely with environment variables, point it at a group, and let it run 24/7.

## Features

- Watches a group for your hashtags in **text and photo captions**
- **Whole-word, case-insensitive** matching — `#entry` matches `#Entry` and `#ENTRY`, but lookalikes like `#entryfinal` never count
- Logs each entry with: UTC timestamp, @username, user ID, full name, hashtag(s), message text, a link to the message, and whether it had an image
- Replies with a **random message per hashtag** so it never feels robotic
- **Ignores group admins** — mods posting examples don't pollute the data
- **Unlimited entries** per person; every hashtag message is a new row
- Edited messages are **never double-counted**
- Writes to a **Google Sheet** (optional) and **always** to a local CSV as a safety net — a Sheets outage never loses an entry (3 retries, then CSV-only)
- Admin-only **`/stats`** command (private DM) for quick totals
- Configurable **without touching the code** — hashtags, replies, and credentials all come from environment variables, so the same code runs any campaign
- The bot token is **never written to the logs** (HTTP request logging is silenced)

## How it works

Telegram delivers every group message to the bot (once Group Privacy is **disabled** — see setup). For each message the bot reads `message.text` or, for photos, `message.caption`, and scans it for your tracked hashtags using whole-word, case-insensitive matching. If the sender is a group admin, the message is skipped (the admin list is fetched from Telegram and cached for an hour). Otherwise the bot appends one row to the local CSV, then to the Google Sheet if enabled (with up to 3 retries), and replies once with a random message for the first matched hashtag. Processed message IDs are remembered so an edit never counts twice. The CSV is written first, so even a total Sheets outage loses nothing.

## Quick start (local, ~10 minutes)

### 1. Install

```
pip install -r requirements.txt
```

### 2. Create the bot

- In Telegram, message **@BotFather** (verify the blue checkmark — there are fakes)
- Send `/newbot`, follow the prompts, copy the **token**
- Send `/setprivacy` → pick your bot → **Disable**
  ⚠️ This is the #1 forgotten step. Without it the bot only sees `/commands`, not normal messages, and will silently log nothing.

### 3. Configure

```
cp .env.example .env
```

Open `.env` and set at least `BOT_TOKEN` and `TRACKED_HASHTAGS`.

### 4. Add the bot to your group

- Add the bot to the Telegram group
- Promote it to **Admin** (required to read all messages)

### 5. Run

```
python bot.py
```

Watch for `Bot starting…` in the output. Post one of your hashtags in the group — the bot replies and a row lands in `entries.csv`.

## Configuration (environment variables)

Everything is configured via environment variables — in `.env` locally, or in your host's variables panel when deployed. **No campaign details ever need to be committed to the code**, which keeps this repo reusable for any campaign.

| Variable | Required | Default | What it does |
|---|---|---|---|
| `BOT_TOKEN` | **yes** | — | Bot token from @BotFather. Never commit it. |
| `TRACKED_HASHTAGS` | recommended | `#entry,#proof,#prediction` | Comma-separated hashtags to track, e.g. `#launch,#proof,#vote` |
| `REPLIES_JSON` | no | friendly defaults | Custom replies as a one-line JSON object mapping each hashtag to a list, e.g. `{"#launch": ["You're in! ✅", "Logged 🚀"]}` |
| `USE_GOOGLE_SHEETS` | no | `false` | Set `true` to also log to a Google Sheet |
| `GSHEET_NAME` | with Sheets | `Campaign Entries` | The **exact** name of your Google Sheet |
| `GOOGLE_CREDS_JSON` | cloud hosting | empty | The **entire** service-account JSON, pasted as one value. Leave blank locally and use a `creds.json` file instead. |
| `GROUP_CHAT_ID` | for `/stats` | `0` | Your group's chat ID (looks like `-100…`) — only needed for the `/stats` command |
| `CSV_FILE` | no | `entries.csv` | Where the local CSV mirror is written |

### Customising hashtags and replies

Set `TRACKED_HASHTAGS` and (optionally) `REPLIES_JSON` and restart — that's it. If a hashtag has no custom reply, the bot falls back to a generic "Logged ✅". You can also edit the `_DEFAULT_HASHTAGS` and `_DEFAULT_REPLIES` values near the top of `bot.py`, but environment variables are recommended so your campaign details stay out of the code.

## Google Sheets setup (optional, ~10 minutes)

Google won't let a bot write to your Sheet directly — you create a **service account** (a robot Google account), download its JSON key, and share your Sheet with it like a coworker.

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) → create a project (any name).
2. Enable **both** APIs (top search bar → name → Enable):
   - **Google Sheets API**
   - **Google Drive API** (required — the bot opens the sheet *by name*, which goes through Drive)
3. Search **Service Accounts** → **+ Create Service Account** → name it → **Create and Continue** → skip the role step → **Done**.
4. Open the new service account → **Keys** tab → **Add Key → Create new key → JSON** → a `.json` file downloads. Treat it like a password. Don't set an expiration date.
5. Create a Google Sheet at [sheets.google.com](https://sheets.google.com) and name it **exactly** what you set as `GSHEET_NAME`. Leave it blank — the bot writes the header row itself.
6. Click **Share** on the sheet → paste the service account's email (ends in `gserviceaccount.com`) → role **Editor** → untick "Notify people" → Share.
7. Provide the credentials:
   - **Locally:** save the file as `creds.json` next to `bot.py` (it's gitignored).
   - **Cloud hosting:** open the file, select **all** of it (Ctrl+A — it must start with `{` and end with `}`), and paste it into the `GOOGLE_CREDS_JSON` variable.
8. Set `USE_GOOGLE_SHEETS=true` and restart. The log line you want is:

```
Google Sheets connected.
```

No billing is needed for any of this — the Sheets/Drive APIs are free at this scale.

## Deploying 24/7 (Railway example)

A laptop misses entries when it sleeps. For a real campaign, run it on an always-on host. [Railway](https://railway.app) is the path this repo is set up for (`railway.json` pins the start command and crash auto-restart), but any host that runs `python bot.py` with environment variables works (VPS + systemd, Render, Fly.io, …).

1. railway.app → **New Project** → **Deploy from GitHub repo** → pick your fork/copy of this repo. Railway auto-builds from `requirements.txt`.
2. Open the service → **Variables** → add `BOT_TOKEN`, `TRACKED_HASHTAGS`, and (optionally) the Sheets variables above. Secrets go **only** here — never into the repo.
3. After editing variables, watch for Railway's **apply/deploy banner** and click it — variable edits are staged and don't reach the container until applied.
4. Open **Deploy Logs** and confirm:

```
Google Sheets connected.   (if Sheets is on)
Bot starting…
Application started
```

…followed by silence. A quiet log is a healthy bot.

**Things to know:**

- **One instance only.** Telegram allows a single polling connection per token. Don't run `python bot.py` locally while the host is also running it — you'll see `Conflict: terminated by other getUpdates request` in the logs. Stop one of them.
- **Cost:** an always-on polling bot needs a paid tier on most hosts (Railway Hobby is ~$5/mo). Free tiers that sleep will miss entries.
- **The CSV on a cloud host is ephemeral** — it's wiped on each redeploy. That's fine when Google Sheets is your primary log (each row is appended to the Sheet immediately). If you want the CSV to survive restarts too, mount a volume and point `CSV_FILE` at it (e.g. `/data/entries.csv`).

## The `/stats` command

Admins can DM the bot `/stats` and get totals (entries per hashtag, unique users) without opening the sheet. It works **only in a private DM** and **only for admins of the configured group** — regular members are silently ignored, and it never responds inside the group.

Setup:

1. Set `GROUP_CHAT_ID` to your group's ID (a number like `-1001234567890`). Easiest way to find it: forward any message from the group to **@getidsbot** and read the chat `id` it reports. (For private groups you can also take the number after `/c/` in a logged Message Link and prefix `-100`.)
2. The admin must have DM'd the bot at least once (open a private chat with it and send `/start`) — Telegram doesn't let bots message people first.

## What gets logged

| Column | Example |
|---|---|
| Timestamp (UTC) | 2026-06-09 14:32:01 |
| Username | @example_user |
| User ID | 123456789 |
| Full Name | Example User |
| Hashtags | #entry, #proof |
| Message Text | "Done! #entry" |
| Message Link | https://t.me/c/1234567/89 |
| Has Image | Yes / No |

Multiple tracked hashtags in one message are logged in one row (comma-separated) with a single reply. Timestamps are always UTC.

## Testing

The hashtag matcher — the part most likely to cause silent miscounts — has unit tests, and they run in CI on every push:

```
python -m pytest
```

## Troubleshooting

Every one of these was hit for real while building this. Check the **Deploy Logs** first — the answer is almost always there.

| Symptom | Cause | Fix |
|---|---|---|
| Bot replies to `/commands` but ignores normal messages | Group Privacy still enabled | @BotFather → `/setprivacy` → your bot → **Disable**, then remove and re-add the bot to the group |
| Bot never replies at all | Bot isn't a group admin, or wrong group | Promote it to Admin; confirm you're posting in the tracked group |
| `Conflict: terminated by other getUpdates request` repeating | Two copies running with the same token (local + host, two services, or a stale deployment) | Stop the extra copy. If unsure where it is, revoke the token in @BotFather (`/revoke`) and set the new one on the host — every old copy dies instantly |
| `Google Sheets setup failed … No such file or directory: 'creds.json'` | `GOOGLE_CREDS_JSON` is empty or didn't apply | Paste the **whole** JSON (Ctrl+A in the file — must start `{` and end `}`); apply/redeploy; verify with `printenv GOOGLE_CREDS_JSON \| head -c 5` in the host console — it must print `{"typ` |
| `Google Sheets setup failed … SpreadsheetNotFound` | Sheet name mismatch or not shared | Sheet name must match `GSHEET_NAME` exactly; share the sheet with the service-account email as **Editor** |
| `/stats` says "Chat not found" | Wrong `GROUP_CHAT_ID` | Forward a group message to @getidsbot and use the `id` it reports (including the `-100` prefix) |
| `/stats` gets no reply at all | You haven't DM'd the bot, or you're not a group admin | Send the bot `/start` in a private chat first; only admins get an answer |
| Variable changes seem ignored | Host staged the change without applying | Click the host's apply/deploy banner after editing variables, then check the logs' timestamps to confirm a fresh start |

The bot is designed to degrade safely: if Sheets fails it keeps logging to CSV; if a reply fails it still logs; if it crashes the host's restart policy brings it back.

## Project structure

```
bot.py                  the whole bot (~350 lines, commented)
tests/test_hashtags.py  unit tests for the matcher
conftest.py             lets tests/ import bot.py
requirements.txt        python-telegram-bot, python-dotenv, gspread
.env.example            documented template for every variable
railway.json            start command + crash auto-restart for Railway
.github/workflows/      CI: pytest on every push and PR
```

## Privacy & scope notes

- The bot stores what participants post publicly in the group (plus their Telegram username/ID) — nothing else. Tell your community entries are being logged.
- It does **not** verify identities, handle payments, or judge winners — it only tracks participation. Reconciliation and rewards are intentionally manual.
- `.env` and `creds.json` hold your secrets and are gitignored. Never commit them; if a token ever leaks (including via logs you share), revoke it in @BotFather and set the new one.

## License

MIT — see [LICENSE](LICENSE). Free for anyone to use, modify, and run for any campaign.
