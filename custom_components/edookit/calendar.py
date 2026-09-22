from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from pyedookit import Lesson, SchoolEvent

from .coordinator import EdookitCoordinator
from .data import EdookitConfigEntry
from .entity_helpers import EdookitEntity, lesson_description, lesson_summary, next_lesson
from .school_coordinator import EdookitSchoolCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: EdookitConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        [
            EdookitTimetableCalendar(runtime.timetable, entry),
            EdookitSchoolEventsCalendar(runtime.school, entry),
        ]
    )


class EdookitTimetableCalendar(EdookitEntity[EdookitCoordinator], CalendarEntity):
    key = "timetable"

    def _to_event(self, lesson: Lesson) -> CalendarEvent:
        return CalendarEvent(
            start=dt_util.as_local(lesson.start),
            end=dt_util.as_local(lesson.end),
            summary=lesson_summary(lesson),
            description=lesson_description(lesson),
            location=lesson.room,
        )

    @property
    def event(self) -> CalendarEvent | None:
        lesson = next_lesson(self.coordinator.data.lessons, dt_util.now(), skip_cancelled=False)
        return self._to_event(lesson) if lesson else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            self._to_event(lesson)
            for lesson in self.coordinator.data.lessons
            if lesson.end > start_date and lesson.start < end_date
        ]


def _to_calendar_event(event: SchoolEvent) -> CalendarEvent:
    start: datetime | date
    end: datetime | date
    if isinstance(event.start, datetime) and isinstance(event.end, datetime):
        start, end = dt_util.as_local(event.start), dt_util.as_local(event.end)
    else:
        # SchoolEvent's all-day end is the last day; HA's is exclusive.
        start, end = event.start, event.end + timedelta(days=1)
    return CalendarEvent(
        start=start, end=end, summary=event.title, description=event.description, uid=event.id
    )


class EdookitSchoolEventsCalendar(EdookitEntity[EdookitSchoolCoordinator], CalendarEntity):
    key = "school_events"

    @property
    def _events(self) -> list[CalendarEvent]:
        if self.coordinator.data is None:
            return []
        return sorted(
            (_to_calendar_event(e) for e in self.coordinator.data.events),
            key=lambda ce: ce.start_datetime_local,
        )

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next((ce for ce in self._events if ce.end_datetime_local > now), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            ce
            for ce in self._events
            if ce.end_datetime_local > start_date and ce.start_datetime_local < end_date
        ]
