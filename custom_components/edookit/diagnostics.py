from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_CAPTURE_PAGES, CONF_SCHOOL, CONF_SESSION
from .data import EdookitConfigEntry

TO_REDACT = {CONF_SESSION, CONF_SCHOOL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EdookitConfigEntry
) -> dict[str, Any]:
    runtime = entry.runtime_data
    coordinator = runtime.timetable
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "lesson_count": len(coordinator.data.lessons),
        "school_last_update_success": runtime.school.last_update_success,
        "capture_enabled": entry.options.get(CONF_CAPTURE_PAGES, False),
        "event_count": len(runtime.school.data.events) if runtime.school.data else 0,
        "message_count": len(runtime.messages.data or []),
        "unread_message_count": sum(m.unread for m in runtime.messages.data or []),
    }
