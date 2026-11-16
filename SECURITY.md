# Security

- **Least privilege.** Every workflow declares explicit `permissions:`.
  Automation uses one fine-grained personal access token scoped to exactly
  two repositories (`saeedx4-contribution-engine`, `saeedx4-achievement-lab`)
  with Contents / Pull requests / Issues write and Metadata read. It has **no
  Workflows permission**: automation never modifies `.github/workflows/`.
- **Token handling.** The token lives only as a repository Actions secret.
  It is never committed, logged, or printed. Rotation: annually, and
  immediately on any suspicion of exposure (see OPERATIONS.md).
- **Pinned actions.** Third-party actions are pinned to full commit SHAs.
- **No untrusted code execution.** Workflows never run code from forks or
  untrusted PR content with secrets present.
- **Emergency stop.** An `AUTOMATION_PAUSED` file in the repo root, disabling
  workflows in the Actions tab, or revoking the PAT each halt automation.
- **Never automated:** repository deletion, force-push, history rewrite,
  permission changes, payments, adding collaborators.
