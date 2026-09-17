from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pyedookit import AuthError, Session
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN

FAKE_SESSION = Session(
    school="zs-example",
    edookit_cookies={"PHPSESSID": "s"},
    plus4u_cookies={"uoid.ps": "p"},
    csrf_token="csrf",
)


async def test_user_flow_success(hass: HomeAssistant) -> None:
    with (
        patch(
            "custom_components.edookit.config_flow.edookit_login",
            new=AsyncMock(return_value=FAKE_SESSION),
        ),
        patch(
            "pyedookit.client.EdookitClient.get_timetable",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"school": "zs-example", "username": "user@example.com", "password": "hunter2"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCHOOL] == "zs-example"
    assert CONF_SESSION in result["data"]


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.edookit.config_flow.edookit_login",
        new=AsyncMock(side_effect=AuthError("nope")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"school": "zs-example", "username": "user@example.com", "password": "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="zs-example:old@example.com",
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: FAKE_SESSION.to_json()},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.edookit.config_flow.edookit_login",
            new=AsyncMock(return_value=FAKE_SESSION),
        ),
        patch(
            "pyedookit.client.EdookitClient.get_timetable",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "new@example.com", "password": "hunter3"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_SCHOOL] == "zs-example"
