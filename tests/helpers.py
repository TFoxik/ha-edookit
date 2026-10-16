from __future__ import annotations

from pyedookit import Lesson, Period, TimetableWeek


def week(lessons: list[Lesson], periods: list[Period] | None = None) -> TimetableWeek:
    return TimetableWeek(lessons=lessons, periods=periods or [])
