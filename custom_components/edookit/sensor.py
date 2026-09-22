from __future__ import annotations

from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import EdookitCoordinator
from .data import EdookitConfigEntry
from .entity_helpers import EdookitEntity, lesson_attributes, next_lesson
from .school_coordinator import EdookitSchoolCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: EdookitConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        [
            EdookitNextLessonSensor(runtime.timetable, entry),
            EdookitLessonsTodaySensor(runtime.timetable, entry),
            EdookitPaymentsDueSensor(runtime.school, entry),
        ]
    )


class EdookitNextLessonSensor(EdookitEntity[EdookitCoordinator], SensorEntity):
    key = "next_lesson"

    @property
    def native_value(self) -> str | None:
        lesson = next_lesson(self.coordinator.data.lessons, dt_util.now(), skip_cancelled=True)
        return lesson.subject if lesson else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        lesson = next_lesson(self.coordinator.data.lessons, dt_util.now(), skip_cancelled=True)
        if lesson is None:
            return {}
        return {**lesson_attributes(lesson), "end": dt_util.as_local(lesson.end).isoformat()}


class EdookitLessonsTodaySensor(EdookitEntity[EdookitCoordinator], SensorEntity):
    key = "lessons_today"
    _attr_native_unit_of_measurement = "lessons"

    @property
    def native_value(self) -> int:
        today = dt_util.now().date()
        return sum(
            1
            for ls in self.coordinator.data.lessons
            if not ls.is_cancelled and dt_util.as_local(ls.start).date() == today
        )


class EdookitPaymentsDueSensor(EdookitEntity[EdookitSchoolCoordinator], SensorEntity):
    key = "payments_due"
    _attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_value(self) -> Decimal | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.payments.remaining

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.payments.currency

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}
        payments = self.coordinator.data.payments
        return {
            "paid": float(payments.paid),
            "overpaid": float(payments.overpaid),
            "unpaid_requests": [
                {"title": r.title, "amount": float(r.amount)}
                for r in payments.requests
                if not r.is_paid
            ],
        }
