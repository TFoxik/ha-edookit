from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pyedookit import PORTAL_TZ, Exam, ParseError
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.diagnostics import async_get_config_entry_diagnostics
from custom_components.edookit.entity_helpers import upcoming_exam_count
from tests.helpers import week
from tests.test_messages import SESSION, TIMETABLE

EXAMS = "sensor.edookit_zs_example_exams"


def at(day: int, hour: int = 8, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=PORTAL_TZ)


def exam(exam_id: int, start: datetime, minutes: int = 45) -> Exam:
    return Exam(
        id=exam_id,
        title="Zlomky",
        start=start,
        end=start + timedelta(minutes=minutes),
        subject="Matematika",
        course_code="M T - 1.A",
        course_id=9204,
        kind="Malá písemka",
        teacher="Učitelka A",
        announced=at(2, 10),
        description="Sčítání zlomků",
    )


ITEMS = [exam(1, at(9)), exam(2, at(12)), exam(3, at(20)), exam(4, at(5))]


@pytest.fixture(autouse=True)
def clock(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to("2026-11-06 12:00:00+01:00")
    return freezer


async def setup_entry(hass: HomeAssistant, get_exams: AsyncMock) -> MockConfigEntry:
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
        patch("pyedookit.client.EdookitClient.get_exams", new=get_exams),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_exams_sensor_counts_exams_in_the_next_seven_days(hass: HomeAssistant) -> None:
    await setup_entry(hass, AsyncMock(return_value=ITEMS))

    assert hass.states.get(EXAMS).state == "2"


def test_exam_in_progress_is_counted_until_it_ends() -> None:
    items = [exam(1, at(9, 8, 0))]
    assert upcoming_exam_count(items, at(9, 8, 20)) == 1
    assert upcoming_exam_count(items, at(9, 8, 45)) == 0


def test_exam_eight_days_ahead_is_not_counted() -> None:
    assert upcoming_exam_count([exam(1, at(14, 12))], at(6, 12)) == 0
    assert upcoming_exam_count([exam(1, at(13, 11))], at(6, 12)) == 1


def test_no_exam_data_has_no_count() -> None:
    assert upcoming_exam_count(None, at(6, 12)) is None


async def test_exams_sensor_has_no_item_attributes(hass: HomeAssistant) -> None:
    await setup_entry(hass, AsyncMock(return_value=ITEMS))

    attributes = dict(hass.states.get(EXAMS).attributes)
    assert set(attributes) <= {"friendly_name", "icon", "state_class"}
    dumped = json.dumps(attributes)
    for text in ("Zlomky", "Učitelka A", "Matematika", "Sčítání"):
        assert text not in dumped


async def test_exams_sensor_unavailable_when_fetch_fails(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, AsyncMock(side_effect=ParseError("no grids")))

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TIMETABLE).state != "unavailable"
    assert hass.states.get(EXAMS).state == "unavailable"


async def test_diagnostics_include_exam_counts_only(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=ITEMS))

    data = await async_get_config_entry_diagnostics(hass, entry)

    assert (data["exams_count"], data["exams_upcoming_count"]) == (4, 2)
    assert data["exams_last_update_success"] is True
    dumped = json.dumps(data, default=str)
    for text in ("Zlomky", "Učitelka A", "Matematika", "Sčítání"):
        assert text not in dumped


async def test_exams_sensor_drops_an_exam_when_it_ends_without_a_refresh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-09 08:20:00+01:00")
    await setup_entry(hass, AsyncMock(return_value=[exam(1, at(9))]))
    assert hass.states.get(EXAMS).state == "1"

    freezer.move_to("2026-11-09 08:45:01+01:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(EXAMS).state == "0"


async def test_exams_sensor_counts_an_exam_when_it_enters_the_window_without_a_refresh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    await setup_entry(hass, AsyncMock(return_value=[exam(1, at(13, 12, 20))]))
    assert hass.states.get(EXAMS).state == "0"

    freezer.move_to("2026-11-06 12:20:01+01:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(EXAMS).state == "1"
