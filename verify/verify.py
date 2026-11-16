"""Contribution verification: compare expected vs. observed, classify delay.

The engine records every eligible action in an *expected ledger* at the moment
it happens. A verification run reads the observed per-day contribution counts
(GitHub GraphQL ``contributionCalendar``) and classifies each expected item:

- ``pending``   -- observed, or < 24h old (GitHub indexing window)
- ``delayed``   -- not yet observed, 24-48h old
- ``mismatch``  -- not yet observed after 48h: a critical defect. Investigate;
                   never compensate with artificial activity.

This module is pure logic; fetching is done by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

PENDING_WINDOW = timedelta(hours=24)
MISMATCH_AFTER = timedelta(hours=48)


@dataclass(frozen=True)
class ExpectedItem:
    item_id: str
    day: date  # UTC day the contribution should land on
    happened_at: datetime  # timezone-aware UTC


@dataclass(frozen=True)
class Verdict:
    item_id: str
    state: str  # "observed" | "pending" | "delayed" | "mismatch"


def classify(
    item: ExpectedItem,
    observed_counts: dict[date, int],
    expected_counts: dict[date, int],
    now: datetime,
) -> Verdict:
    """Classify one expected item against observed per-day totals.

    ``observed_counts`` / ``expected_counts`` map a UTC day to how many
    contributions GitHub shows / the ledger expects for that day. An item is
    observed when its day's observed total reaches the expected total.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if observed_counts.get(item.day, 0) >= expected_counts.get(item.day, 0) > 0:
        return Verdict(item.item_id, "observed")
    age = now - item.happened_at
    if age < PENDING_WINDOW:
        return Verdict(item.item_id, "pending")
    if age < MISMATCH_AFTER:
        return Verdict(item.item_id, "delayed")
    return Verdict(item.item_id, "mismatch")


def summarize(verdicts: list[Verdict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v.state] = counts.get(v.state, 0) + 1
    return counts
