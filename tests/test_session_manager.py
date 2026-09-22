from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pyedookit import AuthError, EdookitConnectionError, ParseError, Session, SessionExpired
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.session_manager import EdookitSessionManager


def _session(cookie: str, *, expired: bool = False) -> Session:
    expires = datetime.now(UTC) + (timedelta(minutes=-1) if expired else timedelta(minutes=30))
    return Session(
        school="zs-example",
        edookit_cookies={"PHPSESSID": cookie},
        plus4u_cookies={"uoid.ps": "p"},
        csrf_token="csrf",
        edookit_expires_at=expires,
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

    cookie = await manager.async_call(
        lambda client: _async(client.session.edookit_cookies["PHPSESSID"])
    )

    assert cookie == "s"


async def test_expired_session_is_refreshed_and_persisted(hass: HomeAssistant) -> None:
    manager, entry = _manager(hass, _session("old", expired=True))

    with patch(
        "custom_components.edookit.session_manager.edookit_refresh",
        new=AsyncMock(return_value=_session("new")),
    ):
        cookie = await manager.async_call(
            lambda client: _async(client.session.edookit_cookies["PHPSESSID"])
        )

    assert cookie == "new"
    assert Session.from_json(entry.data[CONF_SESSION]).edookit_cookies == {"PHPSESSID": "new"}


async def test_session_expired_during_fetch_refreshes_and_retries(hass: HomeAssistant) -> None:
    manager, _ = _manager(hass, _session("old"))
    calls: list[str] = []

    async def fetch(client):
        calls.append(client.session.edookit_cookies["PHPSESSID"])
        if len(calls) == 1:
            raise SessionExpired("expired")
        return "ok"

    with patch(
        "custom_components.edookit.session_manager.edookit_refresh",
        new=AsyncMock(return_value=_session("new")),
    ):
        assert await manager.async_call(fetch) == "ok"

    assert calls == ["old", "new"]


async def test_concurrent_calls_refresh_once(hass: HomeAssistant) -> None:
    manager, _ = _manager(hass, _session("old", expired=True))

    async def slow_refresh(session, http):
        await asyncio.sleep(0)
        return _session("new")

    refresh = AsyncMock(side_effect=slow_refresh)
    with patch("custom_components.edookit.session_manager.edookit_refresh", new=refresh):
        results = await asyncio.gather(
            manager.async_call(lambda c: _async(c.session.edookit_cookies["PHPSESSID"])),
            manager.async_call(lambda c: _async(c.session.edookit_cookies["PHPSESSID"])),
        )

    assert results == ["new", "new"]
    assert refresh.await_count == 1


async def test_expired_plus4u_cookie_starts_reauth(hass: HomeAssistant) -> None:
    manager, _ = _manager(hass, _session("old", expired=True))

    with (
        patch(
            "custom_components.edookit.session_manager.edookit_refresh",
            new=AsyncMock(side_effect=AuthError("Plus4U session expired")),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await manager.async_call(lambda c: _async("unreachable"))


async def test_second_session_expired_becomes_update_failed(hass: HomeAssistant) -> None:
    manager, _ = _manager(hass, _session("old"))

    async def always_expired(client):
        raise SessionExpired("expired")

    with (
        patch(
            "custom_components.edookit.session_manager.edookit_refresh",
            new=AsyncMock(return_value=_session("new")),
        ),
        pytest.raises(UpdateFailed) as exc_info,
    ):
        await manager.async_call(always_expired)

    assert exc_info.value.translation_key == "session_expired"


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        (EdookitConnectionError("timeout"), "cannot_connect"),
        (ParseError("markup changed"), "parse_error"),
    ],
)
async def test_library_errors_become_translated_update_failed(
    hass: HomeAssistant, error: Exception, translation_key: str
) -> None:
    manager, _ = _manager(hass, _session("s"))

    async def failing(client):
        raise error

    with pytest.raises(UpdateFailed) as exc_info:
        await manager.async_call(failing)

    assert exc_info.value.translation_key == translation_key


async def _async(value):
    return value
