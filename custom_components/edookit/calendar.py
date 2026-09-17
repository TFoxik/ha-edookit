from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from pyedookit import Lesson

from .const import DOMAIN
from .coordinator import EdookitCoordinator
from .entity_helpers import lesson_description, lesson_summary, localize


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EdookitCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EdookitTimetableCalendar(coordinator, entry)])


class EdookitTimetableCalendar(CoordinatorEntity[EdookitCoordinator], CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = "Timetable"

    def __init__(self, coordinator: EdookitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_timetable"

    def _to_event(self, lesson: Lesson) -> CalendarEvent:
        return CalendarEvent(
            start=localize(self.hass, lesson.start),
            end=localize(self.hass, lesson.end),
            summary=lesson_summary(lesson),
            description=lesson_description(lesson),
            location=lesson.room,
        )

    @property
    def _lessons(self) -> list[Lesson]:
        return self.coordinator.data.current_week + self.coordinator.data.next_week

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        upcoming = sorted(
            (ls for ls in self._lessons if localize(self.hass, ls.end) >= now),
            key=lambda ls: ls.start,
        )
        return self._to_event(upcoming[0]) if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            self._to_event(lesson)
            for lesson in self._lessons
            if start_date <= localize(hass, lesson.start) <= end_date
        ]
