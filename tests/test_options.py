from __future__ import annotations

import os
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util
from pyedookit import CAPTURE_PAGES, Session
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.edookit.const import (
    CAPTURE_ENV,
    CONF_MESSAGES_ADMIN_ONLY,
    CONF_SCHOOL,
    CONF_SESSION,
    DOMAIN,
)
from tests.helpers import week

SESSION = Session.from_cookies("zs-example", edookit={"PHPSESSID": "s"}, plus4u={"uoid.ps": "p"})


async def _setup(
    hass: HomeAssistant, options: dict | None = None, *, capture: bool = False
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: SESSION.to_json()},
        options=options or {},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
        patch.dict(os.environ, {CAPTURE_ENV: "1"} if capture else {}),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def test_options_flow_offers_only_the_admin_option_and_saves(hass: HomeAssistant) -> None:
    entry = await _setup(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert [str(key) for key in result["data_schema"].schema] == [CONF_MESSAGES_ADMIN_ONLY]
    with patch(
        "pyedookit.client.EdookitClient.get_timetable_week",
        new=AsyncMock(return_value=week([])),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_MESSAGES_ADMIN_ONLY: True}
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_MESSAGES_ADMIN_ONLY: True}


# The second case is an option stored by versions before 0.8.0.
@pytest.mark.parametrize("options", [None, {"capture_pages": True}])
async def test_capture_is_off_without_the_dev_switch(
    hass: HomeAssistant, options: dict | None
) -> None:
    fetch_page = AsyncMock(return_value="<p/>")
    with patch("pyedookit.client.EdookitClient.fetch_page", new=fetch_page):
        await _setup(hass, options)

    fetch_page.assert_not_awaited()


async def test_capture_on_fetches_capture_pages(hass: HomeAssistant) -> None:
    # First run only records baselines, so no file is written to the config dir.
    fetch_page = AsyncMock(return_value="<p/>")
    with patch("pyedookit.client.EdookitClient.fetch_page", new=fetch_page):
        await _setup(hass, capture=True)

    assert {call.args[0] for call in fetch_page.await_args_list} == set(CAPTURE_PAGES)


async def test_session_refresh_does_not_reload_entry(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    refreshed = Session.from_cookies(
        "zs-example", edookit={"PHPSESSID": "refreshed"}, plus4u={"uoid.ps": "p"}
    )

    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload:
        # A real data change, like EdookitSessionManager makes after a refresh;
        # unchanged data would not fire the update listener at all.
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_SESSION: refreshed.to_json()}
        )
        await hass.async_block_till_done()

    reload.assert_not_awaited()


async def test_capture_runs_daily_outside_the_school_update(hass: HomeAssistant) -> None:
    fetch_page = AsyncMock(return_value="<p/>")
    with (
        patch("pyedookit.client.EdookitClient.fetch_page", new=fetch_page),
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
    ):
        await _setup(hass, capture=True)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert fetch_page.await_count == len(CAPTURE_PAGES)

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=3, minutes=1))
        await hass.async_block_till_done(wait_background_tasks=True)
        # the 3-hourly school update no longer captures
        assert fetch_page.await_count == len(CAPTURE_PAGES)

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1, minutes=1))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert fetch_page.await_count == 2 * len(CAPTURE_PAGES)


async def test_capture_auth_failure_leaves_school_data_alone(hass: HomeAssistant) -> None:
    fetch_page = AsyncMock(side_effect=ConfigEntryAuthFailed("expired"))
    with patch("pyedookit.client.EdookitClient.fetch_page", new=fetch_page):
        entry = await _setup(hass, capture=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data.school.last_update_success
    assert fetch_page.await_count == 1  # stops at the first auth failure


async def test_unload_cancels_the_capture_timer(hass: HomeAssistant) -> None:
    fetch_page = AsyncMock(return_value="<p/>")
    with (
        patch("pyedookit.client.EdookitClient.fetch_page", new=fetch_page),
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
    ):
        entry = await _setup(hass, capture=True)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert await hass.config_entries.async_unload(entry.entry_id)

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1, minutes=1))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert fetch_page.await_count == len(CAPTURE_PAGES)
