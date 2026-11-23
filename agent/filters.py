"""Rule-based pre-filter. Cheap checks run before any AI call, so Claude only sees plausible jobs."""
from __future__ import annotations

import re

YEARS_RE = re.compile(r"(?:minimum|min\.?|at least)?\s*(\d{1,2})\s*(?:\+|-\s*\d{1,2}|to\s*\d{1,2})?\s*(?:\+\s*)?years?", re.I)
BLOCKERS = [
    re.compile(r"\bUAE nationals? only\b", re.I),
    re.compile(r"\bemiratis? only\b", re.I),
    re.compile(r"\bfluen\w* in arabic\b|\barabic (?:is )?(?:mandatory|required|essential)\b", re.I),
    re.compile(r"\bfluen\w* in german\b|\bgerman (?:is )?(?:mandatory|required|essential)\b", re.I),
]
MULTI_LOCATION = re.compile(r"^\d+ locations?$", re.I)


def min_years_asked(text: str) -> int | None:
    """Smallest 'N years' requirement mentioned in the text, ignoring numbers that are clearly not experience."""
    found = []
    for m in YEARS_RE.finditer(text or ""):
        context = text[m.end(): m.end() + 40].lower()
        if "experience" in context or "exp" in context or "relevant" in context or " of " in context[:5]:
            found.append(int(m.group(1)))
    found = [y for y in found if 0 < y <= 20]
    return min(found) if found else None


def location_ok(job: dict, keep: list[str]) -> bool:
    loc = job["location"].lower()
    if not loc or MULTI_LOCATION.match(loc):
        return True  # unknown: let the AI decide from the description
    if job.get("is_remote"):
        return True
    return any(k in loc for k in keep)


def title_ok(title: str, include: list[str], exclude: list[str]) -> bool:
    t = f" {title.lower()} "
    if any(x in t for x in exclude):
        return False
    return any(k in t for k in include)


def prefilter(jobs: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    kept, reasons = [], {"location": 0, "title": 0, "experience": 0, "language_or_nationality": 0}
    for job in jobs:
        if not location_ok(job, cfg["locations_keep"]):
            reasons["location"] += 1
            continue
        if not title_ok(job["title"], cfg["title_keywords"], cfg["title_exclude"]):
            reasons["title"] += 1
            continue
        years = min_years_asked(job["description"])
        if years is not None and years > cfg["max_years_experience"]:
            reasons["experience"] += 1
            continue
        if any(p.search(job["description"]) for p in BLOCKERS):
            reasons["language_or_nationality"] += 1
            continue
        kept.append(job)
    return kept, reasons
