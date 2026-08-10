#!/usr/bin/env python3
"""Warn Ofir on Telegram when the cloud queue is running dry.

The Mac writes posts into scheduled/; GitHub publishes them. If the Mac is
off, asleep, or the writing agent breaks, the channel keeps posting from the
buffer and everything looks fine, right up until the buffer empties. This is
the alarm for exactly that window.

Two things this deliberately does NOT do, because both bit us on 2026-08-10
when the queue emptied and nobody was told:

1. It never derives the channel list from whatever directories happen to
   exist. scheduled/<channel>/ disappears once its last post is published
   (git does not track empty directories), so a directory scan reports
   "nothing to worry about" in exactly the case that matters most. The list
   is fixed below and a missing directory counts as zero posts.
2. It does not rely on a dedicated cron line to decide when to run. The
   workflow calls it on every hourly run and the hour check lives here.

Env:
    ALERT_BOT_TOKEN   personal bot token (DM to Ofir)
    ALERT_CHAT_ID     his chat id
    MIN_BUFFER        warn when fewer than this many future posts remain
                      (default 4, which is more than one full day)
    FORCE_CHECK       if "1", report regardless of the hour (manual runs)
"""

import os
import pathlib
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
SCHEDULED = ROOT / "scheduled"
MIN_BUFFER = int(os.environ.get("MIN_BUFFER", "4"))

# Fixed, not discovered. See the module docstring.
CHANNELS = ("en", "he")

# 09:00 UTC is the daily depth report; 21:00 UTC is a second pass that only
# speaks up if a channel is completely out of posts.
DIGEST_HOUR = 9
EMPTY_ONLY_HOUR = 21


def future_slots(channel: str, now: datetime):
    """Future slot times queued for a channel. Missing directory means none."""
    slots = []
    for path in (SCHEDULED / channel).glob("*.txt"):
        try:
            when = datetime.strptime(path.stem, "%Y-%m-%dT%H%M").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        if when > now:
            slots.append(when)
    return slots


def main() -> int:
    now = datetime.now(timezone.utc)
    force = os.environ.get("FORCE_CHECK") == "1"

    depth = {ch: future_slots(ch, now) for ch in CHANNELS}
    empty = [ch for ch, slots in depth.items() if not slots]
    thin = [ch for ch, slots in depth.items() if 0 < len(slots) < MIN_BUFFER]

    for ch in CHANNELS:
        print(f"{ch}: {len(depth[ch])} future posts queued")

    if force or now.hour == DIGEST_HOUR:
        report = empty + thin
    elif now.hour == EMPTY_ONLY_HOUR:
        report = empty
    else:
        print("not a check hour, nothing sent")
        return 0

    lines = []
    for ch in report:
        slots = depth[ch]
        last = max(slots).strftime("%d.%m %H:%M UTC") if slots else "אין"
        lines.append(
            f"ערוץ {ch}: נשארו {len(slots)} פוסטים מתוזמנים בענן (האחרון: {last})."
        )

    if not lines:
        print("buffer ok")
        return 0

    token = os.environ.get("ALERT_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("ALERT_CHAT_ID", "").strip()
    headline = "הערוץ עומד להשתתק" if empty else "התראת מלאי ענן"
    text = (
        f"{headline}\n"
        + "\n".join(lines)
        + "\nכנראה שהמק לא כתב פוסטים חדשים. כשתדליק אותו תגיד לי ואמלא את התור."
    )
    print(text)
    if not token or not chat_id:
        print("ALERT_BOT_TOKEN/ALERT_CHAT_ID not set, printed only", file=sys.stderr)
        return 0

    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
    return 0


if __name__ == "__main__":
    sys.exit(main())
