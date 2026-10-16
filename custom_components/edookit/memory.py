from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from pyedookit import PORTAL_TZ, Lesson, Period, SchoolEvent

from .week import WeekLessons, derive_periods, monday_of

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SAVE_DELAY = 10


def _dump_dt(value: datetime) -> str:
    return value.isoformat()


def _load_dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(PORTAL_TZ)


def _dump_lesson(lesson: Lesson) -> dict[str, Any]:
    return {**asdict(lesson), "start": _dump_dt(lesson.start), "end": _dump_dt(lesson.end)}


def _load_lesson(data: dict[str, Any]) -> Lesson:
    return Lesson(**{**data, "start": _load_dt(data["start"]), "end": _load_dt(data["end"])})


def _dump_period(period: Period) -> dict[str, Any]:
    return {
        "number": period.number,
        "start": period.start.isoformat(),
        "end": period.end.isoformat(),
    }


def _load_period(data: dict[str, Any]) -> Period:
    return Period(
        data["number"], time.fromisoformat(data["start"]), time.fromisoformat(data["end"])
    )


def _dump_event(event: SchoolEvent) -> dict[str, Any]:
    return {
        **asdict(event),
        "all_day": event.all_day,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
    }


def _load_event(data: dict[str, Any]) -> SchoolEvent:
    if data["all_day"]:
        start: datetime | date = date.fromisoformat(data["start"])
        end: datetime | date = date.fromisoformat(data["end"])
    else:
        start, end = _load_dt(data["start"]), _load_dt(data["end"])
    return SchoolEvent(
        id=data["id"],
        title=data["title"],
        start=start,
        end=end,
        description=data["description"],
        created_by=data["created_by"],
    )


def _dump_week(week: WeekLessons) -> dict[str, Any]:
    return {
        "monday": week.monday.isoformat(),
        "lessons": [_dump_lesson(lesson) for lesson in week.lessons],
        "periods": [_dump_period(period) for period in week.periods],
    }


def _load_week(data: dict[str, Any]) -> WeekLessons:
    return WeekLessons(
        date.fromisoformat(data["monday"]),
        [_load_lesson(lesson) for lesson in data["lessons"]],
        [_load_period(period) for period in data["periods"]],
    )


def _started(event: SchoolEvent, now: datetime) -> bool:
    if isinstance(event.start, datetime):
        return event.start <= now
    return event.start <= now.astimezone(PORTAL_TZ).date()


def _ended_before(event: SchoolEvent, monday: date) -> bool:
    if isinstance(event.end, datetime):
        return event.end < datetime.combine(monday, time.min, tzinfo=PORTAL_TZ)
    return event.end < monday


class WeekMemory:
    """Weeks fetched and events seen so far, kept across polls and restarts.

    The portal only ever shows the current week and drops events after the
    fact, so the card's grid and its next-week projection need this.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"edookit.{entry_id}.week"
        )
        self._weeks: dict[date, WeekLessons] = {}
        self._events: dict[str, SchoolEvent] = {}
        self._listeners: list[Callable[[], None]] = []

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if not stored:
            return
        try:
            weeks = [_load_week(week) for week in stored["weeks"]]
            events = [_load_event(event) for event in stored["events"]]
        except KeyError, TypeError, ValueError:
            _LOGGER.warning("Ignoring unreadable remembered timetable", exc_info=True)
            return
        self._weeks = {week.monday: week for week in weeks}
        self._events = {event.id: event for event in events}

    def weeks(self) -> list[WeekLessons]:
        return sorted(self._weeks.values(), key=lambda week: week.monday)

    def events(self) -> list[SchoolEvent]:
        return list(self._events.values())

    def remember_lessons(self, lessons: list[Lesson], periods: list[Period], today: date) -> None:
        def mutate() -> None:
            by_monday: dict[date, list[Lesson]] = {}
            for lesson in lessons:
                monday = monday_of(lesson.start.astimezone(PORTAL_TZ).date())
                by_monday.setdefault(monday, []).append(lesson)
            for monday, week_lessons in by_monday.items():
                self._weeks[monday] = WeekLessons(
                    monday, week_lessons, periods or derive_periods(week_lessons)
                )
            oldest = monday_of(today) - timedelta(days=7)
            self._weeks = {m: w for m, w in self._weeks.items() if m >= oldest}

        self._change(mutate)

    def observe_events(self, events: list[SchoolEvent], now: datetime) -> None:
        def mutate() -> None:
            fed = {event.id: event for event in events}
            kept = {
                event_id: event
                for event_id, event in self._events.items()
                if event_id not in fed and _started(event, now)
            }
            monday = monday_of(now.astimezone(PORTAL_TZ).date())
            self._events = {
                event_id: event
                for event_id, event in {**kept, **fed}.items()
                if not _ended_before(event, monday)
            }

        self._change(mutate)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        @callback
        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _change(self, mutate: Callable[[], None]) -> None:
        before = (dict(self._weeks), dict(self._events))
        mutate()
        if (self._weeks, self._events) == before:
            return
        self._store.async_delay_save(self._serialise, SAVE_DELAY)
        for listener in list(self._listeners):
            listener()

    def _serialise(self) -> dict[str, Any]:
        return {
            "weeks": [_dump_week(week) for week in self.weeks()],
            "events": [_dump_event(event) for event in self._events.values()],
        }
