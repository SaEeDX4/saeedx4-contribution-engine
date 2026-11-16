# Weekly scheduling — randomized push distribution

Owner directive, 2026-11-16 (permanent). Implemented in
`planner/weekly.py` (planning) and `planner/accounting.py` (enforcement),
validated by `tests/test_k5_weekly.py` (52 simulated weeks).

## The model

Each calendar week (Monday 00:00 – Sunday 23:59:59, America/Vancouver):

| Day kind | Count per week | Rule |
|---|---|---|
| Single Push Day (A) | exactly 1 | Exactly 1 intended automated push that local day, randomized time |
| Three Push Day (B) | exactly 1, different weekday | Exactly 3 intended automated pushes, randomized, ≥ 2 h apart |
| Standard | remaining 5 | 3–10 randomized activity *opportunities* (≥ 90 min apart) — opportunities are not pushes |

A and B are drawn uniformly (two distinct weekdays) and independently
every week — no rotation. Plans are drawn with a CSPRNG in production
(`secrets.SystemRandom`); tests inject seeded RNGs for reproducibility.

## Accounting

- Caps apply to the **combined** activity of both authorized
  repositories, never per repo.
- A **push** is one operation that updates a remote branch: a direct
  branch push, a push of automated commits to a branch, or a PR merge
  that updates the target branch. Pushes, commits, pull requests and
  GitHub-attributed contributions are four separate metrics; a push may
  carry many commits, and a contribution is recorded only when GitHub
  confirms it.
- Every push first claims its plan slot in the push ledger
  (`planner/accounting.py`). Claim keys are idempotent
  (`week:date:push:slot`), so retries and duplicate runs can never
  create an extra push. Ledger state is written atomically and survives
  restarts.
- If no legitimate, validated backlog work is ready at a push slot, the
  slot resolves to a recorded **no-op** and the shortfall is reported by
  the verification sweeps. Work is never fabricated to meet a number.
- Security-critical exceptions never hide inside randomized activity;
  they follow the documented exception + approval path in SECURITY.md.

## Persistence

The next week's plan is generated before the week begins (Sunday
23:37 America/Vancouver) and stored in `ledger/weeks/`. A stored plan
is never redrawn. The in-repo copy of the plan rides the week's first
actual push, so persisting the plan never consumes a push slot itself.

## Verification

The three daily sweeps compare planned vs. actual push counts, check
special-day cap compliance, and classify discrepancies as
PENDING / DELAYED / CONFIRMED MISMATCH as usual.
