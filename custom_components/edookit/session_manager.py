from __future__ import annotations

from collections.abc import Awaitable, Callable

import aiohttp
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
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
