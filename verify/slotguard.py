"""Slot guard: decides whether a workflow execution belongs to a real
verification slot in America/Vancouver, and how late it is.

Why this exists: GitHub's scheduled-workflow timing is best-effort and,
in this repository's observed evidence (Nov 16-17, 2026), the
``timezone:`` field on cron entries was not honoured — runs fired at
UTC-interpreted times with 10-45+ minute delays, and some slots never
fired at all. The defence is layered:

1. Workflows declare BOTH UTC phases of every Vancouver slot (PST and
   PDT), so a firing lands near the slot in either interpretation.
2. This guard runs first in every execution: it computes the current
   America/Vancouver time and classifies the execution against today's
   slots. Only an execution that matches a slot of the *current local
   day* may perform verification. Off-phase firings exit as no-ops;
   executions that arrive after the acceptance window, or for a
   previous day, are recorded as STALE and perform no work — work can
   never leak into a different local calendar day.
3. A watchdog workflow (watchdog.yml) checks, every 30 minutes,
   whether each of today's slots has produced a run; if a slot is
   overdue beyond tolerance and no run exists, it dispatches a
   recovery run carrying the slot id. The guard + a self-check for an
   already-completed run of the same slot make recovery idempotent.

Tolerances (owner directive 2026-11-18, revised 2026-11-24 with the
owner's "in the end it must work" instruction):
- ON_TIME:  started within 15 minutes after the slot.
- DELAYED:  started more than 15 minutes after the slot but still on
  the same local day: verification RUNS and the delay is recorded in
  the report. (The original 180-minute stale cliff was a design error:
  it conflated "late" with "wrong day". GitHub's scheduler provably
  delivers some runs hours late; a same-day verification still checks
  the same day's state, and duplicate suppression — not refusal — is
  the correct guard. Evidence: 2026-11-23, the 15:07 slot's only run
  arrived at 19:52 and was discarded unused.)
- STALE:    reserved for executions claiming a slot of a DIFFERENT
  local day (cross-day recovery dispatches). Those never execute.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Vancouver")

VERIFY_SLOTS: tuple[time, ...] = (time(8, 7), time(15, 7), time(22, 7))
PLANNER_SLOTS: tuple[time, ...] = (time(8, 12),)

ON_TIME_TOLERANCE = timedelta(minutes=15)
ACCEPTANCE_WINDOW = timedelta(minutes=180)
EARLY_TOLERANCE = timedelta(minutes=10)


@dataclass(frozen=True)
class SlotMatch:
    slot_id: str  # e.g. "2026-11-19T08:07"
    slot_at: datetime  # timezone-aware, America/Vancouver
    state: str  # "on_time" | "delayed" | "stale" | "off_phase"
    delay: timedelta


def slot_id_for(day: date, slot: time) -> str:
    return f"{day.isoformat()}T{slot.strftime('%H:%M')}"


def match_slot(
    now_utc: datetime,
    slots: tuple[time, ...],
    intended_slot_id: str | None = None,
) -> SlotMatch | None:
    """Classify an execution.

    ``intended_slot_id`` is set for watchdog recovery dispatches: the
    execution must belong to that exact slot of the *current* local
    day, otherwise it is stale (a recovery that arrives after local
    midnight must never execute the previous day's work).
    """
    now = now_utc.astimezone(TZ)
    today = now.date()

    if intended_slot_id:
        for slot in slots:
            if slot_id_for(today, slot) == intended_slot_id:
                slot_at = datetime.combine(today, slot, tzinfo=TZ)
                delay = now - slot_at
                if delay < -EARLY_TOLERANCE:
                    state = "off_phase"
                elif delay <= ON_TIME_TOLERANCE:
                    state = "on_time"
                elif delay <= timedelta(hours=24):
                    state = "delayed"
                else:
                    state = "stale"
                return SlotMatch(intended_slot_id, slot_at, state, delay)
        # Intended slot is not one of today's slots: it belongs to
        # another local day. Never execute it.
        return SlotMatch(intended_slot_id, now, "stale", timedelta(0))

    best: SlotMatch | None = None
    for slot in slots:
        slot_at = datetime.combine(today, slot, tzinfo=TZ)
        delay = now - slot_at
        sid = slot_id_for(today, slot)
        if -EARLY_TOLERANCE <= delay <= ON_TIME_TOLERANCE:
            state = "on_time"
        elif delay > ON_TIME_TOLERANCE:
            # Same local day, however late: the verification still
            # checks this day's state, so it runs as DELAYED with the
            # delay recorded. Slots are computed from today's date
            # only, so no work can leak into another day from here.
            state = "delayed"
        else:
            continue  # slot still in the future beyond early tolerance
        candidate = SlotMatch(sid, slot_at, state, delay)
        if best is None or slot_at > best.slot_at:
            best = candidate
    return best
