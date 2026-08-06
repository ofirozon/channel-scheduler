#!/usr/bin/env python3
"""Publish any due posts from scheduled/ to their Telegram channel.

A scheduled post is a plain text file named:

    scheduled/<channel>/<YYYY-MM-DDTHHMM>.txt      (time is UTC)

It is published once its timestamp is in the past, then moved to
published/<channel>/ so it can never be sent twice. Running late is safe:
every overdue file is sent in chronological order, so a missed or delayed
workflow run self-heals on the next one.

Env:
    EN_CHANNEL_BOT_TOKEN   bot token for the "Claude Code Daily" channel
    EN_CHANNEL_ID          e.g. @DailyClaudeTips
    MAX_LATE_HOURS         skip posts more than this many hours overdue
                           (default 20, so a dead week does not dump a
                           backlog into the channel at once)
    DRY_RUN                if "1", print what would be sent and send nothing
"""

import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
SCHEDULED = ROOT / "scheduled"
PUBLISHED = ROOT / "published"
LOG = ROOT / "published-log.jsonl"

CHANNELS = {
    "en": {"token_env": "EN_CHANNEL_BOT_TOKEN", "id_env": "EN_CHANNEL_ID"},
    "he": {"token_env": "HE_CHANNEL_BOT_TOKEN", "id_env": "HE_CHANNEL_ID"},
}

MAX_LATE_HOURS = float(os.environ.get("MAX_LATE_HOURS", "20"))
DRY_RUN = os.environ.get("DRY_RUN") == "1"


def slot_time(path: pathlib.Path):
    """Parse YYYY-MM-DDTHHMM.txt into an aware UTC datetime, or None."""
    try:
        return datetime.strptime(path.stem, "%Y-%m-%dT%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def send(token: str, chat_id: str, text: str) -> dict:
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "false"}
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    now = datetime.now(timezone.utc)
    published, failed = 0, 0

    for channel, cfg in CHANNELS.items():
        src = SCHEDULED / channel
        if not src.is_dir():
            continue

        due = []
        for path in sorted(src.glob("*.txt")):
            when = slot_time(path)
            if when is None:
                print(f"skip (bad name): {path.name}", file=sys.stderr)
                continue
            if when <= now:
                due.append((when, path))
        if not due:
            continue

        token = os.environ.get(cfg["token_env"], "").strip()
        chat_id = os.environ.get(cfg["id_env"], "").strip()
        if not token or not chat_id:
            print(f"ERROR: {cfg['token_env']}/{cfg['id_env']} not set", file=sys.stderr)
            return 1

        dest = PUBLISHED / channel
        dest.mkdir(parents=True, exist_ok=True)

        for when, path in sorted(due):
            text = path.read_text(encoding="utf-8").strip()
            late_hours = (now - when).total_seconds() / 3600

            if not text:
                print(f"skip (empty): {path.name}", file=sys.stderr)
                path.unlink()
                continue
            # Hard rule carried over from the local publisher: never an em-dash.
            if "—" in text:
                print(f"SKIP (em-dash): {path.name}", file=sys.stderr)
                failed += 1
                continue
            if late_hours > MAX_LATE_HOURS:
                print(
                    f"skip (stale by {late_hours:.1f}h): {path.name}", file=sys.stderr
                )
                path.rename(dest / f"{path.stem}.skipped.txt")
                continue

            if DRY_RUN:
                print(f"[dry-run] would send {channel}/{path.name} ({len(text)} chars)")
                continue

            try:
                resp = send(token, chat_id, text)
            except Exception as exc:  # network, 429, anything
                print(f"FAILED {path.name}: {exc}", file=sys.stderr)
                failed += 1
                continue

            if not resp.get("ok"):
                print(f"FAILED {path.name}: {resp}", file=sys.stderr)
                failed += 1
                continue

            msg_id = resp["result"]["message_id"]
            path.rename(dest / path.name)
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "channel": channel,
                            "slot_utc": when.isoformat(),
                            "sent_utc": now.isoformat(),
                            "late_hours": round(late_hours, 2),
                            "message_id": msg_id,
                            "file": path.name,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            published += 1
            print(f"published {channel}/{path.name} -> message_id {msg_id}")

    print(f"done: {published} published, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
