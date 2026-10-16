from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pyedookit import PORTAL_TZ, EdookitConnectionError, Lesson, SchoolEvent, Session
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edookit.const import CONF_SCHOOL, CONF_SESSION, DOMAIN
from custom_components.edookit.memory import WeekMemory
from custom_components.edookit.week import WeekLessons, build_payload
from tests.helpers import week
from tests.week_data import FIVE_PERIODS, KAMARAD, VOLNO, this_week

SESSION = Session.from_cookies("zs-example", edookit={"PHPSESSID": "s"}, plus4u={"uoid.ps": "p"})
FRIDAY = date(2026, 10, 16)


async def _flush_delayed_save(hass: HomeAssistant) -> None:
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()


def _memory(hass: HomeAssistant, entry_id: str = "abc") -> WeekMemory:
    return WeekMemory(hass, entry_id)


def _prague(day: int, hour: int) -> datetime:
    return datetime(2026, 10, day, hour, 0, tzinfo=PORTAL_TZ)


def _lessons_in(monday: date, count: int = 1) -> list[Lesson]:
    return [
        Lesson(
            start=datetime.combine(monday, FIVE_PERIODS[n].start, tzinfo=PORTAL_TZ),
            end=datetime.combine(monday, FIVE_PERIODS[n].end, tzinfo=PORTAL_TZ),
            subject="Matematika",
            code="M",
        )
        for n in range(count)
    ]


