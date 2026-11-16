# Architecture

## Components

1. **gh-health toolkit** (`src/gh_health/`) — pure, tested library + CLI that
   summarizes GitHub Actions workflow runs into a health report.
2. **Planner** (`planner/planner.py`) — draws each day's activity opportunities
   (3–10, CSPRNG via `secrets`, ≥90-minute separation, America/Vancouver day).
   A plan is written once per date; the date is the idempotency key.
3. **Heartbeat executor** (production, not yet active) — short jobs that check
   whether a planned slot is due and whether a *meaningful* backlog item is
   ready. No ready work means a recorded no-op. It never invents work.
4. **Verifier** (`verify/verify.py`) — compares the expected ledger
   (`ledger/expected.jsonl`) with observed contribution counts from GitHub's
   GraphQL `contributionCalendar`, classifying each item pending / delayed /
   mismatch (24h / 48h thresholds).

## Attribution model

- Author of automated commits: the repository owner, `SaEeDX4
  <198836972+SaEeDX4@users.noreply.github.com>`, acting through automation he
  explicitly authorized for these two repositories only.
- Committer: the automation identity that applied the change.
- Every automated commit/PR carries an `Automated-By` block, a run ID and the
  backlog item ID, and is mirrored into the public ledger. Automated work is
  never described as manually written.
- A contribution is only ever reported as counted after the verifier observes
  it on the owner's actual contribution graph.

## Boundaries

This system operates only in `saeedx4-contribution-engine` and
`saeedx4-achievement-lab`. Cross-repository interaction is read-only.
