from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypedDict

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
from pyedookit import CAPTURE_PAGES, EdookitClient, content_fingerprint

from .const import DOMAIN
from .session_manager import EdookitSessionManager

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1


class _CaptureState(TypedDict):
    baselines: dict[str, str]
    captured_on: dict[str, str]


def _page_fetcher(name: str) -> Callable[[EdookitClient], Awaitable[str]]:
    return lambda client: client.fetch_page(name)


def _write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


class PageCapture:
    """Saves portal pages that have no parser yet once their content changes.

    The first fingerprint seen for a page is its baseline (today: the empty
    page). A later, different fingerprint means real items appeared, so the
    HTML is saved for building a parser from real markup instead of guessing.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str, directory: Path) -> None:
        self._hass = hass
        self._directory = directory
        self._store: Store[_CaptureState] = Store(
            hass, _STORAGE_VERSION, f"{DOMAIN}.capture.{entry_id}"
        )

    async def async_run(self, session: EdookitSessionManager) -> list[str]:
        state = await self._store.async_load() or {"baselines": {}, "captured_on": {}}
        now = dt_util.now()
        today = now.date().isoformat()
        captured: list[str] = []

        for name in CAPTURE_PAGES:
            if name in state["baselines"] and state["captured_on"].get(name) == today:
                continue
            try:
                html = await session.async_call(_page_fetcher(name))
            except UpdateFailed as err:
                _LOGGER.warning("Could not fetch %s for capture: %s", name, err)
                continue
            if (fingerprint := content_fingerprint(html)) is None:
                _LOGGER.debug("Skipping %s for capture: not a portal page", name)
                continue
            baseline = state["baselines"].get(name)
            if baseline is None:
                state["baselines"][name] = fingerprint
                continue
            if fingerprint == baseline:
                continue
            path = self._directory / f"{name}-{now:%Y%m%d-%H%M}.html"
            try:
                await self._hass.async_add_executor_job(_write, path, html)
            except OSError as err:
                _LOGGER.warning("Could not save captured %s page to %s: %s", name, path, err)
                continue
            state["baselines"][name] = fingerprint
            state["captured_on"][name] = today
            captured.append(name)

        await self._store.async_save(state)
        if captured:
            persistent_notification.async_create(
                self._hass,
                f"New content appeared on the Edookit {', '.join(captured)} page(s) and was "
                f"saved to `{self._directory}`. Share the file so support for it can be "
                "built. It contains personal data such as names and messages; remove them "
                "before sharing.",
                title="Edookit: page captured",
                notification_id=f"{DOMAIN}_capture",
            )
        return captured
