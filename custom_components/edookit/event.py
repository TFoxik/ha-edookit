from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EdookitCoordinator
from .entity_helpers import lesson_summary


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EdookitCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EdookitTimetableChangedEvent(coordinator, entry)])


class EdookitTimetableChangedEvent(CoordinatorEntity[EdookitCoordinator], EventEntity):
    _attr_has_entity_name = True
    _attr_name = "Timetable changed"
    _attr_event_types = ["lesson_cancelled", "lesson_changed"]

    def __init__(self, coordinator: EdookitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_timetable_changed"

    def _handle_coordinator_update(self) -> None:
        for lesson in self.coordinator.data.newly_disrupted:
            event_type = "lesson_cancelled" if lesson.is_cancelled else "lesson_changed"
            self._trigger_event(
                event_type,
                {
                    "subject": lesson_summary(lesson),
                    "start": lesson.start.isoformat(),
                    "room": lesson.room,
                    "teacher": lesson.teacher,
                },
            )
        super()._handle_coordinator_update()
