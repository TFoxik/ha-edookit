from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from pyedookit import Lesson

from .const import DOMAIN
from .coordinator import EdookitCoordinator
from .entity_helpers import localize


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


class _EdookitSensorBase(CoordinatorEntity[EdookitCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EdookitCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    def _lessons(self) -> list[Lesson]:
        return self.coordinator.data.current_week + self.coordinator.data.next_week


class EdookitNextLessonSensor(_EdookitSensorBase):
    _attr_name = "Next lesson"

    def __init__(self, coordinator: EdookitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "next_lesson")

    def _next(self) -> Lesson | None:
        now = dt_util.now()
        upcoming = sorted(
            (
                ls
                for ls in self._lessons()
                if not ls.is_cancelled and localize(self.hass, ls.end) >= now
            ),
            key=lambda ls: ls.start,
        )
        return upcoming[0] if upcoming else None

    @property
    def native_value(self) -> str | None:
        lesson = self._next()
        return lesson.subject if lesson else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        lesson = self._next()
        if lesson is None:
            return {}
        return {
            "start": localize(self.hass, lesson.start).isoformat(),
            "end": localize(self.hass, lesson.end).isoformat(),
            "room": lesson.room,
            "teacher": lesson.teacher,
        }


class EdookitLessonsTodaySensor(_EdookitSensorBase):
    _attr_name = "Lessons today"
    _attr_native_unit_of_measurement = "lessons"

    def __init__(self, coordinator: EdookitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "lessons_today")

    @property
    def native_value(self) -> int:
        today = dt_util.now().date()
        return sum(
            1
            for ls in self._lessons()
            if not ls.is_cancelled and ls.start.date() == today
        )
