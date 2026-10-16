from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.core import HomeAssistant
from pyedookit import Session
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from tests.helpers import week
from tests.week_data import this_week

CARD_JS = (
    Path(__file__).parent.parent / "custom_components/edookit/frontend/edookit-timetable-card.js"
)
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
