#!/usr/bin/env python3
"""Prior-art watch: decide which projects are due a look, and say nothing when none are.

The cadence is the owner's rule, implemented against *upstream* activity rather than our own
calendar, because our counters drift and a missed tick silently ages the whole list:

    project touched in the last 2 days   -> look every 2 days
    touched in the last week             -> look weekly
    quiet for a week or more             -> look every 2 weeks

A project is also due immediately when its head commit differs from the one we last looked at, so a
quiet project that suddenly moves is never waited on.

Output: one line per due project, sorted, and nothing at all when nothing is due. That is what makes
this cheap: cron compares this output with the previous tick and skips the agent entirely when it is
unchanged. State lives in the state file passed as argv[1] (kept out of version control).

Exit codes: 0 always, unless a state file problem makes the answer unknowable (2).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# owner/repo -> why it is worth watching, in one line. The reason is carried here rather than in the
# cron prompt so the list can be updated without touching the schedule.
WATCHLIST: dict[str, str] = {
    # Reference engine (D14): the asset pipeline is the lesson most relevant to D18.
    "SFTtech/openage": "from-scratch AoE2 engine: asset pipeline, content model, determinism contrast",
    # Deterministic reimplementation aimed at exact DE replays (D13).
    "librematch/genie": "format readers and a deterministic DE-targeting implementation",
    # Dat modelling we depend on: U15 (create_time as build time) and U17 (negative packed attack).
    "SiegeEngineers/genie-rs": "dat/save/rec readers; check U15 and U17 against its model",
    # Asset pipeline pieces.
    "SiegeEngineers/sld-extractor": "SLD (DE sprite) extraction: the asset-pack layer under D18",
    "SiegeEngineers/WololoKingdoms": "HD-era file conversion: what changes between HD and DE data",
    # Published-value cross-checks for anything the dat leaves ambiguous.
    "SiegeEngineers/aoc-reference-data": "reference data for AoE2 projects: cross-check source",
    "SiegeEngineers/halfon": "unit/building/tech reference: published values for U-numbers",
    "SiegeEngineers/aoe2techtree": "tech tree data and presentation",
    # Format and map-script knowledge for later steps.
    "SiegeEngineers/genieutils-py": "Python dat tooling: an independent reading of the same format",
    "SiegeEngineers/rms-check": "random map script linter: .rms semantics for step 6+",
    "SiegeEngineers/rms-doc": "random map script language documentation",
}

API = "https://api.github.com/repos/{repo}"
UA = "ruage-prior-art-watch/1.0"


def fetch(repo: str) -> tuple[str, str] | None:
    """(pushed_at ISO, head sha) for a repo, or None if GitHub would not say."""
    # `commits?per_page=1` gives both the date and the sha in one request, and it is the same
    # endpoint whether or not the project uses releases.
    url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
    try:
        out = subprocess.run(
            ["curl", "-sS", "-m", "20", "-H", f"User-Agent: {UA}", url],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        payload = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list) or not payload:
        return None
    entry = payload[0]
    sha = entry.get("sha")
    date = (entry.get("commit") or {}).get("committer", {}).get("date")
    if not isinstance(sha, str) or not isinstance(date, str):
        return None
    return date, sha


def interval_for(idle_days: float) -> int:
    """The owner's backoff: 2 days while hot, a week while warm, a fortnight once cold."""
    if idle_days < 2:
        return 2
    if idle_days < 7:
        return 7
    return 14


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return state if isinstance(state, dict) else {}


def main() -> int:
    if len(sys.argv) > 1:
        state_path = sys.argv[1]
    else:
        # `<repo>/build/prior-art-state.json`: build/ is gitignored, so the watch cannot dirty the
        # tree it is watching, and the state survives between cron ticks.
        state_path = str(Path(__file__).resolve().parents[2] / "build" / "prior-art-state.json")
    now = datetime.now(timezone.utc)
    state = load_state(state_path)
    due: list[str] = []

    for repo in sorted(WATCHLIST):
        fetched = fetch(repo)
        if fetched is None:
            # Say so rather than pretending the project is quiet: silence would look like "nothing
            # changed", which is the one thing this watch must never fake.
            due.append(f"UNREACHABLE {repo} (GitHub did not answer; treat as unknown, not idle)")
            continue
        pushed_at, sha = fetched
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        idle_days = (now - pushed).total_seconds() / 86400.0
        interval = interval_for(idle_days)

        seen = state.get(repo) or {}
        last_checked = seen.get("last_checked_at")
        last_sha = seen.get("sha")
        never_seen = not isinstance(last_checked, str)
        moved = isinstance(last_sha, str) and last_sha != sha

        if never_seen:
            wait_days = 0.0
        else:
            checked = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
            wait_days = interval - (now - checked).total_seconds() / 86400.0

        if never_seen or moved or wait_days <= 0.0:
            reason = "new head" if moved else ("first look" if never_seen else "due")
            due.append(
                f"DUE {repo} last_commit={pushed.date().isoformat()} idle={idle_days:.1f}d "
                f"every={interval}d reason={reason} sha={sha[:10]} why={WATCHLIST[repo]}"
            )
            state[repo] = {"sha": sha, "last_checked_at": now.isoformat()}
        else:
            state[repo] = {
                "sha": last_sha if isinstance(last_sha, str) else sha,
                "last_checked_at": last_checked,
                "last_commit": pushed_at,
                "next_due_in_days": round(wait_days, 2),
            }

    try:
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except OSError as err:
        print(f"STATE-WRITE-FAILED {state_path}: {err}", file=sys.stderr)
        return 2

    if due:
        print("\n".join(due))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
