from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from custom_components.edookit.capture import PageCapture

EMPTY = '<section class="content"><h1>Úkoly</h1><p>Žádné úkoly</p></section>'
WITH_ITEM = '<section class="content"><h1>Úkoly</h1><p>Žádné úkoly</p><div>Čtení</div></section>'


class FakeSession:
    """Stands in for EdookitSessionManager: hands itself over as the client."""

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    async def async_call(self, fetch):
        return await fetch(self)

    async def fetch_page(self, name: str) -> str:
        return self.pages[name]


def _pages(assignments: str = EMPTY) -> dict[str, str]:
    return {"assignments": assignments, "exams": EMPTY, "consents": EMPTY}


def _notification(hass: HomeAssistant) -> dict:
    return hass.data["persistent_notification"]["edookit_capture"]


async def test_first_run_only_records_baselines(hass: HomeAssistant, tmp_path: Path) -> None:
    capture = PageCapture(hass, "entry1", tmp_path)

    assert await capture.async_run(FakeSession(_pages())) == []
    assert list(tmp_path.iterdir()) == []


async def test_changed_page_is_saved_and_notified(
    hass: HomeAssistant, tmp_path: Path, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/Prague")
    freezer.move_to("2026-09-22 10:00:00+02:00")
    capture = PageCapture(hass, "entry1", tmp_path)
    await capture.async_run(FakeSession(_pages()))

    captured = await capture.async_run(FakeSession(_pages(assignments=WITH_ITEM)))

    assert captured == ["assignments"]
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["assignments-20260922-1000.html"]
    assert (tmp_path / files[0]).read_text() == WITH_ITEM
    assert (tmp_path / files[0]).stat().st_mode & 0o777 == 0o600
    assert "assignments" in _notification(hass)["message"]
    assert await capture.async_run(FakeSession(_pages(assignments=WITH_ITEM))) == []


async def test_at_most_one_capture_per_page_per_day(
    hass: HomeAssistant, tmp_path: Path, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/Prague")
    freezer.move_to("2026-09-22 10:00:00+02:00")
    capture = PageCapture(hass, "entry1", tmp_path)
    await capture.async_run(FakeSession(_pages()))
    await capture.async_run(FakeSession(_pages(assignments=WITH_ITEM)))

    freezer.move_to("2026-09-22 13:00:00+02:00")
    again = WITH_ITEM.replace("Čtení", "Psaní")
    assert await capture.async_run(FakeSession(_pages(assignments=again))) == []

    freezer.move_to("2026-09-23 10:00:00+02:00")
    assert await capture.async_run(FakeSession(_pages(assignments=again))) == ["assignments"]


async def test_baselines_survive_a_restart(hass: HomeAssistant, tmp_path: Path) -> None:
    await PageCapture(hass, "entry1", tmp_path).async_run(FakeSession(_pages()))

    restarted = PageCapture(hass, "entry1", tmp_path)

    assert await restarted.async_run(FakeSession(_pages(assignments=WITH_ITEM))) == ["assignments"]


async def test_one_failing_page_does_not_stop_the_others(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    from homeassistant.helpers.update_coordinator import UpdateFailed

    class FlakySession(FakeSession):
        async def fetch_page(self, name: str) -> str:
            if name == "exams":
                raise UpdateFailed("down")
            return await super().fetch_page(name)

    capture = PageCapture(hass, "entry1", tmp_path)
    await capture.async_run(FlakySession(_pages()))

    assert await capture.async_run(FlakySession(_pages(assignments=WITH_ITEM))) == ["assignments"]


async def test_failed_write_does_not_raise_or_stop_other_pages(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    capture = PageCapture(hass, "entry1", tmp_path)
    await capture.async_run(FakeSession(_pages()))
    changed = {name: WITH_ITEM for name in ("assignments", "exams", "consents")}

    def flaky_write(path: Path, html: str) -> None:
        if path.name.startswith("assignments"):
            raise OSError("disk full")
        path.write_text(html)

    with patch("custom_components.edookit.capture._write", side_effect=flaky_write):
        captured = await capture.async_run(FakeSession(changed))

    assert captured == ["exams", "consents"]


async def test_error_pages_are_not_captured_and_keep_the_baseline(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    # A 5xx or maintenance page has no portal content section.
    maintenance = "<html><body><h1>Probíhá údržba</h1></body></html>"
    capture = PageCapture(hass, "entry1", tmp_path)
    await capture.async_run(FakeSession(_pages()))

    assert await capture.async_run(FakeSession(_pages(assignments=maintenance))) == []
    assert await capture.async_run(FakeSession(_pages())) == []
    assert list(tmp_path.iterdir()) == []


async def test_error_page_is_not_used_as_a_first_baseline(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    maintenance = "<html><body><h1>Probíhá údržba</h1></body></html>"
    capture = PageCapture(hass, "entry1", tmp_path)
    await capture.async_run(FakeSession(_pages(assignments=maintenance)))

    assert await capture.async_run(FakeSession(_pages())) == []
