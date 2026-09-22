from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pyedookit import Session
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_CAPTURE_PAGES, CONF_SCHOOL, CONF_SESSION, DOMAIN

SESSION = Session(
    school="zs-example",
    edookit_cookies={"PHPSESSID": "s"},
    plus4u_cookies={"uoid.ps": "p"},
    csrf_token="csrf",
)


async def _setup(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: SESSION.to_json()},
        options=options or {},
    )
    entry.add_to_hass(hass)
    with patch("pyedookit.client.EdookitClient.get_timetable", new=AsyncMock(return_value=[])):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_options_flow_defaults_to_off_and_saves(hass: HomeAssistant) -> None:
    entry = await _setup(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    with (
        patch("pyedookit.client.EdookitClient.get_timetable", new=AsyncMock(return_value=[])),
        patch("pyedookit.client.EdookitClient.fetch_page", new=AsyncMock(return_value="<p/>")),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_CAPTURE_PAGES: True}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_CAPTURE_PAGES: True}
    assert entry.runtime_data.capture_enabled is True


async def test_capture_off_fetches_no_extra_pages(hass: HomeAssistant) -> None:
    fetch_page = AsyncMock(return_value="<p/>")
    with patch("pyedookit.client.EdookitClient.fetch_page", new=fetch_page):
        await _setup(hass)

    fetch_page.assert_not_awaited()


async def test_capture_on_fetches_capture_pages(hass: HomeAssistant) -> None:
    # First run only records baselines, so no file is written to the config dir.
    fetch_page = AsyncMock(return_value="<p/>")
    with patch("pyedookit.client.EdookitClient.fetch_page", new=fetch_page):
        await _setup(hass, {CONF_CAPTURE_PAGES: True})

    assert {call.args[0] for call in fetch_page.await_args_list} == {
        "assignments",
        "exams",
        "inbox",
        "consents",
    }


async def test_session_refresh_does_not_reload_entry(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    refreshed = Session(
        school="zs-example",
        edookit_cookies={"PHPSESSID": "refreshed"},
        plus4u_cookies={"uoid.ps": "p"},
        csrf_token="csrf2",
    )

    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload:
        # A real data change, like EdookitSessionManager makes after a refresh;
        # unchanged data would not fire the update listener at all.
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_SESSION: refreshed.to_json()}
        )
        await hass.async_block_till_done()

    reload.assert_not_awaited()
