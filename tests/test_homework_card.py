from __future__ import annotations

import dataclasses
import re
import shutil
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pyedookit import PORTAL_TZ, Exam, Homework

from custom_components.edookit.exams_payload import exams_payload
from custom_components.edookit.homework_payload import homework_payload
from tests.helpers import find, run_node, text
from tests.test_exams import at as ex_at
from tests.test_exams import exam
from tests.test_homework import at, hw

CARD_JS = (
    Path(__file__).parent.parent / "custom_components/edookit/frontend/edookit-homework-card.js"
)
HARNESS_JS = Path(__file__).parent / "homework_card_harness.js"
ENTITY = "sensor.edookit_x_homework"
NOW = int(datetime(2026, 11, 6, 12, 0, tzinfo=PORTAL_TZ).timestamp() * 1000)


def _render(
    config: dict[str, Any] | None = None,
    items: list[Homework] | None = None,
    *,
    payload: dict[str, Any] | None = None,
    exams: list[Exam] | None = None,
    exam_payload: dict[str, Any] | None = None,
    language: str = "cs",
    now: int = NOW,
    advance_ms: int = 0,
    clicks: list[str] | None = None,
    disconnect: bool = False,
    tz: str | None = None,
) -> dict[str, Any]:
    return run_node(
        HARNESS_JS,
        {
            "config": {"entity": ENTITY, **(config or {})},
            "language": language,
            "now": now,
            "events": [payload if payload is not None else homework_payload(items or [])],
            "exam_events": [
                exam_payload if exam_payload is not None else exams_payload(exams or [])
            ],
            "clicks": clicks or [],
            "advance_ms": advance_ms,
            "disconnect": disconnect,
        },
        tz,
    )


def _cls(name: str) -> Callable[[dict[str, Any]], bool]:
    return lambda n: name in (n.get("cls") or "").split()


def _texts(out: dict[str, Any], name: str) -> list[str]:
    return [text(n) for n in find(out["tree"], _cls(name))]


def _rows(out: dict[str, Any]) -> list[dict[str, Any]]:
    return find(out["tree"], _cls("row"))


def _ids_in(node: dict[str, Any]) -> list[int]:
    return [int(r["attrs"]["data-id"]) for r in find(node, _cls("row"))]


def _ids(out: dict[str, Any]) -> list[int]:
    return _ids_in(out["tree"])


def _in(node: dict[str, Any], name: str) -> list[str]:
    return [text(n) for n in find(node, _cls(name))]


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
    [
        {"entity": ""},
        {"view": "grid"},
        {"max_items": 0},
        {"max_items": 2.5},
        {"keep_overdue_days": -1},
        {"keep_overdue_days": 1.5},
    ],
)
def test_rejects_missing_entity_and_bad_options(config: dict[str, Any]) -> None:
    assert _render(config)["error"]


def test_subscribes_to_the_homework_of_the_entity() -> None:
    assert _render()["calls"] == [{"type": "edookit/homework/subscribe", "entity_id": ENTITY}]


def test_list_groups_and_order() -> None:
    items = [hw(4, None), hw(3, at(16)), hw(2, at(7)), hw(1, at(5))]

    out = _render(items=items)

    assert _texts(out, "group") == ["Po termínu", "Zítra", "Později", "Bez termínu"]
    assert _ids(out) == [1, 2, 3, 4]
    assert _texts(out, "title") == ["Domácí úkoly"]


def test_today_and_this_week_groups() -> None:
    items = [hw(1, at(8)), hw(2, at(6, 18)), hw(3, at(9)), hw(4, at(7))]

    out = _render(items=items)

    assert _texts(out, "group") == ["Dnes", "Zítra", "Tento týden", "Později"]
    assert _ids(out) == [2, 4, 1, 3]


def test_done_items_are_hidden() -> None:
    items = [hw(1, at(11)), hw(3, at(13), progress=100, done=True)]

    assert _ids(_render(items=items)) == [1]


def test_overdue_item_drops_after_keep_overdue_days() -> None:
    items = [hw(1, at(4, 14))]

    assert _ids(_render(items=items)) == [1]
    assert _ids(_render({"keep_overdue_days": 1}, items)) == []
    assert _ids(_render({"keep_overdue_days": 0}, items)) == []


