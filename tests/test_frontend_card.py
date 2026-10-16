from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.core import HomeAssistant
from pyedookit import Session
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.week import build_payload
from tests.helpers import week
from tests.week_data import this_week

CARD_JS = (
    Path(__file__).parent.parent / "custom_components/edookit/frontend/edookit-timetable-card.js"
)
HARNESS_JS = Path(__file__).parent / "card_harness.js"
CARD_URL = "/edookit/edookit-timetable-card.js"


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


def test_card_script_is_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    subprocess.run([node, "--check", str(CARD_JS)], check=True)


WEDNESDAY = date(2026, 10, 14)
FRIDAY = date(2026, 10, 16)
SATURDAY = date(2026, 10, 17)
THIS_WEEK_DAYS = ["12.10.", "13.10.", "14.10.", "15.10.", "16.10."]
NEXT_WEEK_DAYS = ["19.10.", "20.10.", "21.10.", "22.10.", "23.10."]


def _render(config: dict[str, Any], *days: date) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    events = [build_payload(day, [this_week], []) for day in days]
    stdin = json.dumps(
        {"config": {"entity": "calendar.edookit_x_timetable", **config}, "events": events}
    )
    result = subprocess.run(
        [node, str(HARNESS_JS)], input=stdin, capture_output=True, text=True, check=True
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
