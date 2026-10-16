from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, time, timedelta

from pyedookit import Lesson, Period


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
