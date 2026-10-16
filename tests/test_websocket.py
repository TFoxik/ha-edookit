from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util
from pyedookit import Session
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from tests.helpers import week
from tests.week_data import KAMARAD, VOLNO, this_week

TIMETABLE = "calendar.edookit_zs_example_timetable"
OTHER_TIMETABLE = "calendar.edookit_zs_other_timetable"


def _entry(school: str = "zs-example") -> MockConfigEntry:
    session = Session.from_cookies(school, edookit={"PHPSESSID": "s"}, plus4u={"uoid.ps": "p"})
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{school}:user@example.com",
        data={CONF_SCHOOL: school, CONF_SESSION: session.to_json()},
    )


@pytest.fixture(autouse=True)
def portal(freezer: FrozenDateTimeFactory) -> Any:
    freezer.move_to("2026-10-16 10:00:00+02:00")
    timetable = AsyncMock(return_value=week(this_week.lessons, this_week.periods))
    events = AsyncMock(return_value=[KAMARAD])
    with (
        patch("pyedookit.client.EdookitClient.get_timetable_week", new=timetable),
        patch("pyedookit.client.EdookitClient.get_events", new=events),
    ):
        yield type("Portal", (), {"timetable": timetable, "events": events})


async def _setup(hass: HomeAssistant, entry: MockConfigEntry | None = None) -> MockConfigEntry:
    entry = entry or _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _subscribe(ws: Any, entity_id: str, msg_id: int = 1) -> dict[str, Any]:
    await ws.send_json({"id": msg_id, "type": "edookit/week/subscribe", "entity_id": entity_id})
    result = await ws.receive_json()
    assert result["success"] is True
    return (await ws.receive_json())["event"]


async def _assert_silent(ws: Any) -> None:
    await ws.send_json({"id": 99, "type": "ping"})
    assert (await ws.receive_json())["type"] == "pong"


async def test_subscribe_sends_the_week_then_updates(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, portal: Any
) -> None:
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)

    first = await _subscribe(ws, TIMETABLE)
    assert first["today"] == "2026-10-16"
    assert first["weeks"][0]["days"][0]["lessons"][0]["code"] == "Čj"

    changed = replace(this_week.lessons[0], code="M", subject="Matematika")
    portal.timetable.return_value = week([changed, *this_week.lessons[1:]], this_week.periods)
    await entry.runtime_data.timetable.async_refresh()
    await hass.async_block_till_done()

    second = (await ws.receive_json())["event"]
    assert second["weeks"][0]["days"][0]["lessons"][0]["code"] == "M"


async def test_new_events_are_pushed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, portal: Any
) -> None:
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)
    first = await _subscribe(ws, TIMETABLE)
    assert [e["id"] for e in first["weeks"][0]["days"][3]["events"]] == ["e1"]

    portal.events.return_value = [KAMARAD, VOLNO]
    await entry.runtime_data.school.async_refresh()
    await hass.async_block_till_done()

    second = (await ws.receive_json())["event"]
    assert [e["id"] for e in second["weeks"][1]["days"][3]["events"]] == ["e2"]


