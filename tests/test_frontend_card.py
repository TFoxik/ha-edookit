from __future__ import annotations

import dataclasses
import hashlib
import re
import shutil
import subprocess
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.core import HomeAssistant
from pyedookit import PORTAL_TZ, Homework, Lesson, Period, SchoolEvent, Session
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.homework_payload import homework_payload
from custom_components.edookit.week import WeekLessons, build_payload
from tests.helpers import run_node, text, walk, week
from tests.test_homework import hw
from tests.week_data import FIVE_PERIODS, KAMARAD, this_week

CARD_JS = (
    Path(__file__).parent.parent / "custom_components/edookit/frontend/edookit-timetable-card.js"
)
HARNESS_JS = Path(__file__).parent / "card_harness.js"
CARD_URL = "/edookit/edookit-timetable-card.js"
MESSAGES_CARD_URL = "/edookit/edookit-messages-card.js"
GRADES_CARD_URL = "/edookit/edookit-grades-card.js"
HOMEWORK_CARD_URL = "/edookit/edookit-homework-card.js"


async def test_card_script_is_served_and_registered(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    session = Session.from_cookies(
        "zs-example", edookit={"PHPSESSID": "s"}, plus4u={"uoid.ps": "p"}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="zs-example:user@example.com",
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: session.to_json()},
    )
    entry.add_to_hass(hass)
    timetable = AsyncMock(return_value=week(this_week.lessons, this_week.periods))
    with patch("pyedookit.client.EdookitClient.get_timetable_week", new=timetable):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    resp = await (await hass_client()).get(CARD_URL)
    assert resp.status == 200
    assert "edookit-timetable-card" in await resp.text()
    assert any(f"{CARD_URL}?v=" in url for url in hass.data[DATA_EXTRA_MODULE_URL].urls)

    resp = await (await hass_client()).get(MESSAGES_CARD_URL)
    assert resp.status == 200
    assert "edookit-messages-card" in await resp.text()
    assert any(f"{MESSAGES_CARD_URL}?v=" in url for url in hass.data[DATA_EXTRA_MODULE_URL].urls)

    resp = await (await hass_client()).get(GRADES_CARD_URL)
    assert resp.status == 200
    assert "edookit-grades-card" in await resp.text()
    assert any(f"{GRADES_CARD_URL}?v=" in url for url in hass.data[DATA_EXTRA_MODULE_URL].urls)

    resp = await (await hass_client()).get(HOMEWORK_CARD_URL)
    assert resp.status == 200
    assert "edookit-homework-card" in await resp.text()
    assert any(f"{HOMEWORK_CARD_URL}?v=" in url for url in hass.data[DATA_EXTRA_MODULE_URL].urls)
    digest = hashlib.sha256(CARD_JS.read_bytes()).hexdigest()[:8]
    assert any(
        url.startswith(f"{CARD_URL}?v=") and url.endswith(digest)
        for url in hass.data[DATA_EXTRA_MODULE_URL].urls
    )


def test_card_script_is_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    subprocess.run([node, "--check", str(CARD_JS)], check=True)


def test_card_never_uses_html_injection() -> None:
    assert not re.search(
        r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", CARD_JS.read_text()
    )


WEDNESDAY = date(2026, 10, 14)
THURSDAY = date(2026, 10, 15)
FRIDAY = date(2026, 10, 16)
SATURDAY = date(2026, 10, 17)
THIS_WEEK_DAYS = ["12.10.", "13.10.", "14.10.", "15.10.", "16.10."]
NEXT_WEEK_DAYS = ["19.10.", "20.10.", "21.10.", "22.10.", "23.10."]


