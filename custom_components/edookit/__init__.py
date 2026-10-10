from __future__ import annotations

from datetime import datetime
from pathlib import Path

import aiohttp
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_track_time_interval
from pyedookit import Session

from .capture import PageCapture
from .const import CAPTURE_DIR, CAPTURE_INTERVAL, CONF_CAPTURE_PAGES, CONF_SESSION, DOMAIN
from .coordinator import EdookitCoordinator
from .data import EdookitConfigEntry, EdookitRuntimeData
from .school_coordinator import EdookitSchoolCoordinator
from .session_manager import EdookitSessionManager

PLATFORMS = [Platform.CALENDAR, Platform.EVENT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> bool:
    # Cookieless because pyedookit sends cookies by hand per host. Created
    # during setup, so HA detaches it when this entry unloads.
    http = async_create_clientsession(hass, cookie_jar=aiohttp.DummyCookieJar())
    session = EdookitSessionManager(hass, entry, Session.from_json(entry.data[CONF_SESSION]), http)
    timetable = EdookitCoordinator(hass, entry, session)
    await timetable.async_config_entry_first_refresh()
    school = EdookitSchoolCoordinator(hass, entry, session)
    # Not async_config_entry_first_refresh(): a broken events/payments page
    # must not keep the timetable from loading. Auth failures still start
    # reauth from inside async_refresh().
    await school.async_refresh()

    entry.runtime_data = EdookitRuntimeData(timetable=timetable, school=school)
    if entry.options.get(CONF_CAPTURE_PAGES, False):
        _start_capture(hass, entry, session)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _start_capture(
    hass: HomeAssistant, entry: EdookitConfigEntry, session: EdookitSessionManager
) -> None:
    capture = PageCapture(hass, entry.entry_id, Path(hass.config.path(CAPTURE_DIR)))

    @callback
    def _run(_: datetime | None = None) -> None:
        entry.async_create_background_task(
            hass, capture.async_run(session), f"{DOMAIN} page capture"
        )

    _run()
    entry.async_on_unload(async_track_time_interval(hass, _run, CAPTURE_INTERVAL))


async def async_unload_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
