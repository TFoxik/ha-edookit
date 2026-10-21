from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import EdookitCoordinator
    from .memory import WeekMemory
    from .messages_coordinator import EdookitMessagesCoordinator
    from .school_coordinator import EdookitSchoolCoordinator


@dataclass(slots=True)
class EdookitRuntimeData:
    timetable: EdookitCoordinator
    school: EdookitSchoolCoordinator
    memory: WeekMemory
    messages: EdookitMessagesCoordinator


type EdookitConfigEntry = ConfigEntry[EdookitRuntimeData]
