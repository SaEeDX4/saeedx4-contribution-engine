import random
from datetime import date, datetime, timedelta, timezone

from planner.planner import MAX_SLOTS, MIN_SEPARATION, MIN_SLOTS, plan_day
from verify.verify import ExpectedItem, classify


def test_plan_bounds_and_separation():
    rng = random.Random(1234)
    for i in range(60):
        plan = plan_day(date(2026, 1, 1) + timedelta(days=i), rng)
        assert MIN_SLOTS <= len(plan.slots) <= MAX_SLOTS
        times = sorted(plan.slots)
        for a, b in zip(times, times[1:]):
            delta = datetime.combine(date.min, b) - datetime.combine(date.min, a)
            assert delta >= MIN_SEPARATION
        assert len(set(plan.slot_ids)) == len(plan.slots)


def test_classify_states():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    day = date(2026, 1, 9)
    expected = {day: 1}
    fresh = ExpectedItem("a", day, now - timedelta(hours=2))
    assert classify(fresh, {}, expected, now).state == "pending"
    mid = ExpectedItem("b", day, now - timedelta(hours=30))
    assert classify(mid, {}, expected, now).state == "delayed"
    old = ExpectedItem("c", day, now - timedelta(hours=72))
    assert classify(old, {}, expected, now).state == "mismatch"
    assert classify(old, {day: 1}, expected, now).state == "observed"
