from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pyedookit import Session

from .const import CONF_SESSION
from .coordinator import EdookitCoordinator
from .data import EdookitConfigEntry, EdookitRuntimeData
from .session_manager import EdookitSessionManager, get_http_session

PLATFORMS = [Platform.CALENDAR, Platform.EVENT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> bool:
    session = EdookitSessionManager(
        hass, entry, Session.from_json(entry.data[CONF_SESSION]), get_http_session(hass)
    )
    timetable = EdookitCoordinator(hass, entry, session)
    await timetable.async_config_entry_first_refresh()

    entry.runtime_data = EdookitRuntimeData(session=session, timetable=timetable)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
