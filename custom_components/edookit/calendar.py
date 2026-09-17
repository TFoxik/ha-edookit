from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from pyedookit import Lesson

from .const import DOMAIN
from .coordinator import EdookitCoordinator
from .entity_helpers import EdookitEntity, lesson_description, lesson_summary, next_lesson, to_local


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EdookitCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EdookitTimetableCalendar(coordinator, entry)])


class EdookitTimetableCalendar(EdookitEntity, CalendarEntity):
    _attr_name = "Timetable"
    _unique_id_suffix = "timetable"

    def _to_event(self, lesson: Lesson) -> CalendarEvent:
        return CalendarEvent(
            start=to_local(lesson.start),
            end=to_local(lesson.end),
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
            if start_date <= to_local(lesson.start) <= end_date
        ]