def test_card_rerenders_on_its_minute_timer() -> None:
    soon = hw(1, datetime.fromtimestamp((NOW + 30_000) / 1000, PORTAL_TZ))
    config = {"keep_overdue_days": 0}

    before = _render(config, [soon])
    after = _render(config, [soon], advance_ms=60_000)

    assert _ids(before) == [1]
    assert before["scheduled"] and max(before["scheduled"]) <= 60_000
    assert _ids(after) == []
    assert _texts(after, "status") == ["Žádné úkoly"]
    assert after["pending"] and max(after["pending"]) <= 60_000
    assert after["rebuilt"] is True


def test_minute_tick_without_a_visible_change_keeps_the_rendered_card() -> None:
    out = _render(items=[hw(1, at(11))], advance_ms=60_000)

    assert out["rebuilt"] is False
    assert _ids(out) == [1]
    assert out["pending"] and max(out["pending"]) <= 60_000


def test_minute_tick_rebuilds_when_the_countdown_day_changes() -> None:
    out = _render(items=[hw(1, at(8))], advance_ms=12 * 3_600_000 + 60_000)

    assert out["rebuilt"] is True
    assert _texts(out, "group") == ["Zítra"]
    assert _in(_rows(out)[0], "countdown") == ["zítra"]


def test_timer_stops_when_the_card_is_removed() -> None:
    assert _render(items=[hw(1, at(11))], disconnect=True)["pending"] == []


def test_item_without_deadline_is_listed_last() -> None:
    out = _render(items=[hw(4, None, title="Projekt"), hw(1, at(11))])

    assert _texts(out, "group")[-1] == "Bez termínu"
    assert _ids(out) == [1, 4]
    assert _in(_rows(out)[1], "deadline") == []
    assert "Naučit se slovíčka" in text(_rows(out)[1])


def test_row_content_and_countdown() -> None:
    item = dataclasses.replace(hw(1, at(11)), text="Uč. str. 20 - přečíst.")

    row = _rows(_render(items=[item]))[0]

    assert _in(row, "short") == ["Aj"]
    assert _in(row, "text") == ["Uč. str. 20 - přečíst."]
    assert _in(row, "meta") == ["Anglický jazyk · Učitelka A"]
    assert _in(row, "deadline") == ["St 11. 11. 10:00"]
    assert _in(row, "countdown") == ["za 5 dní"]


def test_title_is_shown_when_text_is_empty_and_icon_without_course() -> None:
    bare = Homework(id=7, title="Projekt", text="", done=False, due=at(11))

    row = _rows(_render(items=[bare]))[0]

    assert _in(row, "text") == ["Projekt"]
    assert _in(row, "short") == ["📚"]
    assert _in(row, "meta") == []


def test_row_urgency_classes_and_countdown_words() -> None:
    items = [hw(1, at(5)), hw(2, at(6, 18)), hw(3, at(7)), hw(4, at(9)), hw(5, at(10))]

    rows = _rows(_render(items=items))

    assert [r["cls"] for r in rows] == [
        "row overdue",
        "row soon",
        "row soon",
        "row",
        "row",
    ]
    assert [_in(r, "countdown") for r in rows] == [
        ["po termínu"],
        ["dnes"],
        ["zítra"],
        ["za 3 dny"],
        ["za 4 dny"],
    ]


def test_toggles_hide_teacher_countdown_grouping() -> None:
    items = [hw(2, at(11)), hw(1, at(7))]

    out = _render({"show_teacher": False, "show_countdown": False, "group_by_due": False}, items)

    assert _in(_rows(out)[0], "meta") == ["Anglický jazyk"]
    assert not find(out["tree"], _cls("countdown"))
    assert not find(out["tree"], _cls("group"))
    assert _ids(out) == [1, 2]
    assert not find(_render({"show_header": False}, items)["tree"], _cls("title"))


def test_max_items_shows_plus_n_chip() -> None:
    items = [hw(1, at(7)), hw(2, at(8)), hw(3, at(9))]

    out = _render({"max_items": 2}, items)
    expanded = _render({"max_items": 2}, items, clicks=["click:more"])

    assert len(_rows(out)) == 2
    assert _texts(out, "count") == ["+1"]
    assert len(_rows(expanded)) == 3
    assert "+1" not in _texts(expanded, "count")


