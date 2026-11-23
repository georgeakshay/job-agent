"""Remembers which jobs were already emailed, so no job arrives twice."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path("state/sent_jobs.json")


def load_sent() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def unseen(jobs: list[dict], sent: dict) -> list[dict]:
    sent_urls = {v.get("url") for v in sent.values()}
    return [j for j in jobs if j["id"] not in sent and j["url"] not in sent_urls]


def record(sent: dict, jobs: list[dict]) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    for j in jobs:
        sent[j["id"]] = {"title": j["title"], "company": j["company"], "url": j["url"], "sent_on": today}
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(sent, indent=1, ensure_ascii=False, sort_keys=True))
    return sent
