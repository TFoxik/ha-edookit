from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pyedookit import Exam
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.edookit.exams_payload import exams_payload
from tests.test_exams import EXAMS, ITEMS, at, exam, setup_entry
from tests.test_messages import TIMETABLE


@pytest.fixture(autouse=True)
def clock(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to("2026-11-06 12:00:00+01:00")
    return freezer


def test_exams_payload_fields() -> None:
    bare = Exam(id=5, title="Opakování", start=at(10), end=at(10, 8, 45))

    payload = exams_payload([exam(1, at(9)), bare])

    assert payload["available"] is True
    assert payload["exams"] == [
        {
            "id": 1,
            "title": "Zlomky",
            "subject": "Matematika",
            "short": "M",
            "code": "M T",
            "group": "1.A",
            "teacher": "Učitelka A",
            "kind": "Malá písemka",
            "start": "2026-11-09T08:00:00+01:00",
            "end": "2026-11-09T08:45:00+01:00",
        },
        {
            "id": 5,
            "title": "Opakování",
            "subject": None,
            "short": None,
            "code": None,
            "group": None,
            "teacher": None,
            "kind": None,
            "start": "2026-11-10T08:00:00+01:00",
            "end": "2026-11-10T08:45:00+01:00",
        },
    ]


def test_exams_payload_unavailable() -> None:
    assert exams_payload(None) == {"available": False, "exams": []}


async def _subscribe(ws: Any, entity_id: str = EXAMS) -> dict[str, Any]:
    await ws.send_json({"id": 1, "type": "edookit/exams/subscribe", "entity_id": entity_id})
    return await ws.receive_json()


async def test_subscribe_sends_current_exams_then_updates(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=ITEMS))
    ws = await hass_ws_client(hass)

    assert (await _subscribe(ws, TIMETABLE))["success"] is True
    assert (await ws.receive_json())["event"] == exams_payload(ITEMS)

    newer = [exam(7, at(10)), *ITEMS]
    with patch("pyedookit.client.EdookitClient.get_exams", new=AsyncMock(return_value=newer)):
        await entry.runtime_data.exams.async_refresh()
        await hass.async_block_till_done()

    event = (await ws.receive_json())["event"]
    assert [e["id"] for e in event["exams"]] == [7, 1, 2, 3, 4]
