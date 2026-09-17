from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pyedookit import AuthError, Session

from custom_components.edookit.const import CONF_SCHOOL, DOMAIN

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
    assert "session" in result["data"]


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
