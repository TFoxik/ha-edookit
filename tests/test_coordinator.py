from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from pyedookit import AuthError, Lesson, Session, SessionExpired
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.coordinator import EdookitCoordinator

SESSION = Session(
    school="zs-example",
    edookit_cookies={"PHPSESSID": "s"},
    plus4u_cookies={"uoid.ps": "p"},
    csrf_token="csrf",
)


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: SESSION.to_json()},
    )
    entry.add_to_hass(hass)
    return entry


async def test_expired_plus4u_session_raises_config_entry_auth_failed(hass: HomeAssistant) -> None:
    # Regression test: an AuthError raised while refreshing (e.g. the ~19-day
    # Plus4U cookie itself expired) must surface as ConfigEntryAuthFailed so
    # HA's reauth flow triggers - not escape as an unhandled exception. Before
    # the fix, this AuthError was raised from inside an `except SessionExpired`
    # block and never reached the sibling `except AuthError` around it.
    coordinator = EdookitCoordinator(hass, _entry(hass), SESSION)

    with (
        patch(
            "custom_components.edookit.coordinator.EdookitClient.get_timetable",
            new=AsyncMock(side_effect=SessionExpired("expired")),
        ),
        patch(
            "custom_components.edookit.coordinator.edookit_refresh",
            new=AsyncMock(side_effect=AuthError("Plus4U session expired; full login required")),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()


async def test_successful_refresh_retries_the_fetch(hass: HomeAssistant) -> None:
    lesson = Lesson(
        start=datetime(2026, 9, 21, 8, 0), end=datetime(2026, 9, 21, 8, 45), subject="Matematika"
    )
    refreshed_session = Session(
        school="zs-example",
        edookit_cookies={"PHPSESSID": "new"},
        plus4u_cookies={"uoid.ps": "p"},
        csrf_token="csrf2",
    )
    coordinator = EdookitCoordinator(hass, _entry(hass), SESSION)

    calls = 0

    async def flaky_get_timetable(self: object, week_offset: int) -> list[Lesson]:
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise SessionExpired("expired")
        return [lesson]

    with (
        patch(
            "custom_components.edookit.coordinator.EdookitClient.get_timetable",
            new=flaky_get_timetable,
        ),
        patch(
            "custom_components.edookit.coordinator.edookit_refresh",
            new=AsyncMock(return_value=refreshed_session),
        ),
    ):
        data = await coordinator._async_update_data()

    assert data.lessons == [lesson, lesson]
