from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_SCHOOL, CONF_SESSION
from .data import EdookitConfigEntry

TO_REDACT = {CONF_SESSION, CONF_SCHOOL, "username", "password"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EdookitConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data.timetable
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "lesson_count": len(coordinator.data.lessons),
    }
