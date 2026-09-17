from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyedookit import AuthError, EdookitClient, Lesson, Session, SessionExpired
from pyedookit import refresh as edookit_refresh

from .const import CONF_SESSION, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EdookitData:
    current_week: list[Lesson] = field(default_factory=list)
    next_week: list[Lesson] = field(default_factory=list)
    # current_week + next_week, sorted by start - entities read this instead
    # of each re-concatenating and re-sorting the two lists themselves.
    lessons: list[Lesson] = field(default_factory=list)
    # Lessons that became changed/cancelled since the previous poll - what
    # the event entity fires on, so a single automation trigger works for
    # substitutions and cancellations alike instead of a poll-diff per entity.
    newly_disrupted: list[Lesson] = field(default_factory=list)


def _disruption_key(lesson: Lesson) -> tuple[datetime, str]:
    return (lesson.start, lesson.subject)


class EdookitCoordinator(DataUpdateCoordinator[EdookitData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, session: Session) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self._entry = entry
        self._client = EdookitClient(session)
        self._previously_disrupted: set[tuple[datetime, str]] = set()

    async def _async_update_data(self) -> EdookitData:
        if self._client.session.is_edookit_expired:
            await self._refresh_or_reauth()
        try:
            return await self._fetch()
        except SessionExpired:
            await self._refresh_or_reauth()
            try:
                return await self._fetch()
            except SessionExpired as err:
                raise UpdateFailed("edookit session expired again right after refresh") from err

    async def _fetch(self) -> EdookitData:
        current_week, next_week = await asyncio.gather(
            self._client.get_timetable(week_offset=0),
            self._client.get_timetable(week_offset=1),
        )
        all_lessons = sorted(current_week + next_week, key=lambda ls: ls.start)

        disrupted_now = {
            _disruption_key(lesson)
            for lesson in all_lessons
            if lesson.is_changed or lesson.is_cancelled
        }
        new_keys = disrupted_now - self._previously_disrupted
        newly_disrupted = [
            lesson for lesson in all_lessons if _disruption_key(lesson) in new_keys
        ]
        self._previously_disrupted = disrupted_now

        return EdookitData(
            current_week=current_week,
            next_week=next_week,
            lessons=all_lessons,
            newly_disrupted=newly_disrupted,
        )

    async def _refresh_or_reauth(self) -> None:
        # AuthError raised in here must not be caught by a sibling
        # `except AuthError` around the caller's own try block - Python
        # doesn't propagate that way - so this is the one place that turns
        # it into ConfigEntryAuthFailed and triggers HA's reauth flow.
        try:
            await self._refresh_session()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err

    async def _refresh_session(self) -> None:
        new_session = await edookit_refresh(self._client.session)
        self._client = EdookitClient(new_session)
        self.hass.config_entries.async_update_entry(
            self._entry, data={**self._entry.data, CONF_SESSION: new_session.to_json()}
        )
