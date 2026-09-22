from __future__ import annotations

from datetime import datetime

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from pyedookit import Lesson

from .const import CONF_SCHOOL, DOMAIN
from .coordinator import EdookitCoordinator
from .data import EdookitConfigEntry


class EdookitEntity(CoordinatorEntity[EdookitCoordinator]):
    """Common base for this integration's entities: one service device per
    config entry, and a unique_id and translation key taken from `key`."""

    _attr_has_entity_name = True
    key: str

    def __init__(self, coordinator: EdookitCoordinator, entry: EdookitConfigEntry) -> None:
        super().__init__(coordinator)
        school = entry.data[CONF_SCHOOL]
        self._attr_translation_key = self.key
        self._attr_unique_id = f"{entry.entry_id}_{self.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Edookit {school}",
            manufacturer="Edookit",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"https://{school}.edookit.net",
        )


def lesson_summary(lesson: Lesson) -> str:
    if lesson.is_cancelled:
        return f"{lesson.subject} (zrušeno)"
    if lesson.is_changed:
        return f"{lesson.subject} (změna)"
    return lesson.subject


def lesson_description(lesson: Lesson) -> str | None:
    parts = [p for p in (lesson.teacher, lesson.group, lesson.note) if p]
    return " · ".join(parts) if parts else None


def lesson_attributes(lesson: Lesson) -> dict[str, str | None]:
    """Fields common to the sensor's and event's lesson attribute payloads."""
    return {
        "start": dt_util.as_local(lesson.start).isoformat(),
        "room": lesson.room,
        "teacher": lesson.teacher,
    }


def next_lesson(
    lessons: list[Lesson], now: datetime, *, skip_cancelled: bool
) -> Lesson | None:
    candidates = [
        ls for ls in lessons if (not skip_cancelled or not ls.is_cancelled) and ls.end >= now
    ]
    return min(candidates, key=lambda ls: ls.start, default=None)
