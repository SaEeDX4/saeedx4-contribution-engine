# Backlog — the only source of automated work

An item is *ready* only when it has an acceptance test. The executor takes
the highest ready item; if none is ready, the slot is a recorded no-op.

## Ready

- [ ] B-001: `gh-health` — add median run duration to the health report.
      Acceptance: unit tests cover empty, single and multi-run inputs.
- [ ] B-002: `gh-health` — add a `--format json` output mode.
      Acceptance: JSON output validates against a documented schema; tests pass.
- [ ] B-003: Link checker for Markdown docs (local links only).
      Acceptance: detects a deliberately broken local link in a fixture; no network calls.
- [ ] B-004: Coverage report in CI; fail under 80% for `gh_health`.
      Acceptance: CI job publishes the coverage summary as a step summary.

## Ideas (not ready until specified)

- Flaky-workflow detector (alternating pass/fail on the same commit range).
- Weekly health digest generator for a repository.
