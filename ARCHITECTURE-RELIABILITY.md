# Reliability architecture — scheduling, verification, recovery

Owner directive, 2026-11-18. This document records the root-cause
findings for the K3 scheduling failures and the architecture that
replaces "trust GitHub's scheduler" with layered, self-healing
scheduling. Production automation remains OFF; this is the pilot
implementation being proven over consecutive days of unattended
scheduled execution.

## Root cause (evidence, Nov 16–18, 2026)

GitHub Actions scheduled delivery in this repository is best-effort
and, in observed practice, unreliable in both occurrence and timing:

| Intended slot (America/Vancouver) | Observed scheduled runs |
|---|---|
| verify 08:07 / 15:07 / 22:07, Nov 16 | One run only: 15:43 Vancouver (run 43981759336) |
| verify, Nov 17 | 06:18 Vancouver (44101675657) and 14:51 Vancouver (44194059128) — two runs for three slots |
| verify, Nov 18 | 05:53 Vancouver — belongs to no clean slot |
| planner 08:12, Nov 16–17 | One run per day, at 15:43 / 14:51 Vancouver |

Offsets range from minutes to many hours against any single
interpretation of the cron (with or without the `timezone:` field),
and whole slots never materialize. Additionally, British Columbia
adopted permanent daylight time in March 2026, so America/Vancouver
is UTC−7 year-round — any hand-computed "PST = UTC−8" assumption is
wrong; zoneinfo is the only authority used in code.

Conclusion: no single GitHub cron entry can be trusted. Reliability
must come from redundancy, guards, and recovery — not from the
scheduler.

## The layered design

**Layer 1 — GitHub Actions (execution layer).**
- `verify.yml` declares every Vancouver slot at BOTH of its possible
  UTC phases (UTC−7 and UTC−8), so at least one firing lands near
  each slot regardless of offset behaviour.
- `verify/slotguard.py` runs first in every execution and classifies
  it against the *current Vancouver day*: ON_TIME (≤15 min late),
  DELAYED (15–180 min, verification runs, reported as delayed),
  STALE (>180 min or another day's slot — recorded, no work),
  off-phase (no-op). Work can never leak into a different local
  calendar day.
- `verify/runcheck.py`: before doing work, an execution checks
  whether the same slot already completed today; duplicates exit
  without repeating work. Combined with the accounting ledger's
  idempotent push claims (planner/accounting.py), delayed or
  duplicated executions cannot create duplicate pushes or breach the
  1-push / 3-push combined daily caps.
- `verify/full_verify.py` performs the actual Actions-side
  verification, read-only: Contribution Graph (GraphQL via
  GITHUB_TOKEN), ledger comparison (pending/delayed/mismatch),
  attribution audit of recent commits in both repos (noreply identity
  + Automated-By disclosure), and weekly-plan compliance. The JSON
  report is uploaded as a run artifact.

**Layer 2 — Watchdog (in-Actions recovery).**
- `watchdog.yml` fires every 30 minutes. For each of today's slots
  overdue by >45 minutes with no run in its acceptance window, it
  dispatches a recovery run carrying the slot id
  (`gh workflow run`, using the watchdog's own GITHUB_TOKEN with
  `actions: write` scoped to that workflow only — no new credential,
  no PAT change).
- Recovery is same-day only: after Vancouver midnight a missing slot
  is reported, never executed late. The dispatched run is itself
  slot-guarded and duplicate-checked, so recovery is idempotent.

**Layer 3 — Muse sweeps (independent monitoring layer).**
- Muse's own scheduled sweeps (08:07 / 15:07 / 22:07 Vancouver) do
  not depend on GitHub at all and have fired exactly on time every
  observed day. They perform the checks Actions cannot: Achievements
  via the signed-in browser (GitHub has no Achievements API), plus an
  independent read of the graph, both repos' health, execution
  health (including missed or duplicated Actions runs and watchdog
  recovery events), and weekly push-limit compliance. They alert the
  owner on confirmed problems only.

**What Muse cannot do (verified 2026-11-18):** Muse's GitHub
connector exposes 46 tools; none list workflow runs and none can
trigger `workflow_dispatch`. The AUTOMATION_PAT holds Actions:
Read-only by design. Therefore recovery dispatch lives inside
Actions (Layer 2), and Muse's role is detection, verification and
reporting — which is the correct separation anyway: the monitor must
not depend on the system it monitors.

## Tolerances and reporting

- ON_TIME ≤ 15 min after the slot; DELAYED 15–180 min (runs, flagged);
  MISSED = no execution within the window and no same-day recovery —
  reported by the next Muse sweep and in the watchdog summary.
- Every verification report states its slot, state and delay; missed
  checks are never silently absorbed or back-filled with fake work.

## Proof standard for K3

K3 passes only with documented evidence from actual unattended
scheduled executions over at least two consecutive days: run IDs,
scheduled vs actual timestamps, conclusions, and any watchdog
recovery events — collected by a scheduled evidence check, never
from manual dispatches.