def test_grouping_uses_prague_dates_in_any_browser_zone() -> None:
    late = hw(1, datetime.fromisoformat("2026-11-07T00:30:00+01:00"))

    out = _render(items=[late], tz="America/New_York")

    assert _texts(out, "group") == ["Zítra"]
    assert _in(_rows(out)[0], "deadline") == ["So 7. 11. 00:30"]


def test_empty_and_unavailable_states() -> None:
    assert _texts(_render(items=[]), "status") == ["Žádné úkoly"]
    assert _texts(_render(payload=homework_payload(None)), "status") == ["Úkoly nejsou dostupné"]


def test_english_strings() -> None:
    out = _render(items=[hw(1, at(11))], language="en")

    assert _texts(out, "title") == ["Homework"]
    assert _texts(out, "group") == ["Later"]
    row = _rows(out)[0]
    assert _in(row, "deadline") == ["Wed 11 Nov 10:00"]
    assert _in(row, "countdown") == ["in 5 days"]


def test_language_option_overrides_the_user_language() -> None:
    assert _texts(_render({"language": "en"}, [hw(1, at(11))]), "title") == ["Homework"]


def test_portal_text_is_rendered_as_text() -> None:
    hostile = "<img src=x onerror=alert(1)>"
    item = dataclasses.replace(hw(1, at(11)), text=hostile, subject=hostile, teacher=hostile)

    out = _render(items=[item])

    assert not find(out["tree"], lambda n: n["tag"] == "img")
    text_nodes = find(out["tree"], lambda n: n["tag"] == "#text" and n["text"] == hostile)
    assert text_nodes
    assert _in(_rows(out)[0], "text") == [hostile]


def _dialogs(out: dict[str, Any]) -> list[dict[str, Any]]:
    return find(out["tree"], lambda n: n.get("attrs", {}).get("role") == "dialog")


def test_compact_counts_visible_items_and_overdue() -> None:
    items = [hw(1, at(11)), hw(2, at(5)), hw(3, at(13), progress=100, done=True)]

    out = _render({"view": "compact"}, items)

    assert _texts(out, "total") == ["2 úkoly · 1 po termínu"]
    assert not _rows(out)


def test_compact_nearest_is_earliest_deadline_ahead() -> None:
    items = [hw(1, at(13)), hw(2, at(5)), hw(3, at(11)), hw(4, None)]

    out = _render({"view": "compact"}, items)

    nearest = find(out["tree"], _cls("nearest"))
    assert [text(n) for n in nearest] == ["Nejbližší: Aj · St 11. 11. 10:00"]
    assert nearest[0]["cls"] == "nearest"


def test_compact_all_overdue_shows_oldest_in_red() -> None:
    items = [hw(1, at(5)), hw(2, at(4, 14))]

    out = _render({"view": "compact"}, items)

    nearest = find(out["tree"], _cls("nearest"))
    assert nearest[0]["cls"] == "nearest overdue"
    assert text(nearest[0]) == "Nejbližší: Aj · St 4. 11. 14:00 · po termínu"
    assert _texts(out, "total") == ["2 úkoly · 2 po termínu"]


def test_compact_without_deadlines_has_no_nearest_line() -> None:
    out = _render({"view": "compact"}, [hw(1, None)])

    assert _texts(out, "total") == ["1 úkol"]
    assert not find(out["tree"], _cls("nearest"))


@pytest.mark.parametrize(
    ("count", "cs", "en"),
    [
        (1, "1 úkol", "1 assignment"),
        (2, "2 úkoly", "2 assignments"),
        (4, "4 úkoly", "4 assignments"),
        (5, "5 úkolů", "5 assignments"),
    ],
)
def test_compact_plurals(count: int, cs: str, en: str) -> None:
    items = [hw(i, at(11)) for i in range(1, count + 1)]

    assert _texts(_render({"view": "compact"}, items), "total") == [cs]
    assert _texts(_render({"view": "compact"}, items, language="en"), "total") == [en]


def test_compact_english_overdue_and_nearest() -> None:
    out = _render({"view": "compact"}, [hw(1, at(5)), hw(2, at(11))], language="en")

    assert _texts(out, "total") == ["2 assignments · 1 overdue"]
    assert _texts(out, "nearest") == ["Next: Aj · Wed 11 Nov 10:00"]


