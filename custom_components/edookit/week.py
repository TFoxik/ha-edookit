from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Any

from pyedookit import PORTAL_TZ, Lesson, Period, SchoolEvent


@dataclass(slots=True)
class WeekLessons:
    monday: date
    lessons: list[Lesson]
    periods: list[Period]


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def default_week(today: date) -> int:
    return 1 if today.weekday() >= 5 else 0


def derive_periods(lessons: list[Lesson]) -> list[Period]:
    slots = sorted({(ls.start.time(), ls.end.time()) for ls in lessons})
    return [Period(number, start, end) for number, (start, end) in enumerate(slots, start=1)]


def period_of(start: time, periods: list[Period]) -> int:
    for period in periods:
        if period.start <= start < period.end:
            return period.number

    def distance(period: Period) -> int:
        return abs(
            (start.hour * 60 + start.minute) - (period.start.hour * 60 + period.start.minute)
        )

    return min(periods, key=distance).number


def resolve_week(monday: date, known: list[WeekLessons]) -> tuple[WeekLessons | None, bool]:
    for week in known:
        if week.monday == monday:
            return week, False

    earlier = [week for week in known if week.monday < monday and week.lessons]
    if not earlier:
        return None, False

    source = max(earlier, key=lambda week: week.monday)
    shift = timedelta(weeks=(monday - source.monday).days // 7)
    lessons = [replace(ls, start=ls.start + shift, end=ls.end + shift) for ls in source.lessons]
    return WeekLessons(monday, lessons, source.periods), True


@dataclass(slots=True)
class _Slot:
    period: int
    lesson: Lesson


@dataclass(slots=True)
class _Occurrence:
    event: SchoolEvent
    start: datetime | None
    end: datetime | None
    slots: list[_Slot]


def _hhmm(value: datetime | time) -> str:
    local = value.astimezone(PORTAL_TZ).time() if isinstance(value, datetime) else value
    return local.strftime("%H:%M")


def _local_date(value: datetime) -> date:
    return value.astimezone(PORTAL_TZ).date()


def _slots(lessons: list[Lesson], periods: list[Period]) -> list[_Slot]:
    return [
        _Slot(period_of(ls.start.astimezone(PORTAL_TZ).time(), periods), ls)
        for ls in sorted(lessons, key=lambda ls: ls.start)
    ]


def _occurrences(day: date, events: list[SchoolEvent], slots: list[_Slot]) -> list[_Occurrence]:
    day_start = datetime.combine(day, time.min, tzinfo=PORTAL_TZ)
    day_end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=PORTAL_TZ)
    found = []
    for event in events:
        if isinstance(event.start, datetime) and isinstance(event.end, datetime):
            start, end = max(event.start, day_start), min(event.end, day_end)
            if start < end:
                hit = [s for s in slots if s.lesson.start < end and s.lesson.end > start]
                found.append(_Occurrence(event, start, end, hit))
        elif event.start <= day <= event.end:
            found.append(_Occurrence(event, None, None, list(slots)))
    found.sort(key=lambda o: (o.start is not None, o.start or day_start))
    return found


def _edge(occurrence: _Occurrence, day: date, periods: list[Period]) -> str | None:
    if occurrence.slots or occurrence.end is None:
        return None
    if periods and occurrence.end <= datetime.combine(day, periods[0].start, tzinfo=PORTAL_TZ):
        return "before"
    return "after"


def _lesson_payload(slot: _Slot, replaced_by: str | None) -> dict[str, Any]:
    lesson = slot.lesson
    return {
        "period": slot.period,
        "start": _hhmm(lesson.start),
        "end": _hhmm(lesson.end),
        "code": lesson.code,
        "subject": lesson.subject,
        "teacher": lesson.teacher,
        "room": lesson.room,
        "note": lesson.note,
        "changed": lesson.is_changed,
        "cancelled": lesson.is_cancelled,
        "replaced_by": replaced_by,
    }


def _event_payload(occurrence: _Occurrence, day: date, periods: list[Period]) -> dict[str, Any]:
    event, slots = occurrence.event, occurrence.slots
    numbers = [s.period for s in slots]
    return {
        "id": event.id,
        "title": event.title,
        "all_day": occurrence.start is None,
        "start": _hhmm(occurrence.start) if occurrence.start else None,
        "end": _hhmm(occurrence.end) if occurrence.end else None,
        "first_period": min(numbers, default=None),
        "last_period": max(numbers, default=None),
        "edge": _edge(occurrence, day, periods),
        "description": event.description,
        "created_by": event.created_by,
        "replaces": [
            {"period": s.period, "subject": s.lesson.subject}
            for s in sorted(slots, key=lambda s: s.period)
        ],
    }


def _day_payload(
    day: date, lessons: list[Lesson], periods: list[Period], events: list[SchoolEvent]
) -> dict[str, Any]:
    slots = _slots([ls for ls in lessons if _local_date(ls.start) == day], periods)
    occurrences = _occurrences(day, events, slots)
    replaced_by: dict[int, str] = {}
    for occurrence in occurrences:
        for slot in occurrence.slots:
            replaced_by.setdefault(id(slot), occurrence.event.id)
    return {
        "date": day.isoformat(),
        "lessons": [_lesson_payload(s, replaced_by.get(id(s))) for s in slots],
        "events": [_event_payload(o, day, periods) for o in occurrences],
    }


def _week_payload(
    monday: date, known: list[WeekLessons], events: list[SchoolEvent]
) -> dict[str, Any]:
    week, projected = resolve_week(monday, known)
    lessons = week.lessons if week else []
    periods = (week.periods or derive_periods(lessons)) if week else []
    if not periods:
        remembered = [w for w in known if w.periods]
        periods = max(remembered, key=lambda w: w.monday).periods if remembered else []
    return {
        "monday": monday.isoformat(),
        "loaded": week is not None,
        "projected": projected,
        "periods": [
            {"number": p.number, "start": _hhmm(p.start), "end": _hhmm(p.end)} for p in periods
        ],
        "days": [
            _day_payload(monday + timedelta(days=offset), lessons, periods, events)
            for offset in range(5)
        ],
    }


def build_payload(
    today: date, known: list[WeekLessons], events: list[SchoolEvent]
) -> dict[str, Any]:
    this_monday = monday_of(today)
    return {
        "today": today.isoformat(),
        "default_week": default_week(today),
        "weeks": [_week_payload(this_monday + timedelta(weeks=n), known, events) for n in (0, 1)],
    }
