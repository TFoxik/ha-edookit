from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from pyedookit import Payments, SchoolEvent

from .const import DOMAIN, SCHOOL_UPDATE_INTERVAL
from .data import EdookitConfigEntry
from .session_manager import EdookitSessionManager

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SchoolData:
    events: list[SchoolEvent]
    payments: Payments


def event_span(event: SchoolEvent) -> tuple[datetime, datetime]:
    """Local start and exclusive end, so timed and all-day events compare."""
    if isinstance(event.start, datetime) and isinstance(event.end, datetime):
        return dt_util.as_local(event.start), dt_util.as_local(event.end)
    return (
        dt_util.start_of_local_day(event.start),
        dt_util.start_of_local_day(event.end + timedelta(days=1)),
    )


class EdookitSchoolCoordinator(DataUpdateCoordinator[SchoolData]):
    config_entry: EdookitConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: EdookitConfigEntry, session: EdookitSessionManager
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
        events = await self._session.async_call(lambda client: client.get_events())
        payments = await self._session.async_call(lambda client: client.get_payments())
        return SchoolData(events=sorted(events, key=lambda e: event_span(e)[0]), payments=payments)