async def test_unknown_entity_is_not_found(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await _setup(hass)
    ws = await hass_ws_client(hass)

    await ws.send_json(
        {"id": 1, "type": "edookit/week/subscribe", "entity_id": "calendar.nonexistent"}
    )
    msg = await ws.receive_json()
    assert msg["success"] is False
    assert msg["error"]["code"] == "not_found"


async def test_a_non_edookit_entity_is_not_found(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await _setup(hass)
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "calendar", "other", "x", config_entry=other, suggested_object_id="foreign"
    )
    ws = await hass_ws_client(hass)

    await ws.send_json({"id": 1, "type": "edookit/week/subscribe", "entity_id": "calendar.foreign"})
    msg = await ws.receive_json()
    assert msg["error"]["code"] == "not_found"


async def test_an_entry_that_is_not_loaded_is_not_found(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await _setup(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    ws = await hass_ws_client(hass)

    await ws.send_json({"id": 1, "type": "edookit/week/subscribe", "entity_id": TIMETABLE})
    msg = await ws.receive_json()
    assert msg["error"]["code"] == "not_found"


async def test_two_entries_each_get_their_own_week(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, portal: Any
) -> None:
    await _setup(hass)
    other_lessons = [replace(ls, code="Aj", subject="Anglický jazyk") for ls in this_week.lessons]
    portal.timetable.return_value = week(other_lessons, this_week.periods)
    await _setup(hass, _entry("zs-other"))
    ws = await hass_ws_client(hass)

    mine = await _subscribe(ws, TIMETABLE, 1)
    theirs = await _subscribe(ws, OTHER_TIMETABLE, 2)

    assert mine["weeks"][0]["days"][0]["lessons"][0]["code"] == "Čj"
    assert theirs["weeks"][0]["days"][0]["lessons"][0]["code"] == "Aj"


async def test_the_card_gets_a_push_at_the_next_prague_midnight(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    await _setup(hass)
    ws = await hass_ws_client(hass)
    with patch(
        "custom_components.edookit.websocket.async_track_point_in_utc_time",
        wraps=async_track_point_in_utc_time,
    ) as track:
        first = await _subscribe(ws, TIMETABLE)
        assert (first["today"], first["default_week"]) == ("2026-10-16", 0)

        freezer.move_to("2026-10-16 23:59:00+02:00")
        async_fire_time_changed(hass, datetime(2026, 10, 16, 21, 59, tzinfo=dt_util.UTC))
        await hass.async_block_till_done()
        await _assert_silent(ws)

        freezer.move_to("2026-10-17 00:00:00+02:00")
        async_fire_time_changed(hass, datetime(2026, 10, 16, 22, 0, 1, tzinfo=dt_util.UTC))
        await hass.async_block_till_done()
        saturday = (await ws.receive_json())["event"]
        assert (saturday["today"], saturday["default_week"]) == ("2026-10-17", 1)

        scheduled = [call.args[2] for call in track.call_args_list]
        assert scheduled == [
            datetime(2026, 10, 16, 22, 0, tzinfo=dt_util.UTC),
            datetime(2026, 10, 17, 22, 0, tzinfo=dt_util.UTC),
        ]


async def test_unsubscribing_stops_the_pushes(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)
    await _subscribe(ws, TIMETABLE)

    await ws.send_json({"id": 2, "type": "unsubscribe_events", "subscription": 1})
    assert (await ws.receive_json())["success"] is True

    entry.runtime_data.memory.observe_events([VOLNO], dt_util.now())
    freezer.move_to("2026-10-17 00:00:00+02:00")
    async_fire_time_changed(hass, datetime(2026, 10, 16, 22, 0, 1, tzinfo=dt_util.UTC))
    await hass.async_block_till_done()
    await _assert_silent(ws)


async def _midnight(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to("2026-10-17 00:00:00+02:00")
    async_fire_time_changed(hass, datetime(2026, 10, 16, 22, 0, 1, tzinfo=dt_util.UTC))
    await hass.async_block_till_done()


async def test_unloading_the_entry_ends_every_subscription_with_a_final_event(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)
    await _subscribe(ws, TIMETABLE, 1)
    await _subscribe(ws, TIMETABLE, 2)
    memory = entry.runtime_data.memory
    listeners_seen_by_a_later_callback: list[int] = []
    entry.async_on_state_change(
        lambda: listeners_seen_by_a_later_callback.append(len(memory._listeners))
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert listeners_seen_by_a_later_callback[0] == 0
    finals = [await ws.receive_json(), await ws.receive_json()]
    assert sorted((m["id"], m["type"], m["event"]) for m in finals) == [
        (1, "event", {"unloaded": True}),
        (2, "event", {"unloaded": True}),
    ]

    memory.observe_events([VOLNO], dt_util.now())
    await _midnight(hass, freezer)
    await _assert_silent(ws)
    assert memory._listeners == []

    await ws.close()
    await hass.async_block_till_done()


async def test_closing_the_socket_tears_the_subscription_down(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass)
    memory = entry.runtime_data.memory
    ws = await hass_ws_client(hass)
    timers: list[MagicMock] = []

    def track(*args: Any, **kwargs: Any) -> MagicMock:
        timers.append(MagicMock(wraps=async_track_point_in_utc_time(*args, **kwargs)))
        return timers[-1]

    with patch("custom_components.edookit.websocket.async_track_point_in_utc_time", track):
        await _subscribe(ws, TIMETABLE)
    assert len(memory._listeners) == 1

    await ws.close()
    await hass.async_block_till_done()

    assert memory._listeners == []
    timers[0].assert_called_once_with()
