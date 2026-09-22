from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from pyedookit import Lesson, SchoolEvent

from .coordinator import EdookitCoordinator
from .data import EdookitConfigEntry
from .entity_helpers import EdookitEntity, lesson_description, lesson_summary, next_lesson
from .school_coordinator import EdookitSchoolCoordinator, event_span

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


class EdookitSchoolEventsCalendar(EdookitEntity[EdookitSchoolCoordinator], CalendarEntity):
    key = "school_events"

    @staticmethod
    def _to_event(event: SchoolEvent) -> CalendarEvent:
        if event.all_day:
            return CalendarEvent(
                start=event.start,
                end=event.end + timedelta(days=1),
                summary=event.title,
                description=event.description,
                uid=event.id,
            )
        start, end = event_span(event)
        return CalendarEvent(
            start=start, end=end, summary=event.title, description=event.description, uid=event.id
        )

    @property
    def event(self) -> CalendarEvent | None:
        if self.coordinator.data is None:
            return None
        now = dt_util.now()
        upcoming = [e for e in self.coordinator.data.events if event_span(e)[1] > now]
        return self._to_event(upcoming[0]) if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        if self.coordinator.data is None:
            return []
        return [
            self._to_event(event)
            for event in self.coordinator.data.events
            if event_span(event)[1] > start_date and event_span(event)[0] < end_date
        ]
