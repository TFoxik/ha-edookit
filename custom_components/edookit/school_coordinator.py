from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyedookit import EdookitClient, Payments, SchoolEvent

from .capture import PageCapture
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
        capture: PageCapture | None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_school",
            update_interval=SCHOOL_UPDATE_INTERVAL,
        )
        self._session = session
        self._capture = capture

    async def _async_update_data(self) -> SchoolData:
        events = await self._session.async_call(EdookitClient.get_events)
        payments = await self._session.async_call(EdookitClient.get_payments)
        if self._capture is not None:
            await self._capture.async_run(self._session)
        return SchoolData(events=events, payments=payments)
