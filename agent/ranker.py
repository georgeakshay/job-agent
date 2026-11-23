"""The AI step: Claude ranks the pre-filtered jobs with reasons, then writes a cover note for the best one."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

MODEL = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-4-5"
PROMPTS = Path("prompts")


def _client():
    import anthropic
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


def _ask(prompt: str, max_tokens: int) -> str:
    msg = _client().messages.create(
        model=MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}]
    )
    return "".join(block.text for block in msg.content if block.type == "text").strip()


def _job_for_prompt(job: dict, desc_chars: int = 1500) -> dict:
    return {k: job[k] for k in ("id", "title", "company", "location", "site")} | {
        "description": job["description"][:desc_chars]
    }


def _parse_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("Claude did not return JSON")
    return json.loads(match.group(0))


def rank(jobs: list[dict], profile: str, max_years: int, top_n: int, ask=_ask) -> list[dict]:
    template = (PROMPTS / "rank_jobs.md").read_text()
    prompt = template.format(
        profile=profile,
        jobs=json.dumps([_job_for_prompt(j) for j in jobs], ensure_ascii=False, indent=1),
        max_years=max_years,
        top_n=top_n,
    )
    result = _parse_json(ask(prompt, 4000))
    by_id = {j["id"]: j for j in jobs}
    ranked = []
    for m in result.get("matches", []):
        job = by_id.get(m.get("id"))
        if job:  # ignore any id the model invented
            ranked.append(job | {"score": m.get("score"), "why": m.get("why", ""),
                                 "experience_asked": m.get("experience_asked", "not stated")})
    return ranked[:top_n]


def cover_note(job: dict, profile: str, ask=_ask) -> str:
    template = (PROMPTS / "cover_note.md").read_text()
    return ask(template.format(profile=profile, job=json.dumps(_job_for_prompt(job, 4000), ensure_ascii=False)), 600)
