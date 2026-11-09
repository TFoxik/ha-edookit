from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pyedookit import PORTAL_TZ, Homework, ParseError
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.diagnostics import async_get_config_entry_diagnostics
from tests.helpers import week
from tests.test_messages import SESSION, TIMETABLE

HOMEWORK = "sensor.edookit_zs_example_homework"


def hw(
    homework_id: int,
    due: datetime | None,
    progress: int | None = 0,
    done: bool = False,
    title: str = "Slovíčka 3",
) -> Homework:
    return Homework(
        id=homework_id,
        title=title,
        text="Naučit se slovíčka ze strany 14.",
        done=done,
        due=due,
        progress=progress,
        teacher="Učitelka A",
        created=datetime(2026, 11, 2, 9, 0, tzinfo=PORTAL_TZ),
        course_id=501,
        subject="Anglický jazyk",
        course_code="Aj 2 - I.B",
    )


def at(day: int, hour: int = 10) -> datetime:
    return datetime(2026, 11, day, hour, 0, tzinfo=PORTAL_TZ)


ITEMS = [
    hw(1, at(11)),
    hw(2, at(13), progress=100, done=True),
    hw(3, at(2)),
    hw(4, None),
]


@pytest.fixture(autouse=True)
def clock(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to("2026-11-06 12:00:00+01:00")
    return freezer


async def setup_entry(hass: HomeAssistant, get_homework: AsyncMock) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="zs-example:user@example.com",
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: SESSION.to_json()},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
        patch("pyedookit.client.EdookitClient.get_homework", new=get_homework),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_homework_sensor_counts_open_items_with_deadline_ahead(hass: HomeAssistant) -> None:
    await setup_entry(hass, AsyncMock(return_value=ITEMS))

    assert hass.states.get(HOMEWORK).state == "1"


async def test_homework_sensor_has_no_text_attributes(hass: HomeAssistant) -> None:
    await setup_entry(hass, AsyncMock(return_value=ITEMS))

    attributes = dict(hass.states.get(HOMEWORK).attributes)
    assert set(attributes) <= {"friendly_name", "icon", "state_class"}
    dumped = json.dumps(attributes)
    for text in ("Slovíčka", "Učitelka A", "Anglický jazyk", "strany 14"):
        assert text not in dumped


async def test_homework_parse_error_does_not_fail_setup(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, AsyncMock(side_effect=ParseError("no listing")))

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TIMETABLE).state != "unavailable"
    assert hass.states.get(HOMEWORK).state == "unavailable"


async def test_homework_refresh_every_three_hours(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    get_homework = AsyncMock(return_value=ITEMS)
    await setup_entry(hass, get_homework)
    with (
        patch("pyedookit.client.EdookitClient.get_homework", new=get_homework),
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
    ):
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert get_homework.await_count == 1

        freezer.tick(timedelta(hours=2, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert get_homework.await_count == 2


async def test_diagnostics_count_homework_only(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=ITEMS))

    data = await async_get_config_entry_diagnostics(hass, entry)

    assert (data["homework_count"], data["homework_open_count"]) == (4, 1)
    assert data["homework_last_update_success"] is True
    dumped = json.dumps(data, default=str)
    for text in ("Slovíčka", "Učitelka A", "Anglický jazyk", "strany 14"):
        assert text not in dumped
