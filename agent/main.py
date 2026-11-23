"""Daily run: feeds -> rules -> no-repeats -> Claude ranking -> cover note -> email -> remember what was sent.

Usage:
  python -m agent.main            # full run (needs ANTHROPIC_API_KEY and SMTP secrets)
  python -m agent.main --dry-run  # no AI call, no email, no state change; writes a preview to output/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from agent import feeds, filters, notify, ranker, state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path("config.yaml").read_text())
    profile = Path("profile.md").read_text()

    loaded = []
    for f in cfg["feeds"]:
        try:
            jobs = feeds.load_feed(f["name"], f["url"], f["max_age_days"])
            print(f"[feed] {f['name']}: {len(jobs)} recent jobs")
            loaded.append(jobs)
        except Exception as exc:  # one broken feed should not stop the run
            print(f"[feed] {f['name']} FAILED: {exc}", file=sys.stderr)
    jobs = feeds.merge(loaded)

    candidates, dropped = filters.prefilter(jobs, cfg)
    print(f"[rules] {len(jobs)} -> {len(candidates)} (dropped: {dropped})")

    sent = state.load_sent()
    fresh = state.unseen(candidates, sent)
    print(f"[dedup] {len(candidates)} -> {len(fresh)} not emailed before")
    fresh = fresh[: cfg["max_candidates_for_ai"]]
    stats = {"loaded": len(jobs), "prefiltered": len(candidates), "unseen": len(fresh), "ranked": 0}

    out = Path("output")
    out.mkdir(exist_ok=True)
    if args.dry_run:
        (out / "dry_run_candidates.json").write_text(json.dumps(fresh, indent=1, ensure_ascii=False))
        print(f"[dry-run] {len(fresh)} candidates written to output/dry_run_candidates.json")
        return 0
    if not fresh:
        print("Nothing new today; no email sent.")
        return 0

    matches = ranker.rank(fresh, profile, cfg["max_years_experience"], cfg["top_n_in_email"])
    stats["ranked"] = len(fresh)
    print(f"[claude] {len(matches)} matches")
    if not matches:
        print("Claude found no good fit today; no email sent.")
        return 0

    note = ranker.cover_note(matches[0], profile)
    subject, text, body_html = notify.build_email(matches, note, stats)
    notify.send(subject, text, body_html)
    state.record(sent, matches)
    print(f"[email] sent: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
