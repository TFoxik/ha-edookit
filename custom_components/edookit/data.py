from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import EdookitCoordinator
    from .school_coordinator import EdookitSchoolCoordinator


@dataclass(slots=True)
class EdookitRuntimeData:
    timetable: EdookitCoordinator
    school: EdookitSchoolCoordinator
    capture_enabled: bool


type EdookitConfigEntry = ConfigEntry[EdookitRuntimeData]
