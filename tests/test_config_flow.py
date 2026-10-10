from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pyedookit import AuthError, EdookitConnectionError, Session
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN

FAKE_SESSION = Session.from_cookies(
    "zs-example", edookit={"PHPSESSID": "s"}, plus4u={"uoid.ps": "p"}
)
USER_INPUT = {"school": "zs-example", "username": "user@example.com", "password": "hunter2"}


def _patch_login(**kwargs: object):
    return patch("custom_components.edookit.config_flow.edookit_login", new=AsyncMock(**kwargs))


def _patch_timetable():
    return patch("pyedookit.client.EdookitClient.get_timetable", new=AsyncMock(return_value=[]))


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="zs-example:user@example.com",
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: FAKE_SESSION.to_json()},
    )
    entry.add_to_hass(hass)
    return entry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    with _patch_login(return_value=FAKE_SESSION), _patch_timetable():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCHOOL] == "zs-example"
    assert CONF_SESSION in result["data"]
    assert "password" not in result["data"]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AuthError("nope"), "invalid_auth"),
        (EdookitConnectionError("timeout"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors_then_recovers(
    hass: HomeAssistant, error: Exception, expected: str
) -> None:
    with _patch_login(side_effect=error):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    with _patch_login(return_value=FAKE_SESSION), _patch_timetable():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_aborts_when_already_configured(hass: HomeAssistant) -> None:
    _entry(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "school": " ZS-Example ", "username": "USER@example.com"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    entry = _entry(hass)

    with _patch_login(return_value=FAKE_SESSION), _patch_timetable():
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user@example.com", "password": "hunter3"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_SCHOOL] == "zs-example"


async def test_reauth_flow_rejects_a_different_account(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    login = AsyncMock(return_value=FAKE_SESSION)

    with patch("custom_components.edookit.config_flow.edookit_login", new=login):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "someone-else@example.com", "password": "x"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    login.assert_not_awaited()


async def test_flow_detaches_its_session_after_login(
    hass: HomeAssistant, mock_http_session: MagicMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_login(side_effect=AuthError("bad")):
        await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    mock_http_session.detach.assert_called_once()
