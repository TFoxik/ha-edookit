from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pyedookit import Lesson, Session
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.diagnostics import async_get_config_entry_diagnostics

FAKE_SESSION = Session.from_cookies(
    "zs-example", edookit={"PHPSESSID": "s"}, plus4u={"uoid.ps": "p"}
)


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: FAKE_SESSION.to_json()},
    )
    entry.add_to_hass(hass)
    return entry


async def test_sensors_and_calendar_reflect_fetched_lessons(hass: HomeAssistant) -> None:
    now = dt_util.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    lessons = [
        Lesson(start=now, end=now + timedelta(minutes=45), subject="Matematika", room="12"),
    ]

    with patch(
        "pyedookit.client.EdookitClient.get_timetable",
        new=AsyncMock(return_value=lessons),
    ):
        entry = _entry(hass)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    next_lesson = hass.states.get("sensor.edookit_zs_example_next_lesson")
    assert next_lesson is not None
    assert next_lesson.state == "Matematika"
    assert next_lesson.attributes["room"] == "12"

    calendar = hass.states.get("calendar.edookit_zs_example_timetable")
    assert calendar is not None

    event_entity = hass.states.get("event.edookit_zs_example_timetable_changed")
    assert event_entity is not None

    lessons_today = hass.states.get("sensor.edookit_zs_example_lessons_today")
    assert lessons_today is not None

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None
    assert device.name == "Edookit zs-example"


async def _setup(hass: HomeAssistant, lessons: list[Lesson]) -> MockConfigEntry:
    entry = _entry(hass)
    with patch(
        "pyedookit.client.EdookitClient.get_timetable", new=AsyncMock(return_value=lessons)
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _lesson_in(hours: int, **kwargs: object) -> Lesson:
    start = dt_util.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=hours)
    return Lesson(start=start, end=start + timedelta(minutes=45), subject="Čeština", **kwargs)


async def test_calendar_returns_lessons_overlapping_the_requested_range(
    hass: HomeAssistant,
) -> None:
    lesson = _lesson_in(1, room="5")
    await _setup(hass, [lesson])
    calendar = hass.data["calendar"].get_entity("calendar.edookit_zs_example_timetable")

    inside = await calendar.async_get_events(
        hass, lesson.start + timedelta(minutes=10), lesson.end + timedelta(hours=1)
    )
    outside = await calendar.async_get_events(
        hass, lesson.end + timedelta(minutes=1), lesson.end + timedelta(hours=1)
    )

    assert [e.summary for e in inside] == ["Čeština"]
    assert inside[0].location == "5"
    assert outside == []


async def test_event_fires_once_per_newly_cancelled_lesson(hass: HomeAssistant) -> None:
    entry = await _setup(hass, [])
    cancelled = _lesson_in(2, is_cancelled=True)
    coordinator = entry.runtime_data.timetable

    with patch(
        "pyedookit.client.EdookitClient.get_timetable", new=AsyncMock(return_value=[cancelled])
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        first = hass.states.get("event.edookit_zs_example_timetable_changed")
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        second = hass.states.get("event.edookit_zs_example_timetable_changed")

    assert first is not None
    assert first.attributes["event_type"] == "lesson_cancelled"
    assert first.attributes["subject"] == "Čeština (zrušeno)"
    assert second is not None
    assert second.state == first.state


async def test_diagnostics_redact_the_session_and_school(hass: HomeAssistant) -> None:
    entry = await _setup(hass, [_lesson_in(1)])

    data = await async_get_config_entry_diagnostics(hass, entry)

    assert data["entry_data"][CONF_SESSION] == "**REDACTED**"
    assert data["entry_data"][CONF_SCHOOL] == "**REDACTED**"
    assert data["lesson_count"] == 1


async def test_unload_entry(hass: HomeAssistant) -> None:
    entry = await _setup(hass, [])

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
