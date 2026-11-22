from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyedookit import EdookitClient, Exam

from .const import DOMAIN, SCHOOL_UPDATE_INTERVAL
from .data import EdookitConfigEntry
from .session_manager import EdookitSessionManager

_LOGGER = logging.getLogger(__name__)


class EdookitExamsCoordinator(DataUpdateCoordinator[list[Exam]]):
    """The exams the portal lists: upcoming, today's and recent."""

    config_entry: EdookitConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: EdookitConfigEntry, session: EdookitSessionManager
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_exams",
            update_interval=SCHOOL_UPDATE_INTERVAL,
        )
        self._session = session

    async def _async_update_data(self) -> list[Exam]:
        return await self._session.async_call(EdookitClient.get_exams)
