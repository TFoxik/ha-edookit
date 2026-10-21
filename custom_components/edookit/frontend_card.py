from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

CARD_FILES = ("edookit-timetable-card.js", "edookit-messages-card.js")


def _digests(frontend: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((frontend / name).read_bytes()).hexdigest()[:8] for name in CARD_FILES
    }


async def async_register_card(hass: HomeAssistant) -> None:
    frontend = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"/{DOMAIN}/{name}", str(frontend / name), True) for name in CARD_FILES]
    )
    integration = await async_get_integration(hass, DOMAIN)
    # The files are served with long cache headers, so the URL has to change
    # whenever a file does, not only when the integration version is bumped.
    digests = await hass.async_add_executor_job(_digests, frontend)
    for name in CARD_FILES:
        add_extra_js_url(hass, f"/{DOMAIN}/{name}?v={integration.version}-{digests[name]}")