def _render(
    config: dict[str, Any],
    *days: date,
    events: list[SchoolEvent] | None = None,
    now: str | None = None,
    known: WeekLessons = this_week,
    homework: list[Homework] | None = None,
    tz: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payloads = [build_payload(day, [known], events or []) for day in days]
    return run_node(
        HARNESS_JS,
        {
            "config": {"entity": "calendar.edookit_x_timetable", **config},
            "events": payloads,
            "homework_events": None if homework is None else [homework_payload(homework)],
            "now": now,
            **extra,
        },
        tz,
    )


def test_card_shows_the_week_header_by_default() -> None:
    shown = _render({}, WEDNESDAY)

    assert shown["head"] is True
    assert shown["title"] == "12.–16. 10."
    assert shown["buttons"] == 2
    assert shown["days"] == THIS_WEEK_DAYS


def test_card_without_header_shows_only_the_grid() -> None:
    shown = _render({"show_header": False}, WEDNESDAY)

    assert shown["head"] is False
    assert shown["buttons"] == 0
    assert shown["days"] == THIS_WEEK_DAYS


def test_card_has_no_name_by_default() -> None:
    assert _render({}, WEDNESDAY)["names"] == []


def test_card_shows_its_title_next_to_the_week() -> None:
    shown = _render({"title": "Anna"}, WEDNESDAY)

    assert shown["names"] == ["Anna"]
    assert shown["title"] == "12.–16. 10."
    assert shown["buttons"] == 2


def test_card_without_header_still_shows_its_title() -> None:
    shown = _render({"title": "Anna", "show_header": False}, WEDNESDAY)

    assert shown["head"] is False
    assert shown["names"] == ["Anna"]
    assert shown["days"] == THIS_WEEK_DAYS


def test_card_ignores_a_blank_title() -> None:
    assert _render({"title": "  "}, WEDNESDAY)["names"] == []


def test_card_without_header_shows_next_week_on_saturday() -> None:
    assert _render({"show_header": False}, SATURDAY)["days"] == NEXT_WEEK_DAYS


def test_card_without_header_moves_to_next_week_at_saturday_midnight() -> None:
    assert _render({"show_header": False}, FRIDAY, SATURDAY)["days"] == NEXT_WEEK_DAYS


def _at(hour: int, minute: int, day: int) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=PORTAL_TZ)


# One of each tile placement: before school, after school, spanning periods, all day.
EVERY_PLACEMENT = [
    SchoolEvent("e1", "Družina", _at(7, 0, 12), _at(7, 45, 12)),
    SchoolEvent("e2", "Kroužek", _at(14, 0, 14), _at(16, 0, 14)),
    KAMARAD,
    SchoolEvent("e4", "Ředitelské volno", date(2026, 10, 16), date(2026, 10, 16)),
]


def _shifted(line: str) -> str:
    return " / ".join(str(int(part) - 1) if int(part) > 0 else part for part in line.split(" / "))


def test_card_shows_period_and_day_labels_by_default() -> None:
    shown = _render({}, WEDNESDAY, events=EVERY_PLACEMENT)

    assert shown["periodHeads"] == len(this_week.periods)
    assert shown["days"] == THIS_WEEK_DAYS
    assert shown["columns"].startswith("auto ")
    assert shown["rows"].startswith("auto ")


LONG_DAY = WeekLessons(
    this_week.monday,
    this_week.lessons,
    [
        Period(0, time(7, 10), time(7, 55)),
        *this_week.periods,
        *(Period(n, time(12 + n - 5, 45), time(13 + n - 5, 30)) for n in range(6, 10)),
    ],
)
EVENING = SchoolEvent("e5", "Uspávání", _at(17, 0, 12), _at(18, 0, 12))
MORNING = SchoolEvent("e6", "Družina", _at(6, 0, 13), _at(7, 0, 13))


def test_card_shows_every_school_period_when_nothing_is_outside_lessons() -> None:
    shown = _render({}, WEDNESDAY, known=LONG_DAY)

    assert shown["periodHeads"] == 10


def test_card_drops_unused_periods_between_lessons_and_an_after_school_event() -> None:
    shown = _render({}, WEDNESDAY, events=[EVENING], known=LONG_DAY)

    assert shown["periodHeads"] == 6
    assert shown["columns"].endswith("repeat(6, minmax(0, 1fr)) 4px minmax(56px, 1.4fr)")
    assert ["2", "9"] in shown["cells"]


def test_card_drops_unused_periods_between_a_before_school_event_and_lessons() -> None:
    shown = _render({}, WEDNESDAY, events=[MORNING], known=LONG_DAY)

    assert shown["periodHeads"] == 9
    assert shown["columns"] == "auto minmax(56px, 1.4fr) 4px repeat(9, minmax(0, 1fr))"
    assert ["3", "2"] in shown["cells"]


def test_card_without_periods_drops_the_top_row() -> None:
    full = _render({}, WEDNESDAY, events=EVERY_PLACEMENT)
    shown = _render({"show_periods": False}, WEDNESDAY, events=EVERY_PLACEMENT)

    assert shown["periodHeads"] == 0
    assert shown["days"] == THIS_WEEK_DAYS
    assert not shown["rows"].startswith("auto ")
    assert shown["cells"] == [[_shifted(row), column] for row, column in full["cells"]]


