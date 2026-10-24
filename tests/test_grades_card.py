from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from pyedookit import Grades

from custom_components.edookit.grades_payload import grades_payload
from tests.test_grades_websocket import GRADES, SUBJECTS, TODAY

CARD_JS = Path(__file__).parent.parent / "custom_components/edookit/frontend/edookit-grades-card.js"
HARNESS_JS = Path(__file__).parent / "grades_card_harness.js"
ENTITY = "sensor.edookit_x_latest_grade"


def _render(
    config: dict[str, Any] | None = None,
    grades: Grades | None = GRADES,
    *,
    payload: dict[str, Any] | None = None,
    language: str = "cs",
    seen: frozenset[int] = frozenset(),
    clicks: list[str] | None = None,
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    stdin = json.dumps(
        {
            "config": {"entity": ENTITY, **(config or {})},
            "language": language,
            "events": [payload if payload is not None else grades_payload(grades, TODAY, seen)],
            "clicks": clicks or [],
        }
    )
    result = subprocess.run(
        [node, str(HARNESS_JS)], input=stdin, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def _walk(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in node.get("children", []):
        yield from _walk(child)


def _find(out: dict[str, Any], pred: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
    return [n for n in _walk(out["tree"]) if pred(n)]


def _cls(name: str) -> Callable[[dict[str, Any]], bool]:
    return lambda n: name in (n.get("cls") or "").split()


def _text(node: dict[str, Any]) -> str:
    return "".join(n.get("text") or "" for n in _walk(node))


def _texts(out: dict[str, Any], name: str) -> list[str]:
    return [_text(n) for n in _find(out, _cls(name))]


def test_card_script_is_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    subprocess.run([node, "--check", str(CARD_JS)], check=True)


def test_card_never_uses_html_injection() -> None:
    assert not re.search(
        r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", CARD_JS.read_text()
    )


@pytest.mark.parametrize(
    "config",
    [{"entity": ""}, {"view": "grid"}, {"max_grades": 0}, {"max_grades": 2.5}],
)
def test_rejects_missing_entity_and_bad_options(config: dict[str, Any]) -> None:
    assert _render(config)["error"]


def test_subscribes_to_the_grades_of_the_entity() -> None:
    out = _render({"view": "latest"})

    assert out["calls"] == [{"type": "edookit/grades/subscribe", "entity_id": ENTITY}]


def test_latest_view_big_newest_then_list() -> None:
    out = _render({"view": "latest"})

    big = _find(out, _cls("big"))[0]
    assert [_text(n) for n in _find({"tree": big}, _cls("mark"))] == ["1"]
    assert "Test Unit 1" in _text(big)
    assert "Anglický jazyk" in _text(big)
    assert "Učitelka A" in _text(big)
    assert "váha 1" in _text(big)
    assert [_text(n) for n in _find(out, _cls("topic"))] == [
        "Test Unit 1",
        "Rytmus",
        "Slovíčka",
        "Výlet",
    ]
    assert _texts(out, "title") == ["Známky"]


def test_max_grades_limits_the_list() -> None:
    out = _render({"view": "latest", "max_grades": 2})

    assert _texts(out, "topic") == ["Test Unit 1", "Rytmus"]


def test_new_badge_only_within_five_days() -> None:
    # Today is 23. 10.: 21. 10. and 19. 10. are new, 16. 10. is not.
    out = _render({"view": "latest"})

    rows = _find(out, lambda n: _cls("big")(n) or _cls("row")(n))
    assert [bool(_find({"tree": r}, _cls("new"))) for r in rows] == [True, True, True, False]
    assert _texts(out, "new") == ["nová", "nová", "nová"]


def test_marks_are_coloured_by_value() -> None:
    out = _render({"view": "latest"})

    classes = [n["cls"] for n in _find(out, _cls("mark"))]
    assert classes == ["mark m1", "mark m2", "mark m3", "mark mx"]


def test_empty_grades_show_the_empty_state() -> None:
    out = _render({"view": "latest"}, Grades("1. pololetí 26/27", [], SUBJECTS))

    assert _texts(out, "status") == ["Zatím žádné známky"]


def test_unavailable_payload() -> None:
    out = _render({"view": "latest"}, None)

    assert _texts(out, "status") == ["Známky nejsou dostupné"]


def test_english_strings_and_date() -> None:
    out = _render({"view": "latest"}, language="en")

    assert _texts(out, "title") == ["Grades"]
    assert "21 Oct" in _text(_find(out, _cls("big"))[0])
    assert _texts(out, "new") == ["new", "new", "new"]


def test_language_option_overrides_the_user_language() -> None:
    out = _render({"view": "latest", "language": "en"}, language="cs")

    assert _texts(out, "title") == ["Grades"]


def test_portal_text_is_rendered_as_text() -> None:
    hostile = "<img src=x onerror=alert(1)>"
    first = dataclasses.replace(GRADES.grades[0], topic=hostile)
    out = _render({"view": "latest"}, Grades(GRADES.term, [first], SUBJECTS))

    assert not _find(out, lambda n: n["tag"] == "img")
    assert hostile in _text(_find(out, _cls("big"))[0])


def _subject_rows(out: dict[str, Any]) -> list[dict[str, Any]]:
    return _find(out, _cls("srow"))


def _in(node: dict[str, Any], name: str) -> list[str]:
    return [_text(n) for n in _find({"tree": node}, _cls(name))]


def test_subjects_view_lists_every_subject() -> None:
    out = _render({"view": "subjects"})

    rows = _subject_rows(out)
    assert [_in(r, "short") for r in rows] == [["Aj"], ["Hv"], ["Matematika"]]
    aj, hv, m = rows
    assert (_in(aj, "mark"), _in(aj, "avg"), _in(aj, "att")) == (["3", "1"], ["2,3"], ["100 %"])
    assert (_in(hv, "mark"), _in(hv, "avg"), _in(hv, "att")) == (["2"], ["2,0"], ["90 %"])
    assert (_in(m, "mark"), _in(m, "avg"), _in(m, "att")) == ([], ["—"], ["—"])
    assert _texts(out, "shead") == ["PředmětØDoch."]
    assert not _find(out, _cls("big"))


def test_subjects_view_english_average_uses_dot() -> None:
    out = _render({"view": "subjects"}, language="en")

    assert _in(_subject_rows(out)[0], "avg") == ["2.3"]
    assert _texts(out, "shead") == ["SubjectAvgAtt."]


def test_combined_is_the_default_view() -> None:
    assert _render()["tree"] == _render({"view": "combined"})["tree"]


def test_combined_view_folds_subjects_without_grades() -> None:
    out = _render({"view": "combined"})

    assert "Test Unit 1" in _text(_find(out, _cls("big"))[0])
    rows = _subject_rows(out)
    assert [_in(r, "short") for r in rows] == [["Aj"], ["Hv"]]
    assert _in(rows[0], "avg") == ["2,3"]
    assert not _find(out, _cls("att"))
    assert _texts(out, "fold") == ["1 předmět zatím bez známky"]


@pytest.mark.parametrize(
    ("count", "cs", "en"),
    [
        (2, "2 předměty zatím bez známky", "2 subjects without grades yet"),
        (5, "5 předmětů zatím bez známky", "5 subjects without grades yet"),
    ],
)
def test_combined_view_plural_forms(count: int, cs: str, en: str) -> None:
    empty = [dataclasses.replace(SUBJECTS[2], course_id=600 + i) for i in range(count)]
    grades = Grades(GRADES.term, GRADES.grades, [*SUBJECTS[:2], *empty])

    assert _texts(_render({"view": "combined"}, grades), "fold") == [cs]
    assert _texts(_render({"view": "combined"}, grades, language="en"), "fold") == [en]


def test_combined_view_without_empty_subjects_has_no_fold() -> None:
    grades = Grades(GRADES.term, GRADES.grades, SUBJECTS[:2])

    assert not _find(_render({"view": "combined"}, grades), _cls("fold"))


def test_grade_without_subject_shows_in_latest_not_subjects() -> None:
    latest = _render({"view": "latest"})
    subjects = _render({"view": "subjects"})

    assert "Ostatní" in _text(_find(latest, _cls("row"))[-1])
    assert "Výlet" not in _text(subjects["tree"])


def test_amber_mark_uses_dark_text() -> None:
    # White on #fbc02d is about 1.6:1; mark 3 would be hard to read.
    assert re.search(r"\.m3 \{[^}]*\bcolor: #212121", CARD_JS.read_text())


def _badges(out: dict[str, Any]) -> list[bool]:
    rows = _find(out, lambda n: _cls("big")(n) or _cls("row")(n))
    return [bool(_find({"tree": r}, _cls("new"))) for r in rows]


def test_seen_grade_has_no_badge() -> None:
    out = _render({"view": "latest"}, seen=frozenset({9102}))

    assert _badges(out) == [False, True, True, False]


def test_clicking_a_new_grade_marks_it_seen_at_once() -> None:
    out = _render({"view": "latest"}, clicks=["grade:9101"])

    assert out["ws"] == [{"type": "edookit/grades/seen", "entity_id": ENTITY, "grade_id": 9101}]
    assert _badges(out) == [True, False, True, False]


def test_clicking_a_grade_without_badge_sends_nothing() -> None:
    assert _render({"view": "latest"}, clicks=["grade:9099"])["ws"] == []
