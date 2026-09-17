from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EdookitCoordinator
from .entity_helpers import EdookitEntity, lesson_attributes, next_lesson, to_local


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EdookitCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EdookitNextLessonSensor(coordinator, entry),
            EdookitLessonsTodaySensor(coordinator, entry),
        ]
    )


class EdookitNextLessonSensor(EdookitEntity, SensorEntity):
    _attr_name = "Next lesson"
    _unique_id_suffix = "next_lesson"

    @property
    def native_value(self) -> str | None:
        lesson = next_lesson(self.coordinator.data.lessons, dt_util.now(), skip_cancelled=True)
        return lesson.subject if lesson else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        lesson = next_lesson(self.coordinator.data.lessons, dt_util.now(), skip_cancelled=True)
        if lesson is None:
            return {}
        return {**lesson_attributes(lesson), "end": to_local(lesson.end).isoformat()}


class EdookitLessonsTodaySensor(EdookitEntity, SensorEntity):
    _attr_name = "Lessons today"
    _unique_id_suffix = "lessons_today"
    _attr_native_unit_of_measurement = "lessons"

    @property
    def native_value(self) -> int:
        today = dt_util.now().date()
        return sum(
            1
            for ls in self.coordinator.data.lessons
            if not ls.is_cancelled and ls.start.date() == today
        )