def test_compact_tap_opens_list_popup() -> None:
    items = [hw(1, at(11)), hw(2, at(13)), hw(3, at(5))]

    closed = _render({"view": "compact", "max_items": 1}, items)
    opened = _render({"view": "compact", "max_items": 1}, items, clicks=["click:tile"])
    escaped = _render({"view": "compact"}, items, clicks=["click:tile", "key:overlay:Escape"])

    assert not find(closed["tree"], _cls("overlay"))
    (dialog,) = _dialogs(opened)
    assert dialog["attrs"]["aria-modal"] == "true"
    assert _ids_in(dialog) == [3, 1, 2]
    assert _in(dialog, "group") == ["Po termínu", "Později"]
    assert not find(escaped["tree"], _cls("overlay"))


def test_compact_popup_closes_on_backdrop_and_close_button() -> None:
    items = [hw(1, at(11))]

    for close in ("click:overlay", "click:close"):
        out = _render({"view": "compact"}, items, clicks=["click:tile", close])
        assert not find(out["tree"], _cls("overlay"))


def test_compact_popup_follows_the_minute_timer() -> None:
    soon = hw(1, datetime.fromtimestamp((NOW + 30_000) / 1000, PORTAL_TZ))
    config = {"view": "compact", "keep_overdue_days": 0}

    out = _render(config, [soon, hw(2, at(11))], clicks=["click:tile"], advance_ms=60_000)

    (dialog,) = _dialogs(out)
    assert _ids_in(dialog) == [2]
    assert _texts(out, "total") == ["1 úkol"]


def test_compact_empty() -> None:
    out = _render({"view": "compact"}, [])

    assert _texts(out, "status") == ["Žádné úkoly"]
    assert not find(out["tree"], _cls("tile"))


def _types(out: dict[str, Any]) -> list[str]:
    return [call["type"] for call in out["calls"]]


def test_default_show_subscribes_only_to_homework() -> None:
    assert _types(_render()) == ["edookit/homework/subscribe"]


def test_show_exams_subscribes_only_to_exams() -> None:
    out = _render({"show": "exams"})
    assert out["calls"] == [{"type": "edookit/exams/subscribe", "entity_id": ENTITY}]


def test_show_both_subscribes_to_both() -> None:
    assert sorted(_types(_render({"show": "both"}))) == [
        "edookit/exams/subscribe",
        "edookit/homework/subscribe",
    ]


def test_rejects_bad_show_option() -> None:
    assert _render({"show": "tests"})["error"] == "show must be one of homework, exams, both"


def test_exam_row_content() -> None:
    row = _rows(_render({"show": "exams"}, exams=[exam(9, ex_at(9))]))[0]

    assert _in(row, "short") == ["M"]
    assert _in(row, "text") == ["Zlomky"]
    assert _in(row, "meta") == ["Matematika · Učitelka A"]
    assert _in(row, "kind") == ["Malá písemka"]
    assert _in(row, "deadline") == ["Po 9. 11. 08:00–08:45"]
    assert _in(row, "countdown") == ["za 3 dny"]
    quiet = _rows(_render({"show": "exams", "show_teacher": False}, exams=[exam(9, ex_at(9))]))
    assert _in(quiet[0], "meta") == ["Matematika"]


def test_exams_group_by_start_day() -> None:
    exams = [exam(4, ex_at(12)), exam(3, ex_at(8)), exam(2, ex_at(7)), exam(1, ex_at(6, 14))]

    out = _render({"show": "exams"}, exams=exams)

    assert _texts(out, "group") == ["Dnes", "Zítra", "Tento týden", "Později"]
    assert _ids(out) == [1, 2, 3, 4]


def test_exam_drops_off_when_it_ends() -> None:
    running = exam(1, ex_at(6, 11, 50))

    assert _ids(_render({"show": "exams"}, exams=[running])) == [1]
    later = _render({"show": "exams"}, exams=[running], advance_ms=40 * 60 * 1000)
    assert _ids(later) == []


def test_both_mixes_by_date_exam_first_on_ties() -> None:
    out = _render({"show": "both"}, [hw(1, at(9, 8)), hw(3, at(7))], exams=[exam(2, ex_at(9, 8))])

    assert _ids(out) == [3, 2, 1]
    assert [r["attrs"]["data-kind"] for r in _rows(out)] == ["homework", "exam", "homework"]


