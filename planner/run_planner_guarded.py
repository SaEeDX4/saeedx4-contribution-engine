"""Slot-guarded planner entry point (pilot dry run).

Runs planner.planner.plan_day for today (America/Vancouver) only when
this execution matches today's planner slot (08:12) under the same
guard rules as verification; off-phase firings are no-ops and stale
executions perform no work. See verify/slotguard.py.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from planner.planner import plan_day  # noqa: E402
from verify.slotguard import PLANNER_SLOTS, TZ, match_slot  # noqa: E402


def main() -> int:
    now_utc = datetime.now(timezone.utc)
    match = match_slot(now_utc, PLANNER_SLOTS, os.environ.get("VERIFY_SLOT") or None)
    if match is None or match.state == "off_phase":
        print("planner: off-phase firing — no-op")
        return 0
    print(f"planner slot {match.slot_id}: {match.state} (delay {match.delay})")
    if match.state == "stale":
        print("planner: STALE execution — no work performed")
        return 0
    from verify.runcheck import find_prior_run

    prior = find_prior_run("planner.yml", match.slot_at)
    if prior is not None:
        print(f"planner: duplicate of run {prior.get('id')} — no work repeated")
        return 0
    today = now_utc.astimezone(TZ).date()
    plan = plan_day(today)
    print(f"plan for {today}: {len(plan.slots)} opportunities")
    for slot in plan.slots:
        print(f"  - {slot.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
