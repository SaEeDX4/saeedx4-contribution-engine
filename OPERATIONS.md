# Operations

## Pause / resume

- **Pause everything:** add an empty file `AUTOMATION_PAUSED` to the repo
  root (commit it), or disable each workflow under Actions → ⋯ → Disable.
- **Resume:** remove the file / re-enable the workflows.
- **Stop permanently:** disable all workflows *and* revoke the fine-grained
  PAT (GitHub → Settings → Developer settings → Personal access tokens).

## Credential renewal (annual)

The fine-grained PAT expires. 30 days before expiry the monthly audit flags
it. To rotate: create a replacement token with identical scope (only the two
project repositories), update the `AUTOMATION_PAT` secret in both repos,
verify one pilot run, then revoke the old token.

## Failure alerts

The three daily verification runs record results in `ledger/`. A confirmed
mismatch (expected contribution still invisible after 48h) is treated as a
critical defect: automation pauses, the cause is investigated, and no
compensating activity is created.

## Health checks

- Actions tab: planner, verify and CI workflows should show recent runs.
- Scheduled workflows in public repos are disabled by GitHub after 60 days
  without repository activity; the monthly audit checks workflow state.
