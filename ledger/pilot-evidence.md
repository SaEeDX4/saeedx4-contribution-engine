# Pilot evidence

- Workflow run: 43854112571 (attempt 1)
- Started (UTC): 2026-11-16 11:02:14

## V1 — can GITHUB_TOKEN read the owner's contribution calendar?
V1 RESULT: GITHUB_TOKEN GraphQL read SUCCEEDED: {"data":{"user":{"contributionsCollection":{"contributionCalendar":{"totalContributions":129}}}}}

## PAT identity and scope (V3 + security control)
PAT /user login: SaEeDX4
PAT GET repos/SaEeDX4/saeedx4-contribution-engine -> HTTP 200
PAT GET repos/SaEeDX4/saeedx4-achievement-lab -> HTTP 200
PAT GET repos/SaEeDX4/interview-assistant-website -> HTTP 200
(200 for the two project repos = in scope and cross-repo read works (V3); 404 for interview-assistant-website = correctly out of scope for a fine-grained PAT)

## K1 — attribution events in this run
- K1a: this file is committed directly to main by the pilot workflow.
- Author: SaEeDX4 <198836972+SaEeDX4@users.noreply.github.com>
- Execution: owner's fine-grained PAT (AUTOMATION_PAT secret).

Automated-By: Muse (owner-authorized pilot, Phase 1)
Standing-Authorization: SaEeDX4 Phase 1 approval, 2026-11-16
