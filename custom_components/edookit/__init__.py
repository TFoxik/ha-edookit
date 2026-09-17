from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pyedookit import EdookitClient

from .const import DOMAIN
from .coordinator import EdookitCoordinator, session_from_entry_data

PLATFORMS = ["calendar", "sensor", "event"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = session_from_entry_data(entry.data)
    client = EdookitClient(session)
    coordinator = EdookitCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
