from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pyedookit import PORTAL_TZ, EdookitConnectionError, Message
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from tests.helpers import week
from tests.test_messages import INBOX, UNREAD, setup_entry, summary

MESSAGE = Message(
    id=9003,
    subject="Předmět 9003",
    sender="Učitelka A",
    recipients="Rodič B",
    sent=datetime(2026, 10, 21, 8, 12, tzinfo=PORTAL_TZ),
    body=[{"tag": "p", "children": [{"text": "Vážení rodiče,"}]}],
    body_text="Vážení rodiče,",
)


@pytest.fixture(autouse=True)
def clock(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to("2026-10-21 12:00:00+02:00")
    return freezer


@pytest.fixture
def get_message() -> Any:
    mock = AsyncMock(return_value=MESSAGE)
    with patch("pyedookit.client.EdookitClient.get_message", new=mock):
        yield mock


async def _subscribe(ws: Any, msg_id: int = 1) -> dict[str, Any]:
    await ws.send_json({"id": msg_id, "type": "edookit/messages/subscribe", "entity_id": UNREAD})
    result = await ws.receive_json()
    assert result["success"] is True
    return (await ws.receive_json())["event"]


async def _get(ws: Any, message_id: int, msg_id: int = 2, entity_id: str = UNREAD) -> Any:
    await ws.send_json(
        {
            "id": msg_id,
            "type": "edookit/messages/get",
            "entity_id": entity_id,
            "message_id": message_id,
        }
    )
    return await ws.receive_json()


async def test_subscribe_pushes_the_list_and_unread_count(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await setup_entry(hass, AsyncMock(return_value=INBOX))
    ws = await hass_ws_client(hass)

    event = await _subscribe(ws)

    assert (event["unread"], event["available"], event["today"]) == (2, True, "2026-10-21")
    assert event["messages"][0] == {
        "id": 9003,
        "subject": "Předmět 9003",
        "sender": "Učitelka A",
        "sent": "2026-10-21T08:03:00+02:00",
        "preview": "Vážení rodiče…",
        "unread": True,
    }


async def test_subscribe_pushes_again_after_a_refresh(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    get_inbox = AsyncMock(return_value=INBOX)
    entry = await setup_entry(hass, get_inbox)
    ws = await hass_ws_client(hass)
    await _subscribe(ws)

    with patch(
        "pyedookit.client.EdookitClient.get_inbox",
        new=AsyncMock(return_value=[summary(9004, True), *INBOX]),
    ):
        await entry.runtime_data.messages.async_refresh()
        await hass.async_block_till_done()

    event = (await ws.receive_json())["event"]
    assert [m["id"] for m in event["messages"]] == [9004, 9003, 9002, 9001]
    assert event["unread"] == 3


async def test_subscribe_reports_an_unavailable_inbox(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await setup_entry(hass, AsyncMock(side_effect=EdookitConnectionError("down")))
    ws = await hass_ws_client(hass)

    event = await _subscribe(ws)

    assert event == {"messages": [], "unread": 0, "available": False, "today": "2026-10-21"}


async def test_subscribe_sends_unloaded_when_the_entry_unloads(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=INBOX))
    ws = await hass_ws_client(hass)
    await _subscribe(ws)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert (await ws.receive_json())["event"] == {"unloaded": True}


async def test_get_returns_the_message_and_marks_it_read(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, get_message: AsyncMock
) -> None:
    await setup_entry(hass, AsyncMock(return_value=INBOX))
    ws = await hass_ws_client(hass)
    await _subscribe(ws)

    replies = [await _get(ws, 9003), await ws.receive_json()]
    result = next(r for r in replies if r["type"] == "result")
    pushed = next(r for r in replies if r["type"] == "event")

    assert result["success"] is True
    assert result["result"] == {
        "id": 9003,
        "subject": "Předmět 9003",
        "sender": "Učitelka A",
        "recipients": "Rodič B",
        "sent": "2026-10-21T08:12:00+02:00",
        "body": [{"tag": "p", "children": [{"text": "Vážení rodiče,"}]}],
        "text": "Vážení rodiče,",
    }
    get_message.assert_awaited_once_with(9003)
    assert pushed["event"]["unread"] == 1
    assert hass.states.get(UNREAD).state == "1"


async def test_get_unknown_message_id_is_rejected_without_a_portal_request(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, get_message: AsyncMock
) -> None:
    await setup_entry(hass, AsyncMock(return_value=INBOX))
    ws = await hass_ws_client(hass)

    result = await _get(ws, 1234)

    assert result["success"] is False
    assert result["error"]["code"] == "not_found"
    get_message.assert_not_awaited()


async def test_get_with_unknown_entity_is_not_found(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, get_message: AsyncMock
) -> None:
    await setup_entry(hass, AsyncMock(return_value=INBOX))
    ws = await hass_ws_client(hass)

    result = await _get(ws, 9003, entity_id="sensor.nonexistent")

    assert result["error"]["code"] == "not_found"
    get_message.assert_not_awaited()


async def test_get_when_the_portal_fails_returns_an_error_and_keeps_unread(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, get_message: AsyncMock
) -> None:
    await setup_entry(hass, AsyncMock(return_value=INBOX))
    get_message.side_effect = EdookitConnectionError("down")
    ws = await hass_ws_client(hass)

    result = await _get(ws, 9003)

    assert result["success"] is False
    assert result["error"]["code"] == "portal_error"
    assert hass.states.get(UNREAD).state == "2"


async def test_subscribe_pushes_again_at_the_next_prague_midnight(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, clock: FrozenDateTimeFactory
) -> None:
    await setup_entry(hass, AsyncMock(return_value=INBOX))
    ws = await hass_ws_client(hass)
    await _subscribe(ws)

    with (
        patch("pyedookit.client.EdookitClient.get_inbox", new=AsyncMock(return_value=INBOX)),
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
    ):
        clock.move_to("2026-10-22 00:00:00+02:00")
        async_fire_time_changed(hass, datetime(2026, 10, 21, 22, 0, 1, tzinfo=dt_util.UTC))
        await hass.async_block_till_done()

    events = [(await ws.receive_json())["event"] for _ in range(2)]
    assert {e["today"] for e in events} == {"2026-10-22"}
    assert {e["unread"] for e in events} == {2}