def test_both_with_exams_unavailable_still_shows_homework() -> None:
    out = _render({"show": "both"}, [hw(1, at(11))], exam_payload=exams_payload(None))

    assert _ids(out) == [1]
    assert _texts(out, "status") == ["Písemky nejsou dostupné"]


def test_exams_only_unavailable_status() -> None:
    gone = exams_payload(None)
    assert _texts(_render({"show": "exams"}, exam_payload=gone), "status") == [
        "Písemky nejsou dostupné"
    ]
    english = _render({"show": "exams"}, exam_payload=gone, language="en")
    assert _texts(english, "status") == ["Exams aren't available"]


def test_exams_empty_status() -> None:
    assert _texts(_render({"show": "exams"}), "status") == ["Žádné písemky"]
    assert _texts(_render({"show": "both"}), "status") == ["Žádné úkoly ani písemky"]


@pytest.mark.parametrize(
    ("show", "cs", "en"),
    [
        ("homework", "Domácí úkoly", "Homework"),
        ("exams", "Písemky", "Exams"),
        ("both", "Úkoly a písemky", "Homework and exams"),
    ],
)
def test_title_follows_show(show: str, cs: str, en: str) -> None:
    assert _texts(_render({"show": show}), "title") == [cs]
    assert _texts(_render({"show": show}, language="en"), "title") == [en]


def test_exam_portal_text_is_rendered_as_text() -> None:
    hostile = "<img src=x onerror=alert(1)>"
    item = dataclasses.replace(
        exam(1, ex_at(9)), title=hostile, subject=hostile, teacher=hostile, kind=hostile
    )

    out = _render({"show": "exams"}, exams=[item])

    assert not find(out["tree"], lambda n: n["tag"] == "img")
    assert _in(_rows(out)[0], "text") == [hostile]
    assert _in(_rows(out)[0], "kind") == [hostile]


def test_compact_both_counts_each_kind() -> None:
    homework = [hw(1, at(11)), hw(2, at(5)), hw(3, at(12))]
    exams = [exam(4, ex_at(9)), exam(5, ex_at(10))]

    out = _render({"view": "compact", "show": "both"}, homework, exams=exams)

    assert _texts(out, "total") == ["3 úkoly · 1 po termínu · 2 písemky"]
    plain = _render({"view": "compact", "show": "both"}, homework[::2], exams=exams)
    assert _texts(plain, "total") == ["2 úkoly · 2 písemky"]


def test_compact_nearest_is_soonest_of_either_kind() -> None:
    config = {"view": "compact", "show": "both"}

    homework_first = _render(config, [hw(1, at(6, 18))], exams=[exam(2, ex_at(7))])
    exam_first = _render(config, [hw(1, at(9))], exams=[exam(2, ex_at(7))])

    assert _texts(homework_first, "nearest") == ["Nejbližší: Aj · Pá 6. 11. 18:00"]
    assert _texts(exam_first, "nearest") == ["Nejbližší: 📝 M · So 7. 11. 08:00"]


@pytest.mark.parametrize(
    ("count", "cs", "en"),
    [(1, "1 písemka", "1 exam"), (2, "2 písemky", "2 exams"), (5, "5 písemek", "5 exams")],
)
def test_compact_exam_plurals(count: int, cs: str, en: str) -> None:
    exams = [exam(i, ex_at(9)) for i in range(1, count + 1)]
    config = {"view": "compact", "show": "exams"}

    assert _texts(_render(config, exams=exams), "total") == [cs]
    assert _texts(_render(config, exams=exams, language="en"), "total") == [en]


def test_compact_popup_lists_exams() -> None:
    out = _render(
        {"view": "compact", "show": "both"},
        [hw(1, at(11))],
        exams=[exam(2, ex_at(9))],
        clicks=["click:tile"],
    )

    (dialog,) = _dialogs(out)
    assert _ids_in(dialog) == [2, 1]
    assert _in(dialog, "kind") == ["Malá písemka"]


def test_both_with_homework_unavailable_and_no_exams_says_which_failed() -> None:
    out = _render({"show": "both"}, payload=homework_payload(None))

    assert _texts(out, "status") == ["Žádné písemky", "Úkoly nejsou dostupné"]
