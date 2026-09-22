from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from pyedookit import Lesson

from .coordinator import EdookitConfigEntry
from .entity_helpers import EdookitEntity, lesson_description, lesson_summary, next_lesson

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: EdookitConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([EdookitTimetableCalendar(entry.runtime_data, entry)])


class EdookitTimetableCalendar(EdookitEntity, CalendarEntity):
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
