#!/usr/bin/env python3
"""Warn Ofir on Telegram when the cloud queue is running dry.

The Mac writes posts into scheduled/; GitHub publishes them. If the Mac is
off, asleep, or the writing agent breaks, the channel keeps posting from the
buffer and everything looks fine, right up until the buffer empties. This is
the alarm for exactly that window.

Env:
    ALERT_BOT_TOKEN   personal bot token (DM to Ofir)
    ALERT_CHAT_ID     his chat id
    MIN_BUFFER        warn when fewer than this many future posts remain
                      (default 4, which is more than one full day)
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


def main() -> int:
    now = datetime.now(timezone.utc)
    lines = []

    for channel_dir in sorted(p for p in SCHEDULED.glob("*") if p.is_dir()):
        future = []
        for path in channel_dir.glob("*.txt"):
            try:
                when = datetime.strptime(path.stem, "%Y-%m-%dT%H%M").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
            if when > now:
                future.append(when)
        if len(future) < MIN_BUFFER:
            last = max(future).strftime("%d.%m %H:%M UTC") if future else "אין"
            lines.append(
                f"ערוץ {channel_dir.name}: נשארו {len(future)} פוסטים מתוזמנים בענן "
                f"(האחרון: {last})."
            )

    if not lines:
        print("buffer ok")
        return 0

    token = os.environ.get("ALERT_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("ALERT_CHAT_ID", "").strip()
    text = (
        "התראת מלאי ענן\n"
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
