"""Randomized weekly push-distribution planner.

Owner directive (2026-11-16, permanent): every calendar week
(Monday 00:00 - Sunday 23:59:59, America/Vancouver) gets

- exactly ONE "Single Push Day" (Special Day A): exactly 1 intended
  automated Git push that local day, at a randomized time;
- exactly ONE different "Three Push Day" (Special Day B): exactly 3
  intended automated Git pushes that local day, randomized and spread
  (minimum 2 hours apart);
- the remaining five days keep the standard model: 3-10 randomized
  activity *opportunities* (see planner.py) with >= 90 minutes
  separation. Opportunities are NOT pushes.

The two special weekdays are drawn uniformly at random (two distinct
values) independently each week. Push limits apply to BOTH authorized
repositories combined; accounting lives in accounting.py.

A push is an *intention*, never a fabrication order: if no legitimate,
validated backlog work is ready at a push slot, the slot resolves to an
honest no-op and the shortfall is reported by the verification sweeps.

Plans are generated once per week and persisted; regeneration of an
existing week returns the stored plan unchanged (idempotency key = the
week's Monday). All times are timezone-aware (America/Vancouver) and
DST is handled by zoneinfo arithmetic on local dates.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Vancouver")
DAY = timedelta(hours=24)
PUSH_MIN_SEPARATION = timedelta(hours=2)

KIND_SINGLE = "single_push"
KIND_THREE = "three_push"
KIND_STANDARD = "standard"


def _random_offsets(rng, count: int, min_sep: timedelta) -> tuple[timedelta, ...]:
    offsets: list[timedelta] = []
    attempts = 0
    while len(offsets) < count and attempts < 20_000:
        attempts += 1
        candidate = timedelta(seconds=rng.randrange(int(DAY.total_seconds())))
        if all(abs(candidate - other) >= min_sep for other in offsets):
            offsets.append(candidate)
    if len(offsets) < count:  # pragma: no cover - statistically unreachable
        raise RuntimeError("could not place times with required separation")
    return tuple(sorted(offsets))


def _to_local_dt(day: date, offset: timedelta) -> datetime:
    base = datetime.combine(day, time(0, 0), tzinfo=TZ)
    return base + offset


@dataclass(frozen=True)
class WeekDayPlan:
    day: date
    kind: str  # KIND_SINGLE | KIND_THREE | KIND_STANDARD
    push_times: tuple[datetime, ...] = ()  # intended pushes (special days)
    opportunity_times: tuple[datetime, ...] = ()  # standard days only

    @property
    def push_cap(self) -> int:
        return len(self.push_times)


@dataclass(frozen=True)
class WeekPlan:
    monday: date
    days: tuple[WeekDayPlan, ...] = field(default_factory=tuple)

    @property
    def week_id(self) -> str:
        iso = self.monday.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    @property
    def single_push_day(self) -> WeekDayPlan:
        return next(d for d in self.days if d.kind == KIND_SINGLE)

    @property
    def three_push_day(self) -> WeekDayPlan:
        return next(d for d in self.days if d.kind == KIND_THREE)

    def to_dict(self) -> dict:
        return {
            "week_id": self.week_id,
            "monday": self.monday.isoformat(),
            "timezone": "America/Vancouver",
            "days": [
                {
                    "date": d.day.isoformat(),
                    "kind": d.kind,
                    "push_times": [t.isoformat() for t in d.push_times],
                    "opportunity_times": [t.isoformat() for t in d.opportunity_times],
                }
                for d in self.days
            ],
        }

    @staticmethod
    def from_dict(data: dict) -> "WeekPlan":
        days = tuple(
            WeekDayPlan(
                day=date.fromisoformat(d["date"]),
                kind=d["kind"],
                push_times=tuple(datetime.fromisoformat(t) for t in d["push_times"]),
                opportunity_times=tuple(
                    datetime.fromisoformat(t) for t in d["opportunity_times"]
                ),
            )
            for d in data["days"]
        )
        return WeekPlan(monday=date.fromisoformat(data["monday"]), days=days)


def plan_week(monday: date, rng=None) -> WeekPlan:
    """Draw one week's plan. Pure apart from the injected RNG.

    ``rng`` needs ``sample``, ``randint`` and ``randrange``
    (``random.Random`` for seeded tests, ``secrets.SystemRandom`` in
    production).
    """
    if monday.weekday() != 0:
        raise ValueError("week must start on a Monday")
    rng = rng or secrets.SystemRandom()
    try:
        from .planner import plan_day  # standard-day opportunities (3-10)
    except ImportError:  # loaded without package context
        from planner.planner import plan_day

    special = rng.sample(range(7), 2)
    single_idx, three_idx = special[0], special[1]

    days: list[WeekDayPlan] = []
    for i in range(7):
        day = monday + timedelta(days=i)
        if i == single_idx:
            offsets = _random_offsets(rng, 1, PUSH_MIN_SEPARATION)
            days.append(
                WeekDayPlan(day, KIND_SINGLE, tuple(_to_local_dt(day, o) for o in offsets))
            )
        elif i == three_idx:
            offsets = _random_offsets(rng, 3, PUSH_MIN_SEPARATION)
            days.append(
                WeekDayPlan(day, KIND_THREE, tuple(_to_local_dt(day, o) for o in offsets))
            )
        else:
            std = plan_day(day, rng=rng)
            opps = tuple(
                _to_local_dt(day, timedelta(hours=t.hour, minutes=t.minute, seconds=t.second))
                for t in std.slots
            )
            days.append(WeekDayPlan(day, KIND_STANDARD, (), opps))
    return WeekPlan(monday=monday, days=tuple(days))


def week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def load_or_create_week_plan(monday: date, store_dir: Path, rng=None) -> WeekPlan:
    """Persisted, idempotent plan access: an existing stored plan for the
    week is returned unchanged, so retries/restarts never redraw."""
    store_dir = Path(store_dir)
    path = store_dir / f"week-{WeekPlan(monday=monday).week_id}.json"
    if path.exists():
        return WeekPlan.from_dict(json.loads(path.read_text()))
    plan = plan_week(monday, rng=rng)
    store_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(plan.to_dict(), indent=2))
    tmp.replace(path)  # atomic: a crash mid-write never corrupts the plan
    return plan


if __name__ == "__main__":  # demo: print next week's plan
    import sys

    today = datetime.now(TZ).date()
    target = week_monday(today) + timedelta(days=7)
    plan = plan_week(target)
    print(json.dumps(plan.to_dict(), indent=2))
    sys.exit(0)
