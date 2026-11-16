# Contribution eligibility — what counts, per GitHub's own documentation

A commit counts toward the owner's profile contribution graph only if **all**
of these hold (GitHub Docs, "Why are my contributions not showing up"):

- The commit author's email is associated with the owner's GitHub account
  (we use the account's official noreply address).
- The repository is standalone, not a fork (both project repos are).
- The commit is on the default branch (`main`) or `gh-pages` — feature-branch
  commits count once merged into `main`.
- At least one of: the author is a collaborator/owner of the repo (true),
  has forked it, or has opened a PR/issue in it.

Issues, pull requests and discussions count when opened in a standalone
repository. Co-authored commits follow the same rules for each co-author.

Timing: GitHub may take up to 24 hours to display a qualifying contribution.
This project therefore classifies verification results as pending (<24h),
delayed (24–48h) and mismatch (>48h), and never claims a contribution counted
before the verifier observes it on the graph.

A workflow *run* is not a contribution. Commits authored solely by
`github-actions[bot]` belong to the bot, not the owner — which is why this
system attributes authorized work to the owner as author (with the automation
identity as committer and full disclosure in the commit body), exactly as the
owner directed.
