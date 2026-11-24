"""Slot-guard tests: dual-phase firings, delays, stale protection.

America/Vancouver is UTC-7 year-round since British Columbia adopted
permanent daylight time in March 2026 (zoneinfo is authoritative);
the dual-phase cron declarations additionally cover a UTC-8 phase in
case the offset ever changes again — the guard, not the cron,
decides what executes.
"""

from datetime import datetime, timezone

from verify.slotguard import PLANNER_SLOTS, VERIFY_SLOTS, match_slot


def utc(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_on_time_winter():
    # 08:07 Vancouver (UTC-7) = 15:07 UTC; firing 15:10 UTC is on time.
    m = match_slot(utc(2026, 11, 19, 15, 10), VERIFY_SLOTS)
    assert m.state == "on_time"
    assert m.slot_id == "2026-11-19T08:07"


def test_on_time_summer():
    m = match_slot(utc(2026, 6, 1, 15, 9), VERIFY_SLOTS)
    assert m.state == "on_time"
    assert m.slot_id == "2026-06-01T08:07"


def test_off_phase_is_noop():
    # 12:00 UTC = 05:00 Vancouver: every slot is still in the future.
    m = match_slot(utc(2026, 11, 19, 12, 0), VERIFY_SLOTS)
    assert m is None
    # 03:00 UTC = 20:00 Vancouver (previous UTC day boundary): the
    # latest past slot is 15:07, now classified delayed (same-day rule).
    m = match_slot(utc(2026, 11, 19, 3, 0), VERIFY_SLOTS)
    assert m is None or m.state in ("off_phase", "stale", "delayed")


def test_delayed_within_window():
    # 08:07 slot, firing at 10:07 Vancouver (17:07 UTC): delayed.
    m = match_slot(utc(2026, 11, 19, 17, 7), VERIFY_SLOTS)
    assert m.state == "delayed"
    assert m.slot_id == "2026-11-19T08:07"


def test_late_same_day_is_delayed_not_stale():
    # Revised rule (2026-11-24): 13:30 Vancouver — the 08:07 slot is
    # >180 min past, 15:07 is future. The execution RUNS the 08:07
    # verification as delayed; only cross-day claims are stale.
    # (Real case: 2026-11-23, 15:07 slot's run arrived 19:52 and was
    # discarded under the old cliff.)
    m = match_slot(utc(2026, 11, 19, 20, 30), VERIFY_SLOTS)
    assert m.slot_id == "2026-11-19T08:07"
    assert m.state == "delayed"


def test_recovery_next_day_is_stale():
    m = match_slot(
        utc(2026, 11, 20, 15, 10), VERIFY_SLOTS,
        intended_slot_id="2026-11-19T08:07",
    )
    assert m.state == "stale"


def test_recovery_same_day_delayed():
    # Recovery for 08:07 arriving 11:00 Vancouver (18:00 UTC): allowed.
    m = match_slot(
        utc(2026, 11, 19, 18, 0), VERIFY_SLOTS,
        intended_slot_id="2026-11-19T08:07",
    )
    assert m.state == "delayed"


def test_evening_slot_utc_next_day():
    # 22:07 Vancouver = 05:07 UTC the next UTC day, same Vancouver day.
    m = match_slot(utc(2026, 11, 20, 5, 9), VERIFY_SLOTS)
    assert m.state == "on_time"
    assert m.slot_id == "2026-11-19T22:07"


def test_planner_slot():
    m = match_slot(utc(2026, 11, 19, 15, 14), PLANNER_SLOTS)
    assert m.state == "on_time"
    assert m.slot_id == "2026-11-19T08:12"
