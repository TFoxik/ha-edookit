from __future__ import annotations

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from pyedookit import PORTAL_TZ, Lesson, Period, Session
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.coordinator import EdookitCoordinator
from custom_components.edookit.session_manager import EdookitSessionManager
from tests.helpers import week

SESSION = Session.from_cookies("zs-example", edookit={"PHPSESSID": "s"}, plus4u={"uoid.ps": "p"})


def _coordinator(hass: HomeAssistant) -> EdookitCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_SCHOOL: "zs-example", CONF_SESSION: SESSION.to_json()}
    )
    entry.add_to_hass(hass)
    return EdookitCoordinator(hass, entry, EdookitSessionManager(hass, entry, SESSION, MagicMock()))


def _lesson(hour: int, *, cancelled: bool = False) -> Lesson:
    return Lesson(
        start=datetime(2026, 9, 21, hour, 0, tzinfo=PORTAL_TZ),
        end=datetime(2026, 9, 21, hour, 45, tzinfo=PORTAL_TZ),
        subject=f"S{hour}",
        is_cancelled=cancelled,
    )


async def test_lessons_are_sorted_and_disruptions_reported_once(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    lessons = [_lesson(10), _lesson(8, cancelled=True)]

    with patch(
        "pyedookit.client.EdookitClient.get_timetable_week",
        new=AsyncMock(return_value=week(lessons)),
    ):
        first = await coordinator._async_update_data()
        second = await coordinator._async_update_data()

    assert [ls.subject for ls in first.lessons] == ["S8", "S10"]
    assert [ls.subject for ls in first.newly_disrupted] == ["S8"]
    assert second.newly_disrupted == []


async def test_periods_from_the_page_reach_the_coordinator_data(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    periods = [Period(1, time(8, 0), time(8, 45))]

    with patch(
        "pyedookit.client.EdookitClient.get_timetable_week",
        new=AsyncMock(return_value=week([_lesson(8)], periods)),
    ):
        data = await coordinator._async_update_data()

    assert data.periods == periods
