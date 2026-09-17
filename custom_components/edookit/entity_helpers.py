from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from pyedookit import Lesson

from .coordinator import EdookitCoordinator


class EdookitEntity(CoordinatorEntity[EdookitCoordinator]):
    """Common base for this integration's entities: entity-name mode plus a
    unique_id built from the config entry and a subclass-declared suffix."""

    _attr_has_entity_name = True
    _unique_id_suffix: str

    def __init__(self, coordinator: EdookitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{self._unique_id_suffix}"


def to_local(naive: datetime) -> datetime:
    """Attach HA's configured timezone to a naive datetime parsed from portal HTML.

    Edookit renders wall-clock times with no timezone info, so this assumes
    the school and the Home Assistant instance share a timezone - true for
    the target audience (Czech schools) but worth noting if that changes.
    `dt_util.as_local` attaches HA's configured zone directly to a naive
    value with no UTC conversion first, which is exactly that assumption.
    """
    return dt_util.as_local(naive)


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
        "start": to_local(lesson.start).isoformat(),
        "room": lesson.room,
        "teacher": lesson.teacher,
    }


def next_lesson(
    lessons: list[Lesson], now: datetime, *, skip_cancelled: bool
) -> Lesson | None:
    candidates = [
        ls
        for ls in lessons
        if (not skip_cancelled or not ls.is_cancelled) and to_local(ls.end) >= now
    ]
    return min(candidates, key=lambda ls: ls.start, default=None)
