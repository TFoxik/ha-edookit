from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EdookitCoordinator
from .entity_helpers import EdookitEntity, lesson_attributes, lesson_summary


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EdookitCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EdookitTimetableChangedEvent(coordinator, entry)])


class EdookitTimetableChangedEvent(EdookitEntity, EventEntity):
    _attr_name = "Timetable changed"
    _unique_id_suffix = "timetable_changed"
    _attr_event_types = ["lesson_cancelled", "lesson_changed"]

    def _handle_coordinator_update(self) -> None:
        for lesson in self.coordinator.data.newly_disrupted:
            event_type = "lesson_cancelled" if lesson.is_cancelled else "lesson_changed"
            self._trigger_event(
                event_type, {"subject": lesson_summary(lesson), **lesson_attributes(lesson)}
            )
        super()._handle_coordinator_update()
