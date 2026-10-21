from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.core import HomeAssistant
from pyedookit import PORTAL_TZ, SchoolEvent, Session
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.week import build_payload
from tests.helpers import week
from tests.week_data import KAMARAD, this_week

CARD_JS = (
    Path(__file__).parent.parent / "custom_components/edookit/frontend/edookit-timetable-card.js"
)
HARNESS_JS = Path(__file__).parent / "card_harness.js"
CARD_URL = "/edookit/edookit-timetable-card.js"
MESSAGES_CARD_URL = "/edookit/edookit-messages-card.js"


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
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    payloads = [build_payload(day, [this_week], events or []) for day in days]
    stdin = json.dumps(
        {
            "config": {"entity": "calendar.edookit_x_timetable", **config},
            "events": payloads,
            "now": now,
        }
    )
    # A clock timer left running after disconnect keeps node alive past the timeout.
    result = subprocess.run(
        [node, str(HARNESS_JS)],
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    return json.loads(result.stdout)


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
