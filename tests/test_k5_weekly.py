"""K5 — weekly randomization & push-limit validation.

Simulates 52 independently seeded weeks and checks the properties from
the owner's 2026-11-16 directive, section 6 (K5 items 1-12).
"""

import random
from datetime import date, datetime, timedelta

import pytest

from planner.accounting import AUTHORIZED_REPOS, CapExceeded, PushLedger
from planner.weekly import (
    KIND_SINGLE,
    KIND_STANDARD,
    KIND_THREE,
    PUSH_MIN_SEPARATION,
    TZ,
    load_or_create_week_plan,
    plan_week,
    week_monday,
)

FIRST_MONDAY = date(2026, 1, 5)  # a Monday
WEEKS = [FIRST_MONDAY + timedelta(days=7 * i) for i in range(52)]


def simulate():
    return [plan_week(m, rng=random.Random(10_000 + i)) for i, m in enumerate(WEEKS)]


def test_1_2_exactly_one_single_and_one_three_distinct():
    for plan in simulate():
        kinds = [d.kind for d in plan.days]
        assert kinds.count(KIND_SINGLE) == 1
        assert kinds.count(KIND_THREE) == 1
        assert plan.single_push_day.day != plan.three_push_day.day
        assert plan.single_push_day.push_cap == 1
        assert plan.three_push_day.push_cap == 3


def test_3_remaining_five_days_standard_3_to_10():
    for plan in simulate():
        standard = [d for d in plan.days if d.kind == KIND_STANDARD]
        assert len(standard) == 5
        for d in standard:
            assert 3 <= len(d.opportunity_times) <= 10
            assert d.push_times == ()


def test_4_special_weekdays_vary_independently():
    plans = simulate()
    singles = {p.single_push_day.day.weekday() for p in plans}
    threes = {p.three_push_day.day.weekday() for p in plans}
    # Over 52 uniform draws, seeing fewer than 5 distinct weekdays is
    # essentially impossible unless selection is broken or rotating.
    assert len(singles) >= 5
    assert len(threes) >= 5
    pairs = {(p.single_push_day.day.weekday(), p.three_push_day.day.weekday()) for p in plans}
    assert len(pairs) >= 20  # not a fixed rotation


def test_5_times_randomized_and_timezone_aware():
    for plan in simulate():
        for d in plan.days:
            for t in list(d.push_times) + list(d.opportunity_times):
                assert t.tzinfo is not None
                assert t.utcoffset() is not None
                assert t.date() == d.day  # inside the local calendar day
        three = plan.three_push_day.push_times
        for a, b in zip(three, three[1:]):
            assert b - a >= PUSH_MIN_SEPARATION


def test_6_11_plan_persistence_is_idempotent(tmp_path):
    monday = WEEKS[0]
    p1 = load_or_create_week_plan(monday, tmp_path, rng=random.Random(7))
    # A "restart" with a different RNG must return the stored plan.
    p2 = load_or_create_week_plan(monday, tmp_path, rng=random.Random(999))
    assert p1.to_dict() == p2.to_dict()


def test_7_8_combined_cap_and_retry_safety(tmp_path):
    plan = simulate()[0]
    ledger = PushLedger.load(tmp_path / "ledger.json")
    day = plan.single_push_day
    key = ledger.claim_push(
        week_id=plan.week_id, day=day.day, day_kind=KIND_SINGLE,
        slot_index=0, repo=AUTHORIZED_REPOS[0],
    )
    # Retry with the same key: allowed, still one claim.
    assert ledger.claim_push(
        week_id=plan.week_id, day=day.day, day_kind=KIND_SINGLE,
        slot_index=0, repo=AUTHORIZED_REPOS[1],
    ) == key
    ledger.record_push(key, commits=2, pull_request=False)
    assert ledger.pushes_on(day.day) == 1
    # A second, different slot on a Single Push Day exceeds the COMBINED
    # cap even when it targets the other repository.
    with pytest.raises(CapExceeded):
        ledger.claim_push(
            week_id=plan.week_id, day=day.day, day_kind=KIND_SINGLE,
            slot_index=1, repo=AUTHORIZED_REPOS[1],
        )
    # State survives a reload (restart / partial failure).
    reloaded = PushLedger.load(tmp_path / "ledger.json")
    assert reloaded.pushes_on(day.day) == 1


def test_9_merge_counts_as_push_and_metrics_are_separate(tmp_path):
    plan = simulate()[1]
    ledger = PushLedger.load(tmp_path / "ledger.json")
    day = plan.three_push_day
    for i in range(3):
        key = ledger.claim_push(
            week_id=plan.week_id, day=day.day, day_kind=KIND_THREE,
            slot_index=i, repo=AUTHORIZED_REPOS[i % 2],
        )
        # The third "push" is a PR merge carrying 4 commits.
        ledger.record_push(key, commits=4 if i == 2 else 1, pull_request=(i == 2))
    assert ledger.pushes_on(day.day) == 3
    assert ledger.metric("push") == 3
    assert ledger.metric("commit") == 6  # 1 + 1 + 4 commits != 3 pushes
    assert ledger.metric("pull_request") == 1
    assert ledger.metric("contribution") == 0  # never assumed from pushes
    with pytest.raises(CapExceeded):
        ledger.claim_push(
            week_id=plan.week_id, day=day.day, day_kind=KIND_THREE,
            slot_index=3, repo=AUTHORIZED_REPOS[0],
        )


def test_10_empty_backlog_is_honest_noop(tmp_path):
    plan = simulate()[2]
    ledger = PushLedger.load(tmp_path / "ledger.json")
    day = plan.single_push_day
    key = ledger.claim_push(
        week_id=plan.week_id, day=day.day, day_kind=KIND_SINGLE,
        slot_index=0, repo=AUTHORIZED_REPOS[0],
    )
    ledger.record_noop(key, reason="backlog empty")
    assert ledger.pushes_on(day.day) == 0
    assert ledger.metric("push") == 0


def test_unauthorized_repo_rejected(tmp_path):
    ledger = PushLedger.load(tmp_path / "ledger.json")
    with pytest.raises(ValueError):
        ledger.claim_push(
            week_id="2026-W02", day=date(2026, 1, 6), day_kind=KIND_SINGLE,
            slot_index=0, repo="interview-assistant-website",
        )


def test_week_boundaries_and_dst():
    # Weeks containing the 2026 DST transitions in America/Vancouver
    # (spring forward Mar 8, fall back Nov 1) still produce valid local
    # plans with all times inside their local days.
    for monday in (date(2026, 3, 2), date(2026, 10, 26)):
        plan = plan_week(monday, rng=random.Random(42))
        assert plan.monday == monday
        for d in plan.days:
            for t in list(d.push_times) + list(d.opportunity_times):
                assert t.date() == d.day
    assert week_monday(date(2026, 11, 16)) == date(2026, 11, 16)
    assert week_monday(date(2026, 11, 22)) == date(2026, 11, 16)
