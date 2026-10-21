from __future__ import annotations

import dataclasses
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyedookit import EdookitClient, MessageSummary

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .data import EdookitConfigEntry
from .session_manager import EdookitSessionManager

_LOGGER = logging.getLogger(__name__)


class EdookitMessagesCoordinator(DataUpdateCoordinator[list[MessageSummary]]):
    """The messages in Schránka. Only the list: a message's full text is
    fetched when someone opens it, because fetching it is expected to mark
    it read on the portal."""

    config_entry: EdookitConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: EdookitConfigEntry, session: EdookitSessionManager
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_messages",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self._session = session

    @property
    def session(self) -> EdookitSessionManager:
        return self._session

    async def _async_update_data(self) -> list[MessageSummary]:
        return await self._session.async_call(EdookitClient.get_inbox)

    @callback
    def async_mark_read(self, message_id: int) -> None:
        if self.data is None or not any(m.id == message_id for m in self.data):
            return
        self.async_set_updated_data(
            [dataclasses.replace(m, unread=False) if m.id == message_id else m for m in self.data]
        )
