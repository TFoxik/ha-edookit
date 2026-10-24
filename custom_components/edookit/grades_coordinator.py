from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyedookit import EdookitClient, Grades

from .const import DOMAIN, SCHOOL_UPDATE_INTERVAL
from .data import EdookitConfigEntry
from .session_manager import EdookitSessionManager

_LOGGER = logging.getLogger(__name__)
_SEEN_VERSION = 1


def _seen_store(hass: HomeAssistant, entry_id: str) -> Store[list[int]]:
    return Store(hass, _SEEN_VERSION, f"{DOMAIN}.{entry_id}.grades_seen")


async def async_remove_seen(hass: HomeAssistant, entry_id: str) -> None:
    await _seen_store(hass, entry_id).async_remove()


class EdookitGradesCoordinator(DataUpdateCoordinator[Grades]):
    """The current term's grades, and which of them someone has marked seen
    on a card: one list for the whole household, kept across restarts."""

    config_entry: EdookitConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: EdookitConfigEntry, session: EdookitSessionManager
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_grades",
            update_interval=SCHOOL_UPDATE_INTERVAL,
        )
        self._session = session
        self._seen_store = _seen_store(hass, entry.entry_id)
        self.seen: frozenset[int] = frozenset()

    async def async_load_seen(self) -> None:
        self.seen = frozenset(await self._seen_store.async_load() or [])

    async def async_mark_seen(self, grade_id: int) -> bool:
        """False when the grade isn't listed, so a card can't grow the store."""
        listed = {grade.id for grade in self.data.grades} if self.data else set()
        if grade_id not in listed:
            return False
        self.seen = frozenset((self.seen | {grade_id}) & listed)
        await self._seen_store.async_save(sorted(self.seen))
        self.async_update_listeners()
        return True

    async def _async_update_data(self) -> Grades:
        return await self._session.async_call(EdookitClient.get_grades)
