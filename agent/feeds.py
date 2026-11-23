"""Load jobs from the daily feeds and put them in one common shape."""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timedelta, timezone

import requests


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def job_key(title: str, company: str) -> str:
    """Stable id for a job: same title + company = same job, even if reposted with a new link."""
    raw = f"{_norm(title)}|{_norm(company)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _parse_date(value: str | None) -> datetime | None:
    if not value or value == "None":
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _clean(value) -> str:
    return "" if value in (None, "None", "nan") else str(value)


def normalise(raw: dict, source: str) -> dict:
    """Map either feed's fields onto one schema."""
    url = _clean(raw.get("job_url_direct")) or _clean(raw.get("job_url")) or _clean(raw.get("url"))
    site = _clean(raw.get("site")) or "careers page"
    title, company = _clean(raw.get("title")), _clean(raw.get("company"))
    return {
        "id": job_key(title, company),
        "title": title,
        "company": company,
        "location": _clean(raw.get("location")),
        "url": url,
        "site": site,
        "source": source,
        "posted": _clean(raw.get("date_posted")) or _clean(raw.get("first_seen")),
        "is_remote": _clean(raw.get("is_remote")).lower() == "true",
        "description": _clean(raw.get("description")),
    }


def load_feed(name: str, url: str, max_age_days: int, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    resp = requests.get(f"{url}?t={int(time.time())}", timeout=60)
    resp.raise_for_status()
    data = resp.json()
    cutoff = now - timedelta(days=max_age_days)
    jobs = []
    for raw in data.get("jobs", []):
        job = normalise(raw, name)
        posted = _parse_date(job["posted"])
        if posted and posted < cutoff:
            continue
        jobs.append(job)
    return jobs


def merge(job_lists: list[list[dict]]) -> list[dict]:
    """Combine feeds; the same job seen on several sites is kept once (first source wins)."""
    seen, merged = set(), []
    for jobs in job_lists:
        for job in jobs:
            if job["id"] in seen or not job["title"]:
                continue
            seen.add(job["id"])
            merged.append(job)
    return merged
