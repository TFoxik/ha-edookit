from __future__ import annotations

from datetime import date, datetime, time, timedelta

from pyedookit import PORTAL_TZ, Lesson, Period

from custom_components.edookit.week import WeekLessons

FIVE_PERIODS = [
    Period(1, time(8, 0), time(8, 45)),
    Period(2, time(8, 55), time(9, 40)),
    Period(3, time(10, 0), time(10, 45)),
    Period(4, time(10, 55), time(11, 40)),
    Period(5, time(11, 50), time(12, 35)),
]

SUBJECTS = {
    "Čj": "Český jazyk",
    "M": "Matematika",
    "Pč": "Pracovní činnosti",
    "Tv": "Tělesná výchova",
    "ČaS": "Člověk a jeho svět",
    "Hv": "Hudební výchova",
    "Aj": "Anglický jazyk",
    "Vv": "Výtvarná výchova",
}

MONDAY = date(2026, 10, 12)


def _lesson(
    day: date, period: int, code: str, room: str = "1.B", note: str | None = None
) -> Lesson:
    p = FIVE_PERIODS[period - 1]
    return Lesson(
        start=datetime.combine(day, p.start, tzinfo=PORTAL_TZ),
        end=datetime.combine(day, p.end, tzinfo=PORTAL_TZ),
        subject=SUBJECTS[code],
        teacher="Učitel A",
        room=room,
        note=note,
        code=code,
    )


def _build() -> WeekLessons:
    days = [
        [(1, "Čj"), (2, "M"), (3, "Čj"), (4, "Čj"), (5, "Pč")],
        [(1, "M"), (2, "Tv", "TV 2"), (3, "Čj"), (4, "ČaS")],
        [(1, "Čj"), (2, "Hv"), (3, "Aj"), (4, "Čj")],
        [(1, "Tv", "TV 1"), (2, "Čj"), (3, "M"), (4, "ČaS")],
        [(1, "Čj"), (2, "M"), (3, "Čj"), (4, "Vv")],
    ]
    lessons = [
        _lesson(MONDAY + timedelta(days=offset), *entry)
        for offset, day in enumerate(days)
        for entry in day
    ]
    lessons[0] = _lesson(MONDAY, 1, "Čj", note="Písmeno M")
    lessons.sort(key=lambda ls: ls.start)
    return WeekLessons(MONDAY, lessons, list(FIVE_PERIODS))


this_week = _build()
