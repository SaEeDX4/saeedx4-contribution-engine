"""Randomized daily activity planner.

Rules (owner-approved):
- Each local day (America/Vancouver) independently draws an integer number of
  activity *opportunities* uniformly from 3..10 using a CSPRNG
  (``secrets`` module). An opportunity is a chance to do work, never a
  guarantee of a commit: if no meaningful backlog item is ready, the slot is
  recorded as a no-op.
- Opportunity times are drawn uniformly across the local day with a minimum
  separation of 90 minutes, enforced by rejection sampling.
- Plans are deterministic given their stored seed record: the plan file for a
  date is written once and never regenerated (idempotency key = the date).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, time, timedelta

MIN_SLOTS = 3
MAX_SLOTS = 10
MIN_SEPARATION = timedelta(minutes=90)
DAY = timedelta(hours=24)


@dataclass(frozen=True)
class DayPlan:
    day: date
    slots: tuple[time, ...]

    @property
    def slot_ids(self) -> tuple[str, ...]:
        return tuple(f"{self.day.isoformat()}#{i + 1}" for i in range(len(self.slots)))


def draw_slot_count(rng: secrets.SystemRandom | None = None) -> int:
    rng = rng or secrets.SystemRandom()
    return rng.randint(MIN_SLOTS, MAX_SLOTS)


def plan_day(day: date, rng: secrets.SystemRandom | None = None) -> DayPlan:
    """Draw one day's opportunity times. Pure apart from the injected RNG."""
    rng = rng or secrets.SystemRandom()
    count = draw_slot_count(rng)
    offsets: list[timedelta] = []
    attempts = 0
    while len(offsets) < count and attempts < 10_000:
        attempts += 1
        candidate = timedelta(seconds=rng.randrange(int(DAY.total_seconds())))
        if all(abs(candidate - other) >= MIN_SEPARATION for other in offsets):
            offsets.append(candidate)
    if len(offsets) < count:  # pragma: no cover - statistically unreachable
        raise RuntimeError("could not place slots with required separation")
    slots = tuple(
        sorted(
            time(hour=o.seconds // 3600, minute=(o.seconds % 3600) // 60, second=o.seconds % 60)
            for o in offsets
        )
    )
    return DayPlan(day=day, slots=slots)


if __name__ == "__main__":  # small manual/demo entry point
    import sys
    from zoneinfo import ZoneInfo

    from datetime import datetime

    today = datetime.now(ZoneInfo("America/Vancouver")).date()
    plan = plan_day(today)
    print(f"{plan.day}: {len(plan.slots)} opportunities")
    for slot_id, slot in zip(plan.slot_ids, plan.slots):
        print(f"  {slot_id}  {slot.isoformat()} America/Vancouver")
    sys.exit(0)
