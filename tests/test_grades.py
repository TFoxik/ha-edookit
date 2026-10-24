from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pyedookit import Grade, Grades, ParseError, Subject
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.diagnostics import async_get_config_entry_diagnostics
from tests.helpers import week
from tests.test_messages import SESSION, TIMETABLE

LATEST = "sensor.edookit_zs_example_latest_grade"


def grade(
    grade_id: int,
    mark: str,
    entered: date,
    course_id: int | None = 501,
    topic: str = "Test Unit 1",
    weight: float | None = 1.0,
) -> Grade:
    return Grade(
        id=grade_id,
        mark=mark,
        weight=weight,
        category="Obecné hodnocení",
        topic=topic,
        teacher="Učitelka A",
        entered=entered,
        course_id=course_id,
        subject="Anglický jazyk" if course_id == 501 else "Hudební výchova",
        course_code="Aj 2 - I.B" if course_id == 501 else "Hv - I.B",
    )


AJ = Subject(501, "Anglický jazyk", "Aj 2 - I.B", "Učitelka A, Mgr.", 100.0)
GRADES = Grades(
    "1. pololetí 26/27",
    [grade(9102, "1", date(2026, 10, 21)), grade(9101, "2", date(2026, 10, 19), 502, "Rytmus")],
    [AJ],
)


async def setup_entry(hass: HomeAssistant, get_grades: AsyncMock) -> MockConfigEntry:
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
        patch("pyedookit.client.EdookitClient.get_grades", new=get_grades),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_latest_grade_sensor_shows_newest_mark(hass: HomeAssistant) -> None:
    await setup_entry(hass, AsyncMock(return_value=GRADES))

    assert hass.states.get(LATEST).state == "1"


async def test_latest_grade_has_no_text_attributes(hass: HomeAssistant) -> None:
    await setup_entry(hass, AsyncMock(return_value=GRADES))

    attributes = dict(hass.states.get(LATEST).attributes)
    assert set(attributes) <= {"friendly_name", "icon"}
    dumped = json.dumps(attributes)
    for text in ("Test Unit 1", "Učitelka A", "Anglický jazyk"):
        assert text not in dumped


async def test_latest_grade_unknown_without_grades(hass: HomeAssistant) -> None:
    await setup_entry(hass, AsyncMock(return_value=Grades("1. pololetí 26/27", [], [AJ])))

    assert hass.states.get(LATEST).state == "unknown"


async def test_grades_parse_error_does_not_fail_setup(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, AsyncMock(side_effect=ParseError("no listing")))

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TIMETABLE).state != "unavailable"
    assert hass.states.get(LATEST).state == "unavailable"


async def test_grades_refresh_every_three_hours(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    get_grades = AsyncMock(return_value=GRADES)
    await setup_entry(hass, get_grades)
    with (
        patch("pyedookit.client.EdookitClient.get_grades", new=get_grades),
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
    ):
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert get_grades.await_count == 1

        freezer.tick(timedelta(hours=2, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert get_grades.await_count == 2


async def test_diagnostics_count_grades_only(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=GRADES))

    data = await async_get_config_entry_diagnostics(hass, entry)

    assert (data["grade_count"], data["subject_count"]) == (2, 1)
    assert data["grades_last_update_success"] is True
    assert "Test Unit 1" not in json.dumps(data, default=str)
