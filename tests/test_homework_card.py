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
from pyedookit import PORTAL_TZ, Homework

from custom_components.edookit.homework_payload import homework_payload
from tests.helpers import find, run_node, text
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
