from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pyedookit import PORTAL_TZ, MessageSummary, ParseError, Session
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.diagnostics import async_get_config_entry_diagnostics
from tests.helpers import week

SESSION = Session.from_cookies("zs-example", edookit={"PHPSESSID": "s"}, plus4u={"uoid.ps": "p"})
UNREAD = "sensor.edookit_zs_example_unread_messages"
TIMETABLE = "calendar.edookit_zs_example_timetable"


def summary(message_id: int, unread: bool, subject: str = "Předmět") -> MessageSummary:
    return MessageSummary(
        id=message_id,
        subject=f"{subject} {message_id}",
        sender="Učitelka A",
        sent=datetime(2026, 10, 21, 8, message_id % 60, tzinfo=PORTAL_TZ),
        preview="Vážení rodiče…",
        unread=unread,
    )


INBOX = [summary(9003, True), summary(9002, True), summary(9001, False)]


async def setup_entry(hass: HomeAssistant, get_inbox: AsyncMock) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="zs-example:user@example.com",
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: SESSION.to_json()},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "pyedookit.client.EdookitClient.get_timetable_week",
            new=AsyncMock(return_value=week([])),
        ),
        patch("pyedookit.client.EdookitClient.get_inbox", new=get_inbox),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_unread_sensor_counts_unread_messages(hass: HomeAssistant) -> None:
    await setup_entry(hass, AsyncMock(return_value=INBOX))

    assert hass.states.get(UNREAD).state == "2"


async def test_unread_sensor_has_no_message_content_in_attributes(hass: HomeAssistant) -> None:
    await setup_entry(hass, AsyncMock(return_value=INBOX))

    attributes = json.dumps(dict(hass.states.get(UNREAD).attributes), default=str)
    for message in INBOX:
        for text in (message.subject, message.sender, message.preview):
            assert text not in attributes


async def test_mark_read_updates_the_sensor_at_once(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=INBOX))

    entry.runtime_data.messages.async_mark_read(9003)
    await hass.async_block_till_done()

    assert hass.states.get(UNREAD).state == "1"
    assert [m.unread for m in entry.runtime_data.messages.data] == [False, True, False]


async def test_mark_read_of_an_unknown_id_changes_nothing(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=INBOX))

    entry.runtime_data.messages.async_mark_read(1)
    await hass.async_block_till_done()

    assert hass.states.get(UNREAD).state == "2"


async def test_inbox_failure_leaves_timetable_working_and_sensor_unavailable(
    hass: HomeAssistant,
) -> None:
    entry = await setup_entry(hass, AsyncMock(side_effect=ParseError("no grid")))

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(TIMETABLE).state != "unavailable"
    assert hass.states.get(UNREAD).state == "unavailable"


async def test_diagnostics_has_counts_but_no_message_text(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, AsyncMock(return_value=INBOX))

    data = await async_get_config_entry_diagnostics(hass, entry)

    assert (data["message_count"], data["unread_message_count"]) == (3, 2)
    assert "Předmět" not in json.dumps(data, default=str)
