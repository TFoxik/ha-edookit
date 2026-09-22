from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import EdookitConfigEntry
from .entity_helpers import EdookitEntity, lesson_attributes, next_lesson

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: EdookitConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            EdookitNextLessonSensor(coordinator, entry),
            EdookitLessonsTodaySensor(coordinator, entry),
        ]
    )


class EdookitNextLessonSensor(EdookitEntity, SensorEntity):
    key = "next_lesson"

    @property
    def native_value(self) -> str | None:
        lesson = next_lesson(self.coordinator.data.lessons, dt_util.now(), skip_cancelled=True)
        return lesson.subject if lesson else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        lesson = next_lesson(self.coordinator.data.lessons, dt_util.now(), skip_cancelled=True)
        if lesson is None:
            return {}
        return {**lesson_attributes(lesson), "end": dt_util.as_local(lesson.end).isoformat()}


class EdookitLessonsTodaySensor(EdookitEntity, SensorEntity):
    key = "lessons_today"
    _attr_native_unit_of_measurement = "lessons"

    @property
    def native_value(self) -> int:
        today = dt_util.now().date()
        return sum(
            1
            for ls in self.coordinator.data.lessons
            if not ls.is_cancelled and dt_util.as_local(ls.start).date() == today
        )
