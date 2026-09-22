from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.hass_dict import HassKey
from pyedookit import (
    AuthError,
    EdookitClient,
    EdookitConnectionError,
    Lesson,
    ParseError,
    Session,
    SessionExpired,
)
from pyedookit import refresh as edookit_refresh

from .const import CONF_SESSION, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type EdookitConfigEntry = ConfigEntry[EdookitCoordinator]

_HTTP_SESSION: HassKey[aiohttp.ClientSession] = HassKey(f"{DOMAIN}_http_session")


@callback
def get_http_session(hass: HomeAssistant) -> aiohttp.ClientSession:
    """The integration's HA-managed session, which has no cookie jar.

    pyedookit sets Cookie headers by hand per host, so HA's default shared
    session is unsuitable: its jar would collect edookit/Plus4U cookies and
    resend them alongside the manual ones. Without a jar the session holds
    no per-account state, so every entry and config flow can share it.
    """
    if (http := hass.data.get(_HTTP_SESSION)) is None:
        http = hass.data[_HTTP_SESSION] = async_create_clientsession(
            hass, cookie_jar=aiohttp.DummyCookieJar()
        )
    return http


@dataclass(slots=True)
class EdookitData:
    # week_offset=1 ("next week") is not fetched: the portal accepts the
    # parameter but returns the same week's data back, so it can't be
    # trusted yet - see pyedookit's README for the open question. Only the
    # current week is fetched until that's sorted out.
    lessons: list[Lesson] = field(default_factory=list)
    # Lessons that became changed/cancelled since the previous poll - what
    # the event entity fires on, so a single automation trigger works for
    # substitutions and cancellations alike instead of a poll-diff per entity.
    newly_disrupted: list[Lesson] = field(default_factory=list)


def _disruption_key(lesson: Lesson) -> tuple[datetime, str]:
    return (lesson.start, lesson.subject)


class EdookitCoordinator(DataUpdateCoordinator[EdookitData]):
    config_entry: EdookitConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EdookitConfigEntry,
        session: Session,
        http: aiohttp.ClientSession,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self._http = http
        self._client = EdookitClient(session, http=http)
        self._previously_disrupted: set[tuple[datetime, str]] = set()

    async def _async_update_data(self) -> EdookitData:
        try:
            if self._client.session.is_edookit_expired:
                await self._refresh_or_reauth()
            try:
                return await self._fetch()
            except SessionExpired:
                await self._refresh_or_reauth()
                try:
                    return await self._fetch()
                except SessionExpired as err:
                    raise UpdateFailed(
                        translation_domain=DOMAIN, translation_key="session_expired"
                    ) from err
        except EdookitConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
        except ParseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="parse_error",
                translation_placeholders={"error": str(err)},
            ) from err

    async def _fetch(self) -> EdookitData:
        lessons = sorted(await self._client.get_timetable(week_offset=0), key=lambda ls: ls.start)

        disrupted_now = {
            _disruption_key(lesson)
            for lesson in lessons
            if lesson.is_changed or lesson.is_cancelled
        }
        new_keys = disrupted_now - self._previously_disrupted
        newly_disrupted = [lesson for lesson in lessons if _disruption_key(lesson) in new_keys]
        self._previously_disrupted = disrupted_now

        return EdookitData(lessons=lessons, newly_disrupted=newly_disrupted)

    async def _refresh_or_reauth(self) -> None:
        # AuthError raised in here must not be caught by a sibling
        # `except AuthError` around the caller's own try block - Python
        # doesn't propagate that way - so this is the one place that turns
        # it into ConfigEntryAuthFailed and triggers HA's reauth flow.
        try:
            await self._refresh_session()
        except AuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_expired"
            ) from err

    async def _refresh_session(self) -> None:
        new_session = await edookit_refresh(self._client.session, http=self._http)
        self._client = EdookitClient(new_session, http=self._http)
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_SESSION: new_session.to_json()},
        )
