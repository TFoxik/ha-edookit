from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import EdookitCoordinator
    from .school_coordinator import EdookitSchoolCoordinator
    from .session_manager import EdookitSessionManager


@dataclass(slots=True)
class EdookitRuntimeData:
    session: EdookitSessionManager
    timetable: EdookitCoordinator
    school: EdookitSchoolCoordinator


type EdookitConfigEntry = ConfigEntry[EdookitRuntimeData]
