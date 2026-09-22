from __future__ import annotations

from pathlib import Path

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pyedookit import Session

from .capture import PageCapture
from .const import CAPTURE_DIR, CONF_CAPTURE_PAGES, CONF_SESSION
from .coordinator import EdookitCoordinator
from .data import EdookitConfigEntry, EdookitRuntimeData
from .school_coordinator import EdookitSchoolCoordinator
from .session_manager import EdookitSessionManager, get_http_session

PLATFORMS = [Platform.CALENDAR, Platform.EVENT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> bool:
    session = EdookitSessionManager(
        hass, entry, Session.from_json(entry.data[CONF_SESSION]), get_http_session(hass)
    )
    timetable = EdookitCoordinator(hass, entry, session)
    await timetable.async_config_entry_first_refresh()
    capture_enabled = bool(entry.options.get(CONF_CAPTURE_PAGES, False))
    capture = (
        PageCapture(hass, entry.entry_id, Path(hass.config.path(CAPTURE_DIR)))
        if capture_enabled
        else None
    )
    school = EdookitSchoolCoordinator(hass, entry, session, capture)
    # Not async_config_entry_first_refresh(): a broken events/payments page
    # must not keep the timetable from loading. Auth failures still start
    # reauth from inside async_refresh().
    await school.async_refresh()

    entry.runtime_data = EdookitRuntimeData(
        session=session, timetable=timetable, school=school, capture_enabled=capture_enabled
    )
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_entry_updated(hass: HomeAssistant, entry: EdookitConfigEntry) -> None:
    # Session refreshes also update the entry (its data); only an options
    # change should reload.
    if bool(entry.options.get(CONF_CAPTURE_PAGES, False)) != entry.runtime_data.capture_enabled:
        await hass.config_entries.async_reload(entry.entry_id)
