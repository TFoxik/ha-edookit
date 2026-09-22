from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyedookit import Lesson

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .data import EdookitConfigEntry
from .session_manager import EdookitSessionManager

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EdookitData:
    # week_offset=1 ("next week") is not fetched: the portal accepts the
    # parameter but returns the same week's data back, so it can't be
    # trusted yet - see pyedookit's README for the open question. Only the
    # current week is fetched until that's sorted out.
    lessons: list[Lesson] = field(default_factory=list)
    # Lessons that became changed/cancelled since the previous poll - what
    # the event entity fires on, so a single automation trigger works for
    # substitutions and cancellations alike instead of a poll-diff per entity.
    newly_disrupted: list[Lesson] = field(default_factory=list)


def _disruption_key(lesson: Lesson) -> tuple[datetime, str]:
    return (lesson.start, lesson.subject)


class EdookitCoordinator(DataUpdateCoordinator[EdookitData]):
    config_entry: EdookitConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: EdookitConfigEntry, session: EdookitSessionManager
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self._session = session
        self._previously_disrupted: set[tuple[datetime, str]] = set()

    async def _async_update_data(self) -> EdookitData:
        lessons = sorted(
            await self._session.async_call(lambda client: client.get_timetable(week_offset=0)),
            key=lambda ls: ls.start,
        )

        disrupted_now = {
            _disruption_key(lesson)
            for lesson in lessons
            if lesson.is_changed or lesson.is_cancelled
        }
        new_keys = disrupted_now - self._previously_disrupted
        newly_disrupted = [lesson for lesson in lessons if _disruption_key(lesson) in new_keys]
        self._previously_disrupted = disrupted_now

        return EdookitData(lessons=lessons, newly_disrupted=newly_disrupted)
