from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pyedookit import Homework
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.edookit.homework_payload import homework_payload
from tests.test_homework import HOMEWORK, ITEMS, at, hw, setup_entry
from tests.test_messages import TIMETABLE


@pytest.fixture(autouse=True)
def clock(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to("2026-11-06 12:00:00+01:00")
    return freezer


def test_payload_shape_and_lesson_key() -> None:
    no_course = Homework(id=5, title="Projekt", text="Plakát", done=False)

    payload = homework_payload([hw(1, at(11)), no_course])

    assert payload["available"] is True
    assert payload["homework"] == [
        {
            "id": 1,
            "title": "Slovíčka 3",
            "text": "Naučit se slovíčka ze strany 14.",
            "subject": "Anglický jazyk",
            "short": "Aj",
            "code": "Aj 2",
            "group": "I.B",
            "teacher": "Učitelka A",
            "due": "2026-11-11T10:00:00+01:00",
            "done": False,
        },
        {
            "id": 5,
            "title": "Projekt",
            "text": "Plakát",
            "subject": None,
            "short": None,
            "code": None,
            "group": None,
            "teacher": None,
            "due": None,
            "done": False,
        },
    ]


def test_payload_group_is_null_without_a_separator() -> None:
    item = Homework(
        id=6, title="T", text="", done=False, course_code="Hv", subject="Hudební výchova"
    )

    entry = homework_payload([item])["homework"][0]

    assert (entry["short"], entry["code"], entry["group"]) == ("Hv", "Hv", None)


def test_payload_when_unavailable() -> None:
    assert homework_payload(None) == {"available": False, "homework": []}


async def _subscribe(ws: Any, entity_id: str = HOMEWORK) -> dict[str, Any]:
    await ws.send_json({"id": 1, "type": "edookit/homework/subscribe", "entity_id": entity_id})
    return await ws.receive_json()


async def test_subscribe_pushes_payload(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await setup_entry(hass, AsyncMock(return_value=ITEMS))
    ws = await hass_ws_client(hass)

    assert (await _subscribe(ws))["success"] is True
    event = (await ws.receive_json())["event"]

    assert event == homework_payload(ITEMS)


async def test_subscribe_with_the_timetable_entity(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await setup_entry(hass, AsyncMock(return_value=ITEMS))
    ws = await hass_ws_client(hass)

    assert (await _subscribe(ws, TIMETABLE))["success"] is True
    assert (await ws.receive_json())["event"] == homework_payload(ITEMS)


async def test_subscribe_pushes_again_after_refresh(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=ITEMS))
    ws = await hass_ws_client(hass)
    await _subscribe(ws)
    await ws.receive_json()

    newer = [hw(7, at(12)), *ITEMS]
    with patch("pyedookit.client.EdookitClient.get_homework", new=AsyncMock(return_value=newer)):
        await entry.runtime_data.homework.async_refresh()
        await hass.async_block_till_done()

    event = (await ws.receive_json())["event"]
    assert [h["id"] for h in event["homework"]] == [7, 1, 2, 3, 4]


async def test_subscribe_unknown_entity_is_not_found(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await setup_entry(hass, AsyncMock(return_value=ITEMS))
    ws = await hass_ws_client(hass)

    reply = await _subscribe(ws, "sensor.nothing_here")

    assert reply["success"] is False
    assert reply["error"]["code"] == "not_found"
