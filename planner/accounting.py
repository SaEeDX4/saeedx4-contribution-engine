"""Combined push accounting for the two authorized repositories.

Owner directive (2026-11-16, permanent): the Single Push Day cap (1) and
the Three Push Day cap (3) apply to the COMBINED automated activity of
``saeedx4-contribution-engine`` and ``saeedx4-achievement-lab`` — never
per repository. Standard days have no push cap (their 3-10 slots are
opportunities, not pushes).

Definitions (kept strictly separate, per the directive):
- PUSH: one operation that updates a remote branch — a direct branch
  push, a push of automated commits to a branch, or a pull-request
  merge that updates the target branch. A push may carry many commits.
- COMMIT, PULL REQUEST, CONTRIBUTION: tracked as their own metrics;
  one push != one commit != one contribution.

Every push must first *claim* its plan slot. Claims are idempotent:
the same idempotency key (week_id + date + slot index) can be claimed
exactly once, so a workflow retry or duplicate run can never create an
extra push. State is a JSON file written atomically; it survives
restarts and partial failures. An empty backlog resolves a slot as a
recorded no-op — never as a fabricated push.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

AUTHORIZED_REPOS = ("saeedx4-contribution-engine", "saeedx4-achievement-lab")

# Daily automated-push caps by day kind (combined across both repos).
CAPS = {"single_push": 1, "three_push": 3, "standard": None}


class CapExceeded(RuntimeError):
    """Raised when a push would exceed the day's combined cap."""


@dataclass
class PushLedger:
    path: Path
    state: dict

    @classmethod
    def load(cls, path: Path) -> "PushLedger":
        path = Path(path)
        if path.exists():
            return cls(path, json.loads(path.read_text()))
        return cls(path, {"claims": {}, "events": []})

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2))
        tmp.replace(self.path)

    # -- queries ---------------------------------------------------------
    def pushes_on(self, day: date) -> int:
        return sum(
            1
            for c in self.state["claims"].values()
            if c["date"] == day.isoformat() and c["status"] == "pushed"
        )

    def metric(self, kind: str) -> int:
        return sum(1 for e in self.state["events"] if e["metric"] == kind)

    # -- mutations -------------------------------------------------------
    def claim_push(
        self,
        *,
        week_id: str,
        day: date,
        day_kind: str,
        slot_index: int,
        repo: str,
    ) -> str:
        """Reserve one push slot. Returns the idempotency key.

        Re-claiming the same key returns it without side effects (safe
        retry). Raises CapExceeded if the day's combined cap is full,
        ValueError for an unauthorized repository or unknown day kind.
        """
        if repo not in AUTHORIZED_REPOS:
            raise ValueError(f"repository not authorized: {repo}")
        if day_kind not in CAPS:
            raise ValueError(f"unknown day kind: {day_kind}")
        key = f"{week_id}:{day.isoformat()}:push:{slot_index}"
        existing = self.state["claims"].get(key)
        if existing is not None:
            return key  # idempotent retry — no new claim, no extra push
        cap = CAPS[day_kind]
        if cap is not None and self.pushes_on(day) >= cap:
            raise CapExceeded(
                f"{day} ({day_kind}) combined push cap {cap} already reached"
            )
        self.state["claims"][key] = {
            "date": day.isoformat(),
            "day_kind": day_kind,
            "repo": repo,
            "status": "claimed",
        }
        self._save()
        return key

    def record_push(self, key: str, *, commits: int, pull_request: bool) -> None:
        """Mark a claimed slot as actually pushed and log the separate
        metrics (push / commits / pull request) distinctly."""
        claim = self.state["claims"].get(key)
        if claim is None:
            raise KeyError(f"unknown claim: {key}")
        if claim["status"] == "pushed":
            return  # retry of the recording step itself is a no-op
        claim["status"] = "pushed"
        self.state["events"].append(
            {"metric": "push", "key": key, "repo": claim["repo"], "date": claim["date"]}
        )
        for _ in range(commits):
            self.state["events"].append(
                {"metric": "commit", "key": key, "repo": claim["repo"], "date": claim["date"]}
            )
        if pull_request:
            self.state["events"].append(
                {"metric": "pull_request", "key": key, "repo": claim["repo"], "date": claim["date"]}
            )
        self._save()

    def record_noop(self, key: str, *, reason: str) -> None:
        """Resolve a claimed slot as an honest no-op (e.g. empty backlog).
        A no-op never counts as a push."""
        claim = self.state["claims"].get(key)
        if claim is None:
            raise KeyError(f"unknown claim: {key}")
        if claim["status"] != "claimed":
            return
        claim["status"] = "noop"
        claim["reason"] = reason
        self._save()

    def record_contribution(self, *, day: date, repo: str, ref: str) -> None:
        """Log a GitHub-attributed contribution once GitHub confirms it.
        Contributions are observed, never assumed from pushes."""
        self.state["events"].append(
            {"metric": "contribution", "date": day.isoformat(), "repo": repo, "ref": ref}
        )
        self._save()
