from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

CARD_FILE = "edookit-timetable-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILE}"


async def async_register_card(hass: HomeAssistant) -> None:
    path = Path(__file__).parent / "frontend" / CARD_FILE
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), True)])
    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
