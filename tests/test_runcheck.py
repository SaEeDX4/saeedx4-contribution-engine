"""Duplicate-execution window logic."""

from datetime import datetime, timezone

from verify.runcheck import prior_run_in_window


def utc(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


SLOT = utc(2026, 11, 19, 15, 7)  # 08:07 Vancouver in UTC


def run(rid, created, status="completed"):
    return {"id": rid, "created_at": created, "status": status}


def test_prior_run_found():
    runs = [run(42, "2026-11-19T15:08:00Z")]
    found = prior_run_in_window(runs, SLOT, utc(2026, 11, 19, 16, 7), "99")
    assert found["id"] == 42


def test_current_run_ignored():
    runs = [run(99, "2026-11-19T15:08:00Z")]
    assert prior_run_in_window(runs, SLOT, utc(2026, 11, 19, 16, 7), "99") is None


def test_incomplete_run_ignored():
    runs = [run(42, "2026-11-19T15:08:00Z", status="in_progress")]
    assert prior_run_in_window(runs, SLOT, utc(2026, 11, 19, 16, 7), "99") is None


def test_run_before_window_ignored():
    runs = [run(42, "2026-11-19T14:00:00Z")]  # previous slot's run
    assert prior_run_in_window(runs, SLOT, utc(2026, 11, 19, 16, 7), "99") is None
