from __future__ import annotations

from datetime import datetime
from pathlib import Path

import aiohttp
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from pyedookit import PORTAL_TZ, Session

from .capture import PageCapture
from .const import CAPTURE_DIR, CAPTURE_INTERVAL, CONF_CAPTURE_PAGES, CONF_SESSION, DOMAIN
from .coordinator import EdookitCoordinator
from .data import EdookitConfigEntry, EdookitRuntimeData
from .frontend_card import async_register_card
from .memory import WeekMemory
from .school_coordinator import EdookitSchoolCoordinator
from .session_manager import EdookitSessionManager
from .websocket import async_register_websocket

PLATFORMS = [Platform.CALENDAR, Platform.EVENT, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_register_websocket(hass)
    await async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> bool:
    # Cookieless because pyedookit sends cookies by hand per host. Created
    # during setup, so HA detaches it when this entry unloads.
    http = async_create_clientsession(hass, cookie_jar=aiohttp.DummyCookieJar())
    session = EdookitSessionManager(hass, entry, Session.from_json(entry.data[CONF_SESSION]), http)
    memory = WeekMemory(hass, entry.entry_id)
    await memory.async_load()
    timetable = EdookitCoordinator(hass, entry, session)
    await timetable.async_config_entry_first_refresh()
    school = EdookitSchoolCoordinator(hass, entry, session)
    # Not async_config_entry_first_refresh(): a broken events/payments page
    # must not keep the timetable from loading. Auth failures still start
    # reauth from inside async_refresh().
    await school.async_refresh()

    entry.runtime_data = EdookitRuntimeData(timetable=timetable, school=school, memory=memory)
    _feed_memory(entry, timetable, school, memory)
    if entry.options.get(CONF_CAPTURE_PAGES, False):
        _start_capture(hass, entry, session)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _feed_memory(
    entry: EdookitConfigEntry,
    timetable: EdookitCoordinator,
    school: EdookitSchoolCoordinator,
    memory: WeekMemory,
) -> None:
    @callback
    def _remember_lessons() -> None:
        if timetable.last_update_success and timetable.data is not None:
            today = dt_util.now().astimezone(PORTAL_TZ).date()
            memory.remember_lessons(timetable.data.lessons, timetable.data.periods, today)

    @callback
    def _observe_events() -> None:
        if school.last_update_success and school.data is not None:
            memory.observe_events(school.data.events, dt_util.now().astimezone(PORTAL_TZ))

    _remember_lessons()
    _observe_events()
    entry.async_on_unload(timetable.async_add_listener(_remember_lessons))
    entry.async_on_unload(school.async_add_listener(_observe_events))


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


async def async_remove_entry(hass: HomeAssistant, entry: EdookitConfigEntry) -> None:
    await WeekMemory(hass, entry.entry_id).async_remove()
