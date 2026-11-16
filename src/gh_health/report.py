"""Summarize GitHub Actions workflow-run data into a health report.

Input is the JSON shape returned by the GitHub REST API endpoint
``GET /repos/{owner}/{repo}/actions/runs`` (a dict with ``workflow_runs``).
The functions here are pure: no network, no clock, fully testable.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowHealth:
    name: str
    total: int
    succeeded: int
    failed: int
    cancelled: int
    in_progress: int

    @property
    def success_rate(self) -> float:
        finished = self.succeeded + self.failed
        if finished == 0:
            return 1.0
        return self.succeeded / finished


def summarize_runs(runs: list[dict]) -> list[WorkflowHealth]:
    """Group raw workflow-run dicts by workflow name and count outcomes."""
    by_name: dict[str, Counter] = {}
    for run in runs:
        name = str(run.get("name") or run.get("workflow_id") or "unknown")
        counter = by_name.setdefault(name, Counter())
        counter["total"] += 1
        status = run.get("status")
        conclusion = run.get("conclusion")
        if status != "completed":
            counter["in_progress"] += 1
        elif conclusion == "success":
            counter["succeeded"] += 1
        elif conclusion == "cancelled":
            counter["cancelled"] += 1
        else:
            counter["failed"] += 1
    return [
        WorkflowHealth(
            name=name,
            total=c["total"],
            succeeded=c["succeeded"],
            failed=c["failed"],
            cancelled=c["cancelled"],
            in_progress=c["in_progress"],
        )
        for name, c in sorted(by_name.items())
    ]


def render_markdown(health: list[WorkflowHealth]) -> str:
    lines = [
        "# Workflow health report",
        "",
        "| Workflow | Runs | Success | Failed | Cancelled | Running | Success rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for h in health:
        lines.append(
            f"| {h.name} | {h.total} | {h.succeeded} | {h.failed} | "
            f"{h.cancelled} | {h.in_progress} | {h.success_rate:.0%} |"
        )
    if not health:
        lines.append("| _(no runs)_ | 0 | 0 | 0 | 0 | 0 | — |")
    return "\n".join(lines) + "\n"
