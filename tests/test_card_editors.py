from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

HARNESS_JS = Path(__file__).parent / "editor_harness.js"

TIMETABLE = "calendar.edookit_x_timetable"
UNREAD = "sensor.edookit_x_unread_messages"
LATEST = "sensor.edookit_x_latest_grade"
ENTITIES = [
    {"entity_id": TIMETABLE, "platform": "edookit", "translation_key": "timetable"},
    {"entity_id": "calendar.renamed", "platform": "edookit", "translation_key": "timetable"},
    {"entity_id": UNREAD, "platform": "edookit", "translation_key": "unread_messages"},
    {"entity_id": LATEST, "platform": "edookit", "translation_key": "latest_grade"},
    {
        "entity_id": "sensor.edookit_x_next_lesson",
        "platform": "edookit",
        "translation_key": "next_lesson",
    },
    {"entity_id": "calendar.other_timetable", "platform": "other", "translation_key": "timetable"},
]


def _edit(
    card: str,
    config: dict[str, Any],
    change: dict[str, Any] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    stdin = json.dumps(
        {
            "card": card,
            "config": config,
            "change": change,
            "language": language,
            "entities": ENTITIES,
        }
    )
    result = subprocess.run(
        [node, str(HARNESS_JS)], input=stdin, capture_output=True, text=True, check=True, timeout=20
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("card", ["timetable", "messages", "grades"])
def test_card_offers_its_visual_editor(card: str) -> None:
    assert _edit(card, {"entity": "x"})["editorTag"] == f"edookit-{card}-card-editor"


def test_timetable_editor_shows_defaults_for_options_left_out() -> None:
    shown = _edit("timetable", {"type": "custom:edookit-timetable-card", "entity": TIMETABLE})
    assert shown["data"] == {
        "type": "custom:edookit-timetable-card",
        "entity": TIMETABLE,
        "style": "classic",
        "show_header": True,
        "show_periods": True,
        "show_days": True,
        "show_room": True,
    }
    assert shown["fields"] == [
        "entity",
        "title",
        "style",
        "language",
        "show_header",
        "show_periods",
        "show_days",
        "show_room",
    ]


def test_messages_editor_shows_defaults_for_options_left_out() -> None:
    shown = _edit("messages", {"entity": UNREAD, "compact": True})
    assert shown["data"] == {
        "entity": UNREAD,
        "style": "classic",
        "open": "inline",
        "max_messages": 5,
        "unread_only": False,
        "show_preview": True,
        "compact": True,
        "show_header": True,
    }


def test_timetable_editor_lists_only_edookit_timetables() -> None:
    assert _edit("timetable", {"entity": ""})["entities"] == [TIMETABLE, "calendar.renamed"]


def test_messages_editor_lists_only_unread_message_sensors() -> None:
    assert _edit("messages", {"entity": ""})["entities"] == [UNREAD]


def test_editor_keeps_a_configured_entity_outside_the_list() -> None:
    entity = "sensor.edookit_x_next_lesson"
    assert _edit("timetable", {"entity": entity})["entities"] == [
        TIMETABLE,
        "calendar.renamed",
        entity,
    ]


def test_editor_writes_only_what_differs_from_the_defaults() -> None:
    config = {"type": "custom:edookit-timetable-card", "entity": TIMETABLE}
    shown = _edit("timetable", config, change={"show_room": False})
    assert shown["changed"] == {**config, "show_room": False}
    assert list(shown["changed"]) == ["type", "entity", "show_room"]


def test_editor_drops_an_option_set_back_to_its_default() -> None:
    config = {"entity": UNREAD, "max_messages": 8, "language": "cs"}
    shown = _edit("messages", config, change={"max_messages": 5, "language": None})
    assert shown["changed"] == {"entity": UNREAD}


@pytest.mark.parametrize(
    ("language", "label"), [("cs", "Jen nepřečtené"), ("en", "Unread only"), ("de", "Unread only")]
)
def test_editor_labels_follow_the_user_language(language: str, label: str) -> None:
    assert (
        _edit("messages", {"entity": UNREAD}, language=language)["labels"]["unread_only"] == label
    )


def test_grades_editor_shows_defaults_for_options_left_out() -> None:
    shown = _edit("grades", {"entity": LATEST})

    assert shown["data"] == {"entity": LATEST, "view": "combined", "max_grades": 5}
    assert shown["fields"] == ["entity", "view", "max_grades", "language"]


def test_grades_editor_lists_only_latest_grade_sensors() -> None:
    assert _edit("grades", {"entity": ""})["entities"] == [LATEST]


def test_grades_editor_drops_defaults() -> None:
    shown = _edit(
        "grades", {"entity": LATEST, "view": "latest"}, change={"view": "combined", "max_grades": 3}
    )

    assert shown["changed"] == {"entity": LATEST, "max_grades": 3}


@pytest.mark.parametrize(("language", "label"), [("cs", "Zobrazení"), ("en", "View")])
def test_grades_editor_labels_follow_language(language: str, label: str) -> None:
    assert _edit("grades", {"entity": LATEST}, language=language)["labels"]["view"] == label
