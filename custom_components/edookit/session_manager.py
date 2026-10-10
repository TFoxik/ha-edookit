from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import aiohttp
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.hass_dict import HassKey
from pyedookit import (
    AuthError,
    EdookitClient,
    EdookitConnectionError,
    ParseError,
    Session,
    SessionExpired,
)
from pyedookit import refresh as edookit_refresh

from .const import CONF_SESSION, DOMAIN
from .data import EdookitConfigEntry

_HTTP_SESSION: HassKey[aiohttp.ClientSession] = HassKey(f"{DOMAIN}_http_session")


@callback
def get_http_session(hass: HomeAssistant) -> aiohttp.ClientSession:
    """The integration's HA-managed session, which has no cookie jar.

    pyedookit sets Cookie headers by hand per host, so HA's default shared
    session is unsuitable: its jar would collect edookit/Plus4U cookies and
    resend them alongside the manual ones. Without a jar the session holds
    no per-account state, so every entry and config flow can share it.

    It is created without HA's auto_cleanup, which would tie it to whichever
    entry happened to be setting up and release it when that one entry
    unloads; instead it is released once, on shutdown.
    """
    if (cached := hass.data.get(_HTTP_SESSION)) is not None:
        return cached
    http = hass.data[_HTTP_SESSION] = async_create_clientsession(
        hass, auto_cleanup=False, cookie_jar=aiohttp.DummyCookieJar()
    )

    @callback
    def _release(_: Event) -> None:
        http.detach()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _release)
    return http


class EdookitSessionManager:
    """The one edookit session of a config entry, shared by its coordinators.

    Both coordinators go through `async_call`, so an expired session is
    refreshed once (under a lock) and the result is visible to both.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EdookitConfigEntry,
        session: Session,
        http: aiohttp.ClientSession,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._http = http
        self._client = EdookitClient(session, http=http)
        self._refresh_lock = asyncio.Lock()

    async def async_call[T](self, fetch: Callable[[EdookitClient], Awaitable[T]]) -> T:
        try:
            client = self._client
            if client.session.is_edookit_expired:
                client = await self._refresh(client.session)
            try:
                return await fetch(client)
            except SessionExpired:
                client = await self._refresh(client.session)
            return await fetch(client)
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

    async def _refresh(self, stale: Session) -> EdookitClient:
        async with self._refresh_lock:
            if self._client.session is stale:
                try:
                    new_session = await edookit_refresh(stale, http=self._http)
                except AuthError as err:
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN, translation_key="auth_expired"
                    ) from err
                self._client = EdookitClient(new_session, http=self._http)
                self._hass.config_entries.async_update_entry(
                    self._entry,
                    data={**self._entry.data, CONF_SESSION: new_session.to_json()},
                )
            return self._client