async def test_an_event_that_vanishes_after_it_started_is_kept(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    mem.observe_events([KAMARAD], now=datetime(2026, 10, 15, 9, 0, tzinfo=PORTAL_TZ))
    mem.observe_events([], now=datetime(2026, 10, 16, 9, 0, tzinfo=PORTAL_TZ))
    assert [e.id for e in mem.events()] == ["e1"]


async def test_an_event_that_vanishes_before_it_started_was_cancelled(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    mem.observe_events([KAMARAD], now=datetime(2026, 10, 14, 9, 0, tzinfo=PORTAL_TZ))
    mem.observe_events([], now=datetime(2026, 10, 14, 12, 0, tzinfo=PORTAL_TZ))
    assert mem.events() == []


async def test_a_timed_event_is_kept_from_its_start_minute(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    mem.observe_events([KAMARAD], now=_prague(15, 9))
    mem.observe_events([], now=_prague(15, 10))
    assert [e.id for e in mem.events()] == ["e1"]


async def test_an_all_day_event_is_kept_for_the_whole_of_its_first_day(
    hass: HomeAssistant,
) -> None:
    mem = _memory(hass)
    mem.observe_events([VOLNO], now=_prague(21, 12))
    mem.observe_events([], now=datetime(2026, 10, 22, 0, 30, tzinfo=PORTAL_TZ))
    assert [e.id for e in mem.events()] == ["e2"]


async def test_an_all_day_event_that_vanishes_the_day_before_was_cancelled(
    hass: HomeAssistant,
) -> None:
    mem = _memory(hass)
    mem.observe_events([VOLNO], now=_prague(21, 12))
    mem.observe_events([], now=datetime(2026, 10, 21, 23, 59, tzinfo=PORTAL_TZ))
    assert mem.events() == []


async def test_the_all_day_check_uses_the_prague_date(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    mem.observe_events([VOLNO], now=_prague(21, 12))
    mem.observe_events([], now=datetime(2026, 10, 21, 21, 30, tzinfo=dt_util.UTC))
    assert mem.events() == []

    mem.observe_events([VOLNO], now=_prague(21, 12))
    mem.observe_events([], now=datetime(2026, 10, 21, 22, 30, tzinfo=dt_util.UTC))
    assert [e.id for e in mem.events()] == ["e2"]


async def test_a_feed_event_replaces_its_stored_version(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    renamed = SchoolEvent("e1", "Přejmenováno", KAMARAD.start, KAMARAD.end)
    mem.observe_events([KAMARAD], now=_prague(14, 9))
    mem.observe_events([renamed], now=_prague(14, 10))
    assert [e.title for e in mem.events()] == ["Přejmenováno"]


async def test_events_that_ended_before_this_week_are_pruned(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    last_week = SchoolEvent("old", "Minulý týden", _prague(8, 10), _prague(8, 11))
    last_week_all_day = SchoolEvent("old2", "Minulý den", date(2026, 10, 9), date(2026, 10, 9))
    this_monday_all_day = SchoolEvent("mon", "Pondělí", date(2026, 10, 12), date(2026, 10, 12))
    mem.observe_events(
        [last_week, last_week_all_day, this_monday_all_day, KAMARAD], now=_prague(15, 9)
    )
    assert [e.id for e in mem.events()] == ["mon", "e1"]


async def test_fetched_weeks_are_kept_and_replaced_per_monday(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    mem.remember_lessons(this_week.lessons, this_week.periods, FRIDAY)
    assert [w.monday for w in mem.weeks()] == [date(2026, 10, 12)]
    assert mem.weeks()[0].lessons == this_week.lessons
    assert mem.weeks()[0].periods == FIVE_PERIODS

    mem.remember_lessons(this_week.lessons[:3], this_week.periods, FRIDAY)
    assert len(mem.weeks()[0].lessons) == 3


async def test_lessons_are_grouped_by_their_prague_monday(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    both = _lessons_in(date(2026, 10, 12)) + _lessons_in(date(2026, 10, 19), 2)
    mem.remember_lessons(both, FIVE_PERIODS, FRIDAY)
    assert [(w.monday, len(w.lessons)) for w in mem.weeks()] == [
        (date(2026, 10, 12), 1),
        (date(2026, 10, 19), 2),
    ]


async def test_periods_are_derived_from_the_lessons_when_the_page_has_none(
    hass: HomeAssistant,
) -> None:
    mem = _memory(hass)
    mem.remember_lessons(this_week.lessons, [], FRIDAY)
    assert [(p.number, p.start, p.end) for p in mem.weeks()[0].periods] == [
        (p.number, p.start, p.end) for p in FIVE_PERIODS[:5]
    ]


async def test_weeks_before_last_week_are_pruned(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    for monday in (date(2026, 9, 28), date(2026, 10, 5), date(2026, 10, 12)):
        mem.remember_lessons(_lessons_in(monday), FIVE_PERIODS, FRIDAY)
    assert [w.monday for w in mem.weeks()] == [date(2026, 10, 5), date(2026, 10, 12)]


async def test_an_empty_fetch_remembers_an_empty_week_with_its_periods(
    hass: HomeAssistant,
) -> None:
    mem = _memory(hass)
    mem.remember_lessons([], FIVE_PERIODS, FRIDAY)
    assert mem.weeks() == [WeekLessons(date(2026, 10, 12), [], FIVE_PERIODS)]


async def test_an_empty_fetch_does_not_wipe_a_remembered_week(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    mem.remember_lessons(this_week.lessons, this_week.periods, FRIDAY)
    listener = MagicMock()
    mem.async_add_listener(listener)

    mem.remember_lessons([], [], date(2026, 10, 17))

    assert [w.monday for w in mem.weeks()] == [date(2026, 10, 12)]
    assert mem.weeks()[0].lessons == this_week.lessons
    listener.assert_not_called()


async def test_a_remembered_empty_week_is_loaded_not_projected(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    mem.remember_lessons(this_week.lessons, this_week.periods, FRIDAY)
    holiday = date(2026, 10, 19)
    mem.remember_lessons([], FIVE_PERIODS, holiday)

    payload = build_payload(holiday, mem.weeks(), mem.events())

    first = payload["weeks"][0]
    assert (first["monday"], first["loaded"], first["projected"]) == ("2026-10-19", True, False)
    assert all(day["lessons"] == [] for day in first["days"])
    assert [p["number"] for p in first["periods"]] == [1, 2, 3, 4, 5]


async def test_nothing_remembered_means_an_unloaded_week(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    await mem.async_load()
    payload = build_payload(date(2026, 10, 17), mem.weeks(), mem.events())
    assert [w["loaded"] for w in payload["weeks"]] == [False, False]


async def test_listeners_fire_only_when_the_content_changed(hass: HomeAssistant) -> None:
    mem = _memory(hass)
    listener = MagicMock()
    unsubscribe = mem.async_add_listener(listener)

    mem.remember_lessons(this_week.lessons, this_week.periods, FRIDAY)
    mem.observe_events([KAMARAD], now=_prague(14, 9))
    assert listener.call_count == 2

    mem.remember_lessons(this_week.lessons, this_week.periods, FRIDAY)
    mem.observe_events([KAMARAD], now=_prague(14, 10))
    assert listener.call_count == 2

    mem.observe_events(
        [SchoolEvent("e1", "Jiný název", KAMARAD.start, KAMARAD.end)], _prague(14, 11)
    )
    assert listener.call_count == 3

    unsubscribe()
    mem.observe_events([], now=_prague(14, 12))
    assert listener.call_count == 3


async def test_weeks_and_events_survive_a_restart(
    hass: HomeAssistant, hass_storage: dict[str, object]
) -> None:
    mem = _memory(hass, "entry1")
    mem.remember_lessons(this_week.lessons, this_week.periods, FRIDAY)
    mem.observe_events([KAMARAD, VOLNO], now=_prague(14, 9))
    await _flush_delayed_save(hass)
    assert "edookit.entry1.week" in hass_storage

    fresh = _memory(hass, "entry1")
    await fresh.async_load()

    assert [w.monday for w in fresh.weeks()] == [date(2026, 10, 12)]
    assert fresh.weeks()[0].lessons[0].code == "Čj"
    assert fresh.weeks()[0].lessons == this_week.lessons
    assert fresh.weeks()[0].periods == FIVE_PERIODS
    assert fresh.events() == [KAMARAD, VOLNO]
    assert fresh.events()[0].start.tzinfo is not None
    assert type(fresh.events()[1].start) is date


async def test_a_second_entry_does_not_see_the_first_entrys_weeks(
    hass: HomeAssistant, hass_storage: dict[str, object]
) -> None:
    mem = _memory(hass, "entry1")
    mem.remember_lessons(this_week.lessons, this_week.periods, FRIDAY)
    await _flush_delayed_save(hass)

    other = _memory(hass, "entry2")
    await other.async_load()
    assert other.weeks() == []


@dataclass
class Portal:
    timetable: AsyncMock
    events: AsyncMock


@pytest.fixture
def portal() -> Iterator[Portal]:
    portal = Portal(
        timetable=AsyncMock(return_value=week(this_week.lessons, this_week.periods)),
        events=AsyncMock(return_value=[KAMARAD]),
    )
    with (
        patch("pyedookit.client.EdookitClient.get_timetable_week", new=portal.timetable),
        patch("pyedookit.client.EdookitClient.get_events", new=portal.events),
    ):
        yield portal


async def _setup(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> MockConfigEntry:
    freezer.move_to("2026-10-16 10:00:00+02:00")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="zs-example:user@example.com",
        data={CONF_SCHOOL: "zs-example", CONF_SESSION: SESSION.to_json()},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_feeds_the_memory_from_both_coordinators(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, portal: Portal
) -> None:
    entry = await _setup(hass, freezer)

    memory = entry.runtime_data.memory
    assert [w.monday for w in memory.weeks()] == [date(2026, 10, 12)]
    assert [e.id for e in memory.events()] == ["e1"]


async def test_a_later_poll_updates_the_memory_and_pings_listeners(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, portal: Portal
) -> None:
    entry = await _setup(hass, freezer)
    memory = entry.runtime_data.memory
    listener = MagicMock()
    memory.async_add_listener(listener)

    await entry.runtime_data.school.async_refresh()
    listener.assert_not_called()

    portal.events.return_value = [KAMARAD, VOLNO]
    await entry.runtime_data.school.async_refresh()
    assert listener.call_count == 1
    assert [e.id for e in memory.events()] == ["e1", "e2"]


async def test_a_failed_school_poll_does_not_drop_events(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, portal: Portal
) -> None:
    entry = await _setup(hass, freezer)
    memory = entry.runtime_data.memory

    portal.events.side_effect = EdookitConnectionError("down")
    with patch.object(memory, "observe_events") as observe:
        await entry.runtime_data.school.async_refresh()
    observe.assert_not_called()
    assert [e.id for e in memory.events()] == ["e1"]


async def test_a_failed_timetable_poll_is_not_remembered(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, portal: Portal
) -> None:
    entry = await _setup(hass, freezer)
    memory = entry.runtime_data.memory

    portal.timetable.side_effect = EdookitConnectionError("down")
    with patch.object(memory, "remember_lessons") as remember:
        await entry.runtime_data.timetable.async_refresh()
    remember.assert_not_called()
    assert [w.monday for w in memory.weeks()] == [date(2026, 10, 12)]


async def test_setup_survives_a_school_page_that_fails_from_the_start(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, portal: Portal
) -> None:
    portal.events.side_effect = EdookitConnectionError("down")
    entry = await _setup(hass, freezer)

    assert entry.state is ConfigEntryState.LOADED
    assert [w.monday for w in entry.runtime_data.memory.weeks()] == [date(2026, 10, 12)]
    assert entry.runtime_data.memory.events() == []


async def test_a_restarted_entry_starts_from_what_was_stored(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    portal: Portal,
    hass_storage: dict[str, object],
) -> None:
    entry = await _setup(hass, freezer)
    await _flush_delayed_save(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)

    portal.timetable.return_value = week([])
    portal.events.side_effect = EdookitConnectionError("down")
    freezer.move_to("2026-10-17 09:00:00+02:00")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    memory = entry.runtime_data.memory
    assert [w.monday for w in memory.weeks()] == [date(2026, 10, 12)]
    assert [e.id for e in memory.events()] == ["e1"]
