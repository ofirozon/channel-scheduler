# channel-scheduler

Cloud publisher for Ofir's Telegram channels. Private on purpose: it holds no
secrets in the tree, but it is infrastructure, not showcase code (the public
showcase repo is `self-improving-channel-agent`).

## Why it exists

Everything used to publish from the Mac through `launchd`. If the Mac was off,
asleep, or offline at the slot time, that post simply never went out. This repo
moves the *sending* into GitHub Actions, so the Mac only has to **write** posts,
whenever it happens to be on.

    Mac (writes posts, any time)  ->  scheduled/en/*.txt  ->  GitHub Actions (sends, on time)

## How a post is scheduled

One plain text file per post, the filename is the slot time in **UTC**:

    scheduled/en/2026-08-04T1200.txt

`publish.py` runs hourly and sends every file whose time has passed, oldest
first, then moves it to `published/en/` and appends a line to
`published-log.jsonl`. A file is never sent twice because sending and moving are
the same step. A post more than `MAX_LATE_HOURS` (default 20) overdue is skipped
rather than sent, so a week-long outage does not dump a backlog into the channel
at once; it lands in `published/en/` with a `.skipped.txt` suffix.

Post the current queue from the Mac with:

    ~/.local/bin/channel-cloud-queue.sh <post-file> <YYYY-MM-DDTHHMM utc>

## Slots for "Claude Code Daily"

| UTC   | Israel | US East | US Pacific | UK    |
|-------|--------|---------|------------|-------|
| 12:00 | 15:00  | 08:00   | 05:00      | 13:00 |
| 16:00 | 19:00  | 12:00   | 09:00      | 17:00 |
| 20:00 | 23:00  | 16:00   | 13:00      | 21:00 |

The 20:00 UTC slot is the reason this repo exists: 23:00 Israel time is exactly
when the Mac is most likely to be shut down.

## Configuration

Repository secrets:

- `EN_CHANNEL_BOT_TOKEN` broadcast-only bot for @DailyClaudeTips
- `ALERT_BOT_TOKEN` personal bot, used only to DM Ofir when the queue runs dry

Repository variables:

- `EN_CHANNEL_ID` `@DailyClaudeTips`
- `ALERT_CHAT_ID` Ofir's chat id

## Alarms

At 09:01 UTC daily, `buffer_check.py` counts future scheduled posts. Fewer than
`MIN_BUFFER` (default 4) means the Mac has stopped writing, and Ofir gets a DM
before the channel goes quiet, not after.

## Hard rules

- Never call `getUpdates` with either token. Both are broadcast-only here.
- Never an em-dash in a post. `publish.py` refuses to send one.
- Never commit a token. Secrets live in GitHub, config lives in the tree.
