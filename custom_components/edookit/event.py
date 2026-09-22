from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import EdookitConfigEntry
from .entity_helpers import EdookitEntity, lesson_attributes, lesson_summary

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: EdookitConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([EdookitTimetableChangedEvent(entry.runtime_data.timetable, entry)])


class EdookitTimetableChangedEvent(EdookitEntity, EventEntity):
    key = "timetable_changed"
    _attr_event_types = ["lesson_cancelled", "lesson_changed"]

    def _handle_coordinator_update(self) -> None:
        for lesson in self.coordinator.data.newly_disrupted:
            event_type = "lesson_cancelled" if lesson.is_cancelled else "lesson_changed"
            self._trigger_event(
                event_type, {"subject": lesson_summary(lesson), **lesson_attributes(lesson)}
            )
        super()._handle_coordinator_update()
