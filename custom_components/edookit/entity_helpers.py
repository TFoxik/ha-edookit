from __future__ import annotations

from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pyedookit import Lesson


def localize(hass: HomeAssistant, naive: datetime) -> datetime:
    """Attach HA's configured timezone to a naive datetime parsed from portal HTML.

    Edookit renders wall-clock times with no timezone info, so this assumes
    the school and the Home Assistant instance share a timezone - true for
    the target audience (Czech schools) but worth noting if that changes.
    """
    tzinfo = dt_util.get_time_zone(hass.config.time_zone) or dt_util.DEFAULT_TIME_ZONE
    return naive.replace(tzinfo=tzinfo)


def lesson_summary(lesson: Lesson) -> str:
    if lesson.is_cancelled:
        return f"{lesson.subject} (zrušeno)"
    if lesson.is_changed:
        return f"{lesson.subject} (změna)"
    return lesson.subject


def lesson_description(lesson: Lesson) -> str | None:
    parts = []
    if lesson.teacher:
        parts.append(lesson.teacher)
    if lesson.group:
        parts.append(lesson.group)
    if lesson.note:
        parts.append(lesson.note)
    return " · ".join(parts) if parts else None
