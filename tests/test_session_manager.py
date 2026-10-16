from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pyedookit import AuthError, EdookitConnectionError, ParseError, Session, SessionExpired
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.session_manager import EdookitSessionManager
from tests.helpers import week

HOST = "zs-example.edookit.net"


def _session(cookie: str) -> Session:
    return Session.from_cookies(
        "zs-example", edookit={"PHPSESSID": cookie}, plus4u={"uoid.ps": "p"}
    )


def _manager(
    hass: HomeAssistant, session: Session
) -> tuple[EdookitSessionManager, MockConfigEntry]:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_SCHOOL: "zs-example", CONF_SESSION: session.to_json()}
    )
    entry.add_to_hass(hass)
    return EdookitSessionManager(hass, entry, session, MagicMock()), entry


async def test_passes_the_client_to_the_fetch(hass: HomeAssistant) -> None:
    manager, _ = _manager(hass, _session("s"))

    async def fetch(client):
        return client.session.cookies.get(HOST, "PHPSESSID")

    assert await manager.async_call(fetch) == "s"


async def test_renewed_session_is_persisted(hass: HomeAssistant) -> None:
    manager, entry = _manager(hass, _session("old"))
    with (
        patch(
            "pyedookit.client.EdookitClient._fetch",
            new=AsyncMock(side_effect=[SessionExpired("x"), "<html/>"]),
        ),
        patch("pyedookit.auth.refresh", new=AsyncMock(return_value=_session("new"))),
    ):
        assert await manager.async_call(lambda c: c.fetch_page("assignments")) == "<html/>"

    stored = Session.from_json(entry.data[CONF_SESSION])
    assert stored.cookies.get(HOST, "PHPSESSID") == "new"


async def test_expired_plus4u_sign_in_starts_reauth(hass: HomeAssistant) -> None:
    manager, _ = _manager(hass, _session("old"))

    async def fetch(client):
        raise AuthError("expired")

    with pytest.raises(ConfigEntryAuthFailed):
        await manager.async_call(fetch)


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (SessionExpired("x"), "session_expired"),
        (EdookitConnectionError("x"), "cannot_connect"),
        (ParseError("x"), "parse_error"),
    ],
)
async def test_library_errors_become_translated_update_failed(
    hass: HomeAssistant, error: Exception, key: str
) -> None:
    manager, _ = _manager(hass, _session("s"))

    async def fetch(client):
        raise error

    with pytest.raises(UpdateFailed) as caught:
        await manager.async_call(fetch)
    assert caught.value.translation_key == key


async def test_entry_with_a_0_3_session_sets_up(hass: HomeAssistant) -> None:
    legacy = json.dumps(
        {
            "school": "zs-example",
            "edookit_cookies": {"PHPSESSID": "s"},
            "plus4u_cookies": {"uoid.ps": "p"},
            "csrf_token": "",
            "edookit_expires_at": "2026-10-10T14:07:34+00:00",
        }
    )
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_SCHOOL: "zs-example", CONF_SESSION: legacy})
    entry.add_to_hass(hass)
    with patch(
        "pyedookit.client.EdookitClient.get_timetable_week", new=AsyncMock(return_value=week([]))
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_each_entry_gets_its_own_cookieless_session(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_SCHOOL: "zs-example", CONF_SESSION: _session("s").to_json()}
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.edookit.async_create_clientsession") as create,
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert "auto_cleanup" not in create.call_args.kwargs  # HA's default: released on unload
    assert isinstance(create.call_args.kwargs["cookie_jar"], aiohttp.DummyCookieJar)
