from __future__ import annotations

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
    """A config entry's Edookit client, with errors in Home Assistant's terms.

    pyedookit renews the portal session itself; this persists each renewed
    session into the entry and maps library errors for the coordinators.
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
        self._client = EdookitClient(session, http=http, on_session_update=self._persist)

    @callback
    def _persist(self, session: Session) -> None:
        self._hass.config_entries.async_update_entry(
            self._entry, data={**self._entry.data, CONF_SESSION: session.to_json()}
        )

    async def async_call[T](self, fetch: Callable[[EdookitClient], Awaitable[T]]) -> T:
        try:
            return await fetch(self._client)
        except AuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_expired"
            ) from err
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
