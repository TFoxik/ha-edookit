from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyedookit import EdookitClient, Homework

from .const import DOMAIN, SCHOOL_UPDATE_INTERVAL
from .data import EdookitConfigEntry
from .session_manager import EdookitSessionManager

_LOGGER = logging.getLogger(__name__)


class EdookitHomeworkCoordinator(DataUpdateCoordinator[list[Homework]]):
    """The homework the portal lists, with done and overdue items included."""

    config_entry: EdookitConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: EdookitConfigEntry, session: EdookitSessionManager
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_homework",
            update_interval=SCHOOL_UPDATE_INTERVAL,
        )
        self._session = session

    async def _async_update_data(self) -> list[Homework]:
        return await self._session.async_call(EdookitClient.get_homework)
