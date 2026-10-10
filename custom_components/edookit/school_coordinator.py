from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyedookit import EdookitClient, Payments, SchoolEvent

from .const import DOMAIN, SCHOOL_UPDATE_INTERVAL
from .data import EdookitConfigEntry
from .session_manager import EdookitSessionManager

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SchoolData:
    events: list[SchoolEvent]
    payments: Payments


class EdookitSchoolCoordinator(DataUpdateCoordinator[SchoolData]):
    config_entry: EdookitConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EdookitConfigEntry,
        session: EdookitSessionManager,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_school",
            update_interval=SCHOOL_UPDATE_INTERVAL,
        )
        self._session = session

    async def _async_update_data(self) -> SchoolData:
        events, payments = await asyncio.gather(
            self._session.async_call(EdookitClient.get_events),
            self._session.async_call(EdookitClient.get_payments),
        )
        return SchoolData(events=events, payments=payments)
