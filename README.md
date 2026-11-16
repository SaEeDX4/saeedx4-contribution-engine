# saeedx4-contribution-engine

A GitHub workflow health monitoring toolkit — and the home of a transparent,
owner-authorized contribution automation system.

## What this is

- `gh-health` — a small Python CLI that turns GitHub Actions workflow-run
  data into a readable health report (success rates, failures, stuck runs).
- `planner/` — a randomized daily activity planner. Every day it draws 3–10
  activity *opportunities* with a CSPRNG. An opportunity is a chance to do
  meaningful work from `BACKLOG.md`, never a promise of a commit: when no
  worthwhile work is ready, the slot is recorded as a no-op.
- `verify/` — contribution verification. Every eligible action is recorded in
  an expected ledger and later compared against the owner's actual GitHub
  contribution graph (pending < 24h, delayed 24–48h, mismatch > 48h).

## Automation transparency

All automated activity in this repository is disclosed: automated commits and
pull requests carry an `Automated-By` metadata block, a run ID, and the
`automation` label, and are recorded in `ledger/`. Automation operates on
behalf of the repository owner under his standing authorization. Automated
work is never presented as manually written.

## Emergency stop

Create a file named `AUTOMATION_PAUSED` in the repository root (or disable
the workflows under the Actions tab) to halt all automation immediately.
See `OPERATIONS.md`.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install pytest
PYTHONPATH=src:. python -m pytest
python -m gh_health.cli < runs.json
```
