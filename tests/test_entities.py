from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pyedookit import Lesson, Session
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN

FAKE_SESSION = Session(
    school="zs-example",
    edookit_cookies={"PHPSESSID": "s"},
    plus4u_cookies={"uoid.ps": "p"},
    csrf_token="csrf",
)


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: FAKE_SESSION.to_json()},
    )
    entry.add_to_hass(hass)
    return entry


async def test_sensors_and_calendar_reflect_fetched_lessons(hass: HomeAssistant) -> None:
    # Lesson.start/end are naive wall-clock times as the portal parser would
    # produce them - here, built in the same timezone entity_helpers.to_local()
    # will reattach (hass.config.time_zone), not this machine's local zone.
    now = (
        dt_util.now().replace(minute=0, second=0, microsecond=0, tzinfo=None)
        + timedelta(hours=1)
    )
    lessons = [
        Lesson(start=now, end=now + timedelta(minutes=45), subject="Matematika", room="12"),
    ]

    with patch(
        "pyedookit.client.EdookitClient.get_timetable",
        new=AsyncMock(return_value=lessons),
    ):
        _entry(hass)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    next_lesson = hass.states.get("sensor.next_lesson")
    assert next_lesson is not None
    assert next_lesson.state == "Matematika"
    assert next_lesson.attributes["room"] == "12"

    calendar = hass.states.get("calendar.timetable")
    assert calendar is not None

    event_entity = hass.states.get("event.timetable_changed")
    assert event_entity is not None
