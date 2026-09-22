from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pyedookit import (
    PORTAL_TZ,
    EdookitConnectionError,
    PaymentRequest,
    Payments,
    SchoolEvent,
    Session,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN

SESSION = Session(
    school="zs-example",
    edookit_cookies={"PHPSESSID": "s"},
    plus4u_cookies={"uoid.ps": "p"},
    csrf_token="csrf",
)
EVENTS = [
    SchoolEvent(
        id="5001",
        title="Pasování na čtenáře",
        start=datetime(2026, 9, 23, 13, 30, tzinfo=PORTAL_TZ),
        end=datetime(2026, 9, 23, 15, 30, tzinfo=PORTAL_TZ),
        description="Družina",
    ),
    SchoolEvent(id="5003", title="Státní svátek", start=date(2026, 9, 28), end=date(2026, 9, 28)),
    SchoolEvent(
        id="5004", title="Vánoční prázdniny", start=date(2026, 12, 23), end=date(2027, 1, 3)
    ),
]
PAYMENTS = Payments(
    paid=Decimal(1400),
    remaining=Decimal(400),
    overpaid=Decimal(0),
    currency="CZK",
    requests=[
        PaymentRequest("Družina", Decimal(1400), "CZK", is_paid=True),
        PaymentRequest("Výlet do ZOO", Decimal(400), "CZK", is_paid=False),
    ],
)


async def _setup(hass: HomeAssistant, **patches: AsyncMock) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="zs-example:user@example.com",
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: SESSION.to_json()},
    )
    entry.add_to_hass(hass)
    with (
        patch("pyedookit.client.EdookitClient.get_timetable", new=AsyncMock(return_value=[])),
        patch(
            "pyedookit.client.EdookitClient.get_events",
            new=patches.get("get_events", AsyncMock(return_value=EVENTS)),
        ),
        patch(
            "pyedookit.client.EdookitClient.get_payments",
            new=patches.get("get_payments", AsyncMock(return_value=PAYMENTS)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_events_calendar_returns_events_in_range(hass: HomeAssistant) -> None:
    await _setup(hass)
    calendar = hass.data["calendar"].get_entity("calendar.edookit_zs_example_school_events")
    start = dt_util.start_of_local_day(date(2026, 9, 21))

    events = await calendar.async_get_events(hass, start, start + timedelta(days=8))

    assert [e.summary for e in events] == ["Pasování na čtenáře", "Státní svátek"]
    assert events[0].description == "Družina"
    assert (events[1].start, events[1].end) == (date(2026, 9, 28), date(2026, 9, 29))


async def test_multi_day_event_overlapping_the_range_is_included(hass: HomeAssistant) -> None:
    await _setup(hass)
    calendar = hass.data["calendar"].get_entity("calendar.edookit_zs_example_school_events")
    start = dt_util.start_of_local_day(date(2027, 1, 1))

    events = await calendar.async_get_events(hass, start, start + timedelta(days=1))

    assert [(e.summary, e.end) for e in events] == [("Vánoční prázdniny", date(2027, 1, 4))]


async def test_payments_due_sensor(hass: HomeAssistant) -> None:
    await _setup(hass)

    state = hass.states.get("sensor.edookit_zs_example_payments_due")

    assert state is not None
    assert float(state.state) == 400
    assert state.attributes["unit_of_measurement"] == "CZK"
    assert state.attributes["device_class"] == "monetary"
    assert state.attributes["paid"] == 1400
    assert state.attributes["unpaid_requests"] == [{"title": "Výlet do ZOO", "amount": 400.0}]


async def test_school_failure_leaves_timetable_working(hass: HomeAssistant) -> None:
    failing = AsyncMock(side_effect=EdookitConnectionError("down"))
    entry = await _setup(hass, get_events=failing, get_payments=failing)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.edookit_zs_example_lessons_today").state == "0"
    assert hass.states.get("sensor.edookit_zs_example_payments_due").state == "unavailable"
    assert hass.states.get("calendar.edookit_zs_example_school_events").state == "unavailable"
    calendar = hass.data["calendar"].get_entity("calendar.edookit_zs_example_school_events")
    start = dt_util.start_of_local_day(date(2026, 9, 21))
    assert await calendar.async_get_events(hass, start, start + timedelta(days=7)) == []
