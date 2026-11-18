"""Duplicate-execution check shared by the Actions entry points.

With dual-phase scheduling, two firings can match the same Vancouver
slot (the on-time phase and the +1h phase, which the slot guard sees
as DELAYED). Verification and planning must happen at most once per
slot per local day, so before doing work each entry point asks: has
another run of this workflow already completed for this slot's
window today? If yes, this execution records itself as a duplicate
and performs no work.

The window logic is pure and unit-tested; the API call is a thin
wrapper around `gh api`.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

EARLY = timedelta(minutes=10)


def prior_run_in_window(
    runs: list[dict],
    slot_at: datetime,
    now: datetime,
    current_run_id: str,
) -> dict | None:
    """Return the first completed run (not the current one) created in
    [slot_at - EARLY, now) — evidence the slot was already executed."""
    start = slot_at - EARLY
    for run in runs:
        if str(run.get("id")) == str(current_run_id):
            continue
        if run.get("status") != "completed":
            continue
        created = datetime.fromisoformat(
            run["created_at"].replace("Z", "+00:00")
        )
        if start.astimezone(timezone.utc) <= created < now.astimezone(timezone.utc):
            return run
    return None


def find_prior_run(workflow_file: str, slot_at: datetime) -> dict | None:
    """Query this repo's runs of `workflow_file` for a prior execution
    of the slot. Returns None when gh is unavailable (local testing):
    callers treat that as 'no evidence', never as proof of absence."""
    token = os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not token or not repo:
        return None
    since = (slot_at - EARLY).astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    try:
        out = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/actions/workflows/{workflow_file}/runs"
                f"?created=>={since}&per_page=20",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        runs = json.loads(out.stdout).get("workflow_runs", [])
    except Exception:
        return None
    return prior_run_in_window(
        runs, slot_at, datetime.now(timezone.utc), run_id
    )
