from __future__ import annotations

import dataclasses
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pyedookit import EdookitConnectionError, Grades, Subject
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.edookit.grades_payload import grades_payload
from tests.helpers import week
from tests.test_grades import LATEST, grade, setup_entry

TODAY = date(2026, 10, 23)
SUBJECTS = [
    Subject(501, "Anglický jazyk", "Aj 2 - I.B", "Učitelka A, Mgr.", 100.0),
    Subject(502, "Hudební výchova", "Hv - I.B", "Učitel B", 90.0),
    Subject(503, "Matematika", "", "Učitelka A, Mgr.", None),
]
NO_SUBJECT = dataclasses.replace(
    grade(9099, "A", date(2026, 10, 16), weight=None),
    course_id=None,
    subject=None,
    course_code=None,
    category="Ostatní",
    topic="Výlet",
)
GRADES = Grades(
    "1. pololetí 26/27",
    [
        grade(9102, "1", date(2026, 10, 21)),
        grade(9101, "2", date(2026, 10, 19), 502, "Rytmus", 0.5),
        grade(9100, "3", date(2026, 10, 19), topic="Slovíčka", weight=2.0),
        NO_SUBJECT,
    ],
    SUBJECTS,
)


@pytest.fixture(autouse=True)
def clock(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to("2026-10-23 12:00:00+02:00")
    return freezer


def test_payload_grades_newest_first_with_short_names() -> None:
    payload = grades_payload(GRADES, TODAY)

    assert (payload["available"], payload["today"], payload["term"]) == (
        True,
        "2026-10-23",
        "1. pololetí 26/27",
    )
    assert payload["grades"][0] == {
        "id": 9102,
        "mark": "1",
        "value": 1,
        "weight": 1.0,
        "category": "Obecné hodnocení",
        "topic": "Test Unit 1",
        "teacher": "Učitelka A",
        "entered": "2026-10-21",
        "course_id": 501,
        "subject": "Anglický jazyk",
        "short": "Aj",
        "seen": False,
    }
    assert [g["short"] for g in payload["grades"]] == ["Aj", "Hv", "Aj", None]


def test_payload_subjects_with_marks_oldest_first_and_weighted_average() -> None:
    aj, hv, m = grades_payload(GRADES, TODAY)["subjects"]

    assert (aj["course_id"], aj["name"], aj["short"], aj["teacher"], aj["attendance"]) == (
        501,
        "Anglický jazyk",
        "Aj",
        "Učitelka A, Mgr.",
        100.0,
    )
    assert aj["marks"] == [{"mark": "3", "value": 3}, {"mark": "1", "value": 1}]
    assert aj["average"] == pytest.approx(7 / 3)
    assert (hv["short"], hv["average"]) == ("Hv", 2.0)
    assert (m["short"], m["marks"], m["average"], m["attendance"]) == ("Matematika", [], None, None)


def test_payload_when_unavailable() -> None:
    assert grades_payload(None, TODAY) == {
        "available": False,
        "today": "2026-10-23",
        "term": None,
        "grades": [],
        "subjects": [],
    }


async def _subscribe(ws: Any, entity_id: str = LATEST) -> dict[str, Any]:
    await ws.send_json({"id": 1, "type": "edookit/grades/subscribe", "entity_id": entity_id})
    return await ws.receive_json()


async def test_subscribe_pushes_the_payload(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await setup_entry(hass, AsyncMock(return_value=GRADES))
    ws = await hass_ws_client(hass)

    assert (await _subscribe(ws))["success"] is True
    event = (await ws.receive_json())["event"]

    assert event == grades_payload(GRADES, TODAY)


async def test_subscribe_pushes_again_after_a_refresh(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=GRADES))
    ws = await hass_ws_client(hass)
    await _subscribe(ws)
    await ws.receive_json()

    newer = Grades(GRADES.term, [grade(9103, "2", TODAY), *GRADES.grades], SUBJECTS)
    with patch("pyedookit.client.EdookitClient.get_grades", new=AsyncMock(return_value=newer)):
        await entry.runtime_data.grades.async_refresh()
        await hass.async_block_till_done()

    event = (await ws.receive_json())["event"]
    assert [g["id"] for g in event["grades"]] == [9103, 9102, 9101, 9100, 9099]


async def test_subscribe_reports_unavailable_grades(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await setup_entry(hass, AsyncMock(side_effect=EdookitConnectionError("down")))
    ws = await hass_ws_client(hass)
    await _subscribe(ws)

    assert (await ws.receive_json())["event"]["available"] is False


async def test_subscribe_unknown_entity_is_not_found(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await setup_entry(hass, AsyncMock(return_value=GRADES))
    ws = await hass_ws_client(hass)

    reply = await _subscribe(ws, "sensor.nothing_here")

    assert reply["success"] is False
    assert reply["error"]["code"] == "not_found"


def test_payload_marks_seen_grades() -> None:
    payload = grades_payload(GRADES, TODAY, frozenset({9102}))

    assert [g["seen"] for g in payload["grades"]] == [True, False, False, False]


async def _mark_seen(ws: Any, grade_id: int, msg_id: int = 2) -> dict[str, Any]:
    await ws.send_json(
        {"id": msg_id, "type": "edookit/grades/seen", "entity_id": LATEST, "grade_id": grade_id}
    )
    return await ws.receive_json()


def _seen_key(entry_id: str) -> str:
    return f"edookit.{entry_id}.grades_seen"


async def test_seen_is_pushed_to_every_subscriber_and_stored(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_storage: dict[str, Any]
) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=GRADES))
    other = await hass_ws_client(hass)
    await _subscribe(other)
    await other.receive_json()
    ws = await hass_ws_client(hass)

    reply = await _mark_seen(ws, 9102)

    assert reply["success"] is True
    event = (await other.receive_json())["event"]
    assert [g["seen"] for g in event["grades"]] == [True, False, False, False]
    assert hass_storage[_seen_key(entry.entry_id)]["data"] == [9102]


async def test_seen_survives_a_reload(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=GRADES))
    await _mark_seen(await hass_ws_client(hass), 9102)

    with (
        patch("pyedookit.client.EdookitClient.get_grades", new=AsyncMock(return_value=GRADES)),
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
    ):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    ws = await hass_ws_client(hass)
    await _subscribe(ws)

    assert (await ws.receive_json())["event"]["grades"][0]["seen"] is True


async def test_seen_rejects_an_unknown_grade(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_storage: dict[str, Any]
) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=GRADES))

    reply = await _mark_seen(await hass_ws_client(hass), 1)

    assert reply["success"] is False
    assert reply["error"]["code"] == "not_found"
    assert _seen_key(entry.entry_id) not in hass_storage


async def test_seen_forgets_grades_no_longer_listed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=GRADES))
    ws = await hass_ws_client(hass)
    await _mark_seen(ws, 9099)
    newer = Grades("2. pololetí 26/27", [grade(9300, "1", TODAY)], SUBJECTS)
    with patch("pyedookit.client.EdookitClient.get_grades", new=AsyncMock(return_value=newer)):
        await entry.runtime_data.grades.async_refresh()

    await _mark_seen(ws, 9300, msg_id=3)

    assert entry.runtime_data.grades.seen == frozenset({9300})


async def test_removing_the_entry_removes_the_seen_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_storage: dict[str, Any]
) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=GRADES))
    await _mark_seen(await hass_ws_client(hass), 9102)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert _seen_key(entry.entry_id) not in hass_storage