def test_card_without_days_drops_the_first_column() -> None:
    full = _render({}, WEDNESDAY, events=EVERY_PLACEMENT)
    shown = _render({"show_days": False}, WEDNESDAY, events=EVERY_PLACEMENT)

    assert shown["days"] == []
    assert shown["periodHeads"] == len(this_week.periods)
    assert not shown["columns"].startswith("auto ")
    assert shown["cells"] == [[row, _shifted(column)] for row, column in full["cells"]]


def test_card_can_show_the_lessons_alone() -> None:
    config = {"show_header": False, "show_periods": False, "show_days": False}
    shown = _render(config, WEDNESDAY, events=EVERY_PLACEMENT)

    assert (shown["head"], shown["periodHeads"], shown["days"]) == (False, 0, [])
    assert shown["cells"]


def test_card_without_days_marks_today_with_a_row_band() -> None:
    assert _render({"show_days": False}, WEDNESDAY)["todayRows"] == ["4"]
    assert _render({"show_days": False, "show_periods": False}, WEDNESDAY)["todayRows"] == ["3"]


def test_card_with_days_marks_today_on_the_label_only() -> None:
    assert _render({}, WEDNESDAY)["todayRows"] == []


def test_card_without_days_marks_no_row_when_today_is_not_shown() -> None:
    assert _render({"show_days": False}, SATURDAY)["todayRows"] == []


DURING_HV = "09:10"


def test_card_style_defaults_to_classic() -> None:
    shown = _render({}, WEDNESDAY, now=DURING_HV)

    assert shown["cardClass"] == "card style-classic"
    assert shown["haCardClass"] == "style-classic"
    assert shown["now"] == []


def test_card_rejects_an_unknown_style() -> None:
    assert _render({"style": "neon"}, WEDNESDAY)["error"] == "style must be one of classic, glow"


def test_glow_card_marks_only_the_lesson_in_progress() -> None:
    shown = _render({"style": "glow"}, WEDNESDAY, now=DURING_HV)

    assert shown["cardClass"] == "card style-glow"
    assert shown["haCardClass"] == "style-glow"
    assert shown["now"] == ["Hv"]


@pytest.mark.parametrize(
    ("day", "now"),
    [(WEDNESDAY, "07:30"), (WEDNESDAY, "09:40"), (WEDNESDAY, "12:00"), (SATURDAY, DURING_HV)],
    ids=["before school", "in a break", "after school", "weekend"],
)
def test_glow_card_marks_nothing_outside_lessons(day: date, now: str) -> None:
    assert _render({"style": "glow"}, day, now=now)["now"] == []


def test_glow_card_marks_today_on_the_label_only() -> None:
    assert _render({"style": "glow"}, WEDNESDAY)["todayRows"] == []
    assert _render({"style": "glow", "show_days": False}, WEDNESDAY)["todayRows"] == ["4"]


def test_glow_card_lights_up_an_event_in_progress() -> None:
    during = _render({"style": "glow"}, THURSDAY, events=[KAMARAD], now="10:30")
    before = _render({"style": "glow"}, THURSDAY, events=[KAMARAD], now="09:00")

    assert during["now"] == [KAMARAD.title]
    assert KAMARAD.title not in before["now"]


def test_glow_card_lights_up_an_all_day_event_all_day() -> None:
    shown = _render({"style": "glow"}, FRIDAY, events=EVERY_PLACEMENT, now="15:00")

    assert "Ředitelské volno" in shown["now"]


NOV_MONDAY = date(2026, 11, 9)
HW_ENTITY = "calendar.edookit_x_timetable"
HW_NOW = int(datetime(2026, 11, 9, 12, 0, tzinfo=PORTAL_TZ).timestamp() * 1000)
HW_URL = "edookit/homework/subscribe"
WEEK_URL = "edookit/week/subscribe"


def _nov(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=PORTAL_TZ)


def _english(day: int, period: int, group: str | None = "I.B", code: str = "Aj 2") -> Lesson:
    p = FIVE_PERIODS[period - 1]
    return Lesson(
        start=_nov(day, p.start.hour, p.start.minute),
        end=_nov(day, p.end.hour, p.end.minute),
        subject="Anglický jazyk",
        teacher="Učitelka A",
        room="2.B",
        code=code,
        group=group,
    )


def _czech(day: int, period: int) -> Lesson:
    return dataclasses.replace(_english(day, period), subject="Český jazyk", code="Čj", group=None)


NOV_WEEK = WeekLessons(
    NOV_MONDAY,
    [
        _english(9, 1),
        _czech(9, 2),
        _czech(11, 1),
        _english(11, 3),
        _english(12, 2, group="II.A"),
    ],
    FIVE_PERIODS,
)


