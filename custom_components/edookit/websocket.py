from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util
from pyedookit import PORTAL_TZ

from .const import DOMAIN
from .data import EdookitConfigEntry
from .week import build_payload


def async_register_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, _subscribe_week)


def _next_prague_midnight(now: datetime) -> datetime:
    tomorrow = now.astimezone(PORTAL_TZ).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=PORTAL_TZ).astimezone(dt_util.UTC)


def _loaded_entry(hass: HomeAssistant, entity_id: str) -> EdookitConfigEntry | None:
    entity = er.async_get(hass).async_get(entity_id)
    if entity is None or entity.platform != DOMAIN or entity.config_entry_id is None:
        return None
    entry = hass.config_entries.async_get_entry(entity.config_entry_id)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        return None
    return entry


@websocket_api.websocket_command(
    {
        vol.Required("type"): "edookit/week/subscribe",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@callback
def _subscribe_week(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    entry = _loaded_entry(hass, msg["entity_id"])
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown Edookit entity")
        return

    memory = entry.runtime_data.memory
    msg_id = msg["id"]
    cancel_midnight: CALLBACK_TYPE | None = None
    stopped = False

    @callback
    def push() -> None:
        today = dt_util.now().astimezone(PORTAL_TZ).date()
        payload = build_payload(today, memory.weeks(), memory.events())
        connection.send_message(websocket_api.event_message(msg_id, payload))

    @callback
    def midnight(_: datetime) -> None:
        schedule()
        push()

    @callback
    def schedule() -> None:
        nonlocal cancel_midnight
        cancel_midnight = async_track_point_in_utc_time(
            hass, midnight, _next_prague_midnight(dt_util.utcnow())
        )

    @callback
    def stop() -> None:
        nonlocal stopped
        if stopped:
            return
        stopped = True
        unsubscribe_memory()
        forget_entry_state()
        if cancel_midnight is not None:
            cancel_midnight()

    @callback
    def entry_state_changed() -> None:
        if entry.state is not ConfigEntryState.LOADED:
            connection.subscriptions.pop(msg_id, None)
            stop()

    unsubscribe_memory = memory.async_add_listener(push)
    forget_entry_state = entry.async_on_state_change(entry_state_changed)
    schedule()
    connection.subscriptions[msg_id] = stop
    connection.send_result(msg_id)
    push()
