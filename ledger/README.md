# Ledger

Public, append-only record of this system's activity.

- `expected.jsonl` — one line per eligible action, written when it happens:
  `{"id", "utc", "repo", "kind", "ref"}`.
- `verifications.jsonl` — one line per verification run: observed counts,
  per-item verdicts (observed / pending / delayed / mismatch), workflow
  health, and achievement snapshot hash.