def _homework_render(
    items: list[Homework],
    config: dict[str, Any] | None = None,
    known: WeekLessons = NOV_WEEK,
    **extra: Any,
) -> dict[str, Any]:
    return _render(
        {"show_homework": True, **(config or {})},
        NOV_MONDAY,
        known=known,
        homework=items,
        **{"now_ms": HW_NOW, **extra},
    )


def test_no_homework_subscription_by_default() -> None:
    shown = _render({}, WEDNESDAY, homework=[hw(1, _nov(11, 10))])

    assert shown["subscribed"] == [WEEK_URL]
    assert shown["markers"] == []


def test_no_clock_timer_without_glow_or_homework() -> None:
    shown = _render({}, WEDNESDAY)

    assert shown["scheduled"] == [] and shown["pending"] == []


def test_card_subscribes_to_homework_with_its_own_entity() -> None:
    shown = _homework_render([hw(1, _nov(11, 10))])

    assert shown["subscribed"] == [WEEK_URL, HW_URL]
    assert shown["entities"] == [HW_ENTITY, HW_ENTITY]


def test_marker_on_the_matching_lesson() -> None:
    shown = _homework_render([hw(1, _nov(11, 10))])

    assert shown["markers"] == [{"day": "11.11.", "code": "Aj 2", "column": "4", "cls": "hw"}]


def test_marker_on_a_lesson_without_a_group() -> None:
    item = dataclasses.replace(hw(1, _nov(9, 10)), course_code="Čj")

    shown = _homework_render([item])

    assert [(m["day"], m["code"]) for m in shown["markers"]] == [("9.11.", "Čj")]


def test_week_without_homework_has_no_marker() -> None:
    assert _homework_render([])["markers"] == []


EIGHT_AND_ELEVEN = WeekLessons(NOV_MONDAY, [_english(11, 1), _english(11, 4)], FIVE_PERIODS)


@pytest.mark.parametrize(
    ("due", "column"),
    [(_nov(11, 10), "2"), (_nov(11, 11, 30), "5"), (_nov(11, 7, 30), "2")],
    ids=["between the lessons", "after both", "before both"],
)
def test_marker_picks_lesson_before_deadline_time(due: datetime, column: str) -> None:
    shown = _homework_render([hw(1, due)], known=EIGHT_AND_ELEVEN)

    assert [m["column"] for m in shown["markers"]] == [column]


MONDAY_DUE = _nov(9, 10)
WEDNESDAY_9AM = int(_nov(11, 9).timestamp() * 1000)


def test_overdue_marker_is_red_and_drops_after_window() -> None:
    items = [hw(1, MONDAY_DUE)]

    kept = _homework_render(items, now_ms=WEDNESDAY_9AM)
    dropped = _homework_render(items, {"homework_overdue_days": 1}, now_ms=WEDNESDAY_9AM)

    assert kept["markers"] == [{"day": "9.11.", "code": "Aj 2", "column": "2", "cls": "hw overdue"}]
    assert dropped["markers"] == []


def test_marker_before_deadline_is_not_overdue() -> None:
    shown = _homework_render([hw(1, _nov(9, 14))])

    assert [m["cls"] for m in shown["markers"]] == ["hw"]


def test_done_and_unmatched_items_have_no_marker() -> None:
    base = hw(1, _nov(11, 10))
    items = [
        dataclasses.replace(base, id=1, done=True, progress=100),
        dataclasses.replace(base, id=2, course_code="Aj 2 - II.B"),
        dataclasses.replace(base, id=3, course_code="Nj 1 - I.B"),
        dataclasses.replace(base, id=4, course_code=None),
        dataclasses.replace(base, id=5, due=None),
        dataclasses.replace(base, id=6, due=_nov(10, 10)),
        dataclasses.replace(base, id=7, due=_nov(12, 10)),
    ]

    assert _homework_render(items)["markers"] == []


def test_unavailable_homework_has_no_marker() -> None:
    shown = _homework_render([], homework_events=[{"available": False, "homework": []}])

    assert shown["markers"] == []


def test_marker_day_uses_prague_date() -> None:
    due = datetime(2026, 11, 11, 0, 30, tzinfo=PORTAL_TZ)

    shown = _homework_render([hw(1, due)], tz="UTC")

    assert [(m["day"], m["code"]) for m in shown["markers"]] == [("11.11.", "Aj 2")]


