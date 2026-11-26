"""Full verification, GitHub Actions side (replaces the pilot report).

What this does (all read-only; it never writes to any repository):

1. Slot guard (verify/slotguard.py): classifies this execution against
   today's America/Vancouver verification slots. Off-phase and stale
   executions exit without doing verification work.
2. Contribution Graph: reads the owner's contribution calendar via the
   GraphQL API with the workflow's GITHUB_TOKEN (read path proven in
   pilot test V1) and extracts per-day counts, including today
   (Vancouver) and the trailing year total.
3. Ledger comparison: classifies every item of ledger/expected.jsonl
   with verify.verify.classify (pending / delayed / mismatch).
4. Attribution: lists recent commits in BOTH authorized repositories
   via the REST API and checks that automation-attributed commits use
   the owner's noreply identity and carry the Automated-By disclosure.
5. Weekly push-limit compliance: loads the stored week plan
   (ledger/weeks/week-<ISO>.json) and reports today's kind and cap;
   actual push counts come from the push ledger when present. (The
   authoritative combined-cap enforcement lives in
   planner/accounting.py at execution time; this is the audit view.)
6. Achievements: GitHub exposes NO API for Achievements. This script
   states that explicitly in its report; badge reading is owned by
   the Muse sweep layer (signed-in browser), by design.

Output: a JSON report on stdout, a human summary appended to
$GITHUB_STEP_SUMMARY when set, and the JSON written to the path in
$VERIFY_REPORT_PATH when set (the workflow uploads it as an artifact).
Exit code is 0 for a completed verification (findings are data, not
job failures); non-zero only for infrastructure errors.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verify.slotguard import TZ, VERIFY_SLOTS, match_slot  # noqa: E402
from verify.verify import ExpectedItem, classify, summarize  # noqa: E402

OWNER = "SaEeDX4"
REPOS = ("saeedx4-contribution-engine", "saeedx4-achievement-lab")
NOREPLY = "198836972+SaEeDX4@users.noreply.github.com"
GRAPHQL = (
    'query { user(login: "SaEeDX4") { contributionsCollection { '
    "contributionCalendar { totalContributions weeks { contributionDays "
    "{ date contributionCount } } } } } }"
)


class GhError(RuntimeError):
    """A gh CLI call failed; carries the captured stderr for diagnosis."""


def gh_json(args: list[str], retries: int = 2) -> dict:
    """Run `gh api ...` and parse JSON. On failure, RETRY (the GitHub
    GraphQL calendar query is known to fail transiently server-side)
    and finally raise GhError containing gh's stderr — never swallow
    the error text (2026-11-21: a bare CalledProcessError hid the
    actual GitHub error and made the failure undiagnosable)."""
    last: subprocess.CompletedProcess | None = None
    for attempt in range(retries + 1):
        out = subprocess.run(
            ["gh", "api", *args], capture_output=True, text=True
        )
        if out.returncode == 0:
            return json.loads(out.stdout)
        last = out
        if attempt < retries:
            import time

            time.sleep(5 * (attempt + 1))
    stderr = (last.stderr or "").strip()[-500:] if last else ""
    raise GhError(
        f"gh api {' '.join(args[:1])} failed after {retries + 1} attempts: "
        f"{stderr or '(no stderr captured)'}"
    )


def fetch_calendar() -> tuple[int, dict[date, int]]:
    data = gh_json(["graphql", "-f", f"query={GRAPHQL}"])
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    counts: dict[date, int] = {}
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            counts[date.fromisoformat(day["date"])] = day["contributionCount"]
    return cal["totalContributions"], counts


def fetch_recent_commits(repo: str, since_days: int = 7) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    data = gh_json(
        [f"repos/{OWNER}/{repo}/commits?since={since}&per_page=50"]
    )
    result = []
    for entry in data:
        commit = entry["commit"]
        result.append(
            {
                "sha": entry["sha"][:10],
                "author_name": commit["author"]["name"],
                "author_email": commit["author"]["email"],
                "login": (entry.get("author") or {}).get("login"),
                "disclosure": "Automated-By" in commit["message"],
                "date": commit["author"]["date"],
            }
        )
    return result


def load_expected(root: Path) -> list[ExpectedItem]:
    path = root / "ledger" / "expected.jsonl"
    items: list[ExpectedItem] = []
    if not path.exists():
        return items
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        happened = datetime.fromisoformat(row["expected_at"].replace("Z", "+00:00"))
        items.append(
            ExpectedItem(row["id"], happened.date(), happened)
        )
    return items


def weekly_compliance(root: Path, today: date) -> dict:
    monday = today - timedelta(days=today.weekday())
    iso = monday.isocalendar()
    plan_path = root / "ledger" / "weeks" / f"week-{iso.year}-W{iso.week:02d}.json"
    if not plan_path.exists():
        return {"plan_file": str(plan_path), "stored": False}
    plan = json.loads(plan_path.read_text())
    entry = next((d for d in plan["days"] if d["day"] == today.isoformat()), None)
    return {
        "plan_file": str(plan_path),
        "stored": True,
        "week_id": plan["week_id"],
        "today": entry,
        "note": (
            "Caps are enforced at execution time by planner/accounting.py "
            "(combined across both repos, idempotent claims). This report "
            "shows the plan side; actuals are recorded in the push ledger."
        ),
    }


def main() -> int:
    root = Path(os.environ.get("VERIFY_ROOT", ".")).resolve()
    intended = os.environ.get("VERIFY_SLOT") or None
    now_utc = datetime.now(timezone.utc)
    match = match_slot(now_utc, VERIFY_SLOTS, intended, allow_prev_day_grace=True)
    today_van = now_utc.astimezone(TZ).date()

    report: dict = {
        "generated_at_utc": now_utc.isoformat(),
        "today_vancouver": today_van.isoformat(),
        "slot": None,
        "achievements": (
            "NOT CHECKED HERE: GitHub has no Achievements API. Badge "
            "reading is owned by the Muse sweep layer (signed-in "
            "browser), three times daily."
        ),
    }
    if match is None or match.state == "off_phase":
        report["slot"] = {"state": "off_phase"}
        report["verdict"] = "no-op (off-phase firing)"
        _emit(report)
        return 0
    report["slot"] = {
        "slot_id": match.slot_id,
        "state": match.state,
        "delay_seconds": int(match.delay.total_seconds()),
    }
    if match.state == "stale":
        report["verdict"] = "STALE execution — no verification performed"
        _emit(report)
        return 0

    from verify.runcheck import find_prior_run

    prior = find_prior_run("verify.yml", match.slot_at)
    if prior is not None:
        report["duplicate_of_run"] = prior.get("id")
        report["verdict"] = "duplicate — slot already verified, no work repeated"
        _emit(report)
        return 0

    try:
        return _verify_body(report, root, today_van, now_utc)
    except GhError as exc:
        report["verdict"] = f"INFRA ERROR — {exc}"
        report["infra_error"] = str(exc)
        _emit(report)
        return 2


def _verify_body(report: dict, root: Path, today_van: date, now_utc: datetime) -> int:
    total, counts = fetch_calendar()
    report["contribution_graph"] = {
        "total_last_year": total,
        "today_vancouver_count": counts.get(today_van, 0),
        "yesterday_vancouver_count": counts.get(
            today_van - timedelta(days=1), 0
        ),
    }

    expected = load_expected(root)
    expected_counts: dict[date, int] = {}
    for item in expected:
        expected_counts[item.day] = expected_counts.get(item.day, 0) + 1
    verdicts = [classify(i, counts, expected_counts, now_utc) for i in expected]
    report["ledger_comparison"] = {
        "expected_items": len(expected),
        "summary": summarize(verdicts),
        "mismatches": [v.item_id for v in verdicts if v.state == "mismatch"],
    }

    attribution = {}
    for repo in REPOS:
        commits = fetch_recent_commits(repo)
        automation = [c for c in commits if c["disclosure"]]
        bad = [
            c
            for c in automation
            if c["author_email"] != NOREPLY or c["login"] != OWNER
        ]
        attribution[repo] = {
            "recent_commits": len(commits),
            "automation_disclosed": len(automation),
            "attribution_violations": bad,
        }
    report["attribution"] = attribution
    report["weekly_compliance"] = weekly_compliance(root, today_van)
    report["verdict"] = (
        "CONFIRMED MISMATCH — investigate"
        if report["ledger_comparison"]["mismatches"]
        or any(a["attribution_violations"] for a in attribution.values())
        else "ok"
    )
    _emit(report)
    return 0


def _emit(report: dict) -> None:
    text = json.dumps(report, indent=2, default=str)
    print(text)
    path = os.environ.get("VERIFY_REPORT_PATH")
    if path:
        Path(path).write_text(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write("## Verification report\n\n```json\n" + text + "\n```\n")


if __name__ == "__main__":
    raise SystemExit(main())