def test_homework_in_lesson_detail_is_text() -> None:
    hostile = "<img src=x onerror=alert(1)>"
    item = dataclasses.replace(hw(1, _nov(11, 10)), text=hostile)

    shown = _homework_render([item], {"language": "cs"}, click="hw")

    nodes = list(walk(shown["detail"]))
    rows = [n for n in nodes if "row" in (n.get("cls") or "").split()]
    label, value = next(r["children"] for r in rows if text(r["children"][0]) == "Úkol")
    assert value["children"] == [
        {
            "tag": "div",
            "cls": "",
            "attrs": {},
            "children": [{"tag": "#text", "text": f"{hostile} (do 10:00)"}],
        }
    ]
    assert not [n for n in nodes if n["tag"] == "img"]


def test_homework_detail_row_in_english_falls_back_to_the_title() -> None:
    item = dataclasses.replace(hw(1, _nov(11, 10)), text="")

    shown = _homework_render([item], click="hw")

    rows = [n for n in walk(shown["detail"]) if "row" in (n.get("cls") or "").split()]
    values = {text(r["children"][0]): text(r["children"][1]) for r in rows}
    assert values["Homework"] == "Slovíčka 3 (due 10:00)"


def test_homework_detail_lists_every_item_of_the_lesson() -> None:
    items = [hw(1, _nov(11, 10)), dataclasses.replace(hw(2, _nov(11, 9)), text="Cvičení 4")]

    shown = _homework_render(items, click="hw")

    rows = [n for n in walk(shown["detail"]) if "row" in (n.get("cls") or "").split()]
    values = {text(r["children"][0]): r["children"][1]["children"] for r in rows}
    assert [text(v) for v in values["Homework"]] == [
        "Naučit se slovíčka ze strany 14. (due 10:00)",
        "Cvičení 4 (due 09:00)",
    ]


def test_lesson_without_homework_has_no_homework_row() -> None:
    shown = _render({}, NOV_MONDAY, known=NOV_WEEK, click="code")

    labels = [
        text(n["children"][0])
        for n in walk(shown["detail"])
        if "row" in (n.get("cls") or "").split()
    ]
    assert "Homework" not in labels


def test_marker_follows_the_minute_clock() -> None:
    items = [hw(1, MONDAY_DUE)]
    almost = int(_nov(11, 9, 59).timestamp() * 1000) + 30_000

    before = _homework_render(items, now_ms=almost)
    after = _homework_render(items, now_ms=almost, advance_ms=61_000)

    assert [m["cls"] for m in before["markers"]] == ["hw overdue"]
    assert after["markers"] == []


def test_homework_clock_timer_runs_once_and_stops_on_disconnect() -> None:
    shown = _homework_render([hw(1, _nov(11, 10))], advance_ms=61_000)

    assert len(shown["scheduled"]) == 1
    assert len(shown["live"]) == 1
    assert shown["pending"] == []


def test_both_subscriptions_end_on_disconnect() -> None:
    shown = _homework_render([hw(1, _nov(11, 10))])

    assert sorted(shown["unsubscribed"]) == [HW_URL, WEEK_URL]


def test_turning_homework_off_drops_the_second_subscription_and_the_markers() -> None:
    shown = _homework_render([hw(1, _nov(11, 10))], config_after={"entity": HW_ENTITY})

    assert shown["subscribed"] == [WEEK_URL, HW_URL]
    assert shown["unsubscribed"] == [HW_URL, WEEK_URL]
    assert shown["markers"] == []
    assert shown["pending"] == []


def test_reconnect_resubscribes_each_feed_once() -> None:
    shown = _homework_render([hw(1, _nov(11, 10))], reconnect=True)

    assert shown["subscribed"] == [WEEK_URL, HW_URL, WEEK_URL, HW_URL]
    assert sorted(shown["unsubscribed"]) == [HW_URL, HW_URL, WEEK_URL, WEEK_URL]


@pytest.mark.parametrize("show_homework", [False, True])
def test_hass_before_config_does_not_throw(show_homework: bool) -> None:
    shown = _homework_render(
        [hw(1, _nov(11, 10))], {"show_homework": show_homework}, hass_before_config=True
    )

    assert "error" not in shown
    assert [m["column"] for m in shown["markers"]] == (["4"] if show_homework else [])


@pytest.mark.parametrize("bad", [-1, 1.5, "2"])
def test_rejects_a_bad_homework_overdue_days(bad: float | str) -> None:
    shown = _render({"homework_overdue_days": bad}, WEDNESDAY)

    assert shown["error"] == "homework_overdue_days must be a whole number, 0 or more"
