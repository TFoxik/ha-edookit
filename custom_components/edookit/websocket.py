from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
from pyedookit import PORTAL_TZ

from .const import CONF_MESSAGES_ADMIN_ONLY, DOMAIN
from .data import EdookitConfigEntry
from .grades_payload import grades_payload
from .messages_payload import message_payload, summary_payload
from .week import build_payload


def async_register_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, _subscribe_week)
    websocket_api.async_register_command(hass, _subscribe_messages)
    websocket_api.async_register_command(hass, _get_message)
    websocket_api.async_register_command(hass, _subscribe_grades)
    websocket_api.async_register_command(hass, _mark_grade_seen)


def _next_prague_midnight(now: datetime) -> datetime:
    tomorrow = now.astimezone(PORTAL_TZ).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=PORTAL_TZ).astimezone(dt_util.UTC)


def _portal_today() -> date:
    return dt_util.now().astimezone(PORTAL_TZ).date()


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

    @callback
    def push() -> None:
        payload = build_payload(_portal_today(), memory.weeks(), memory.events())
        connection.send_message(websocket_api.event_message(msg_id, payload))

    _hold_subscription(hass, connection, msg_id, entry, push, memory.async_add_listener(push))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "edookit/messages/subscribe",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@callback
def _subscribe_messages(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    entry = _loaded_entry(hass, msg["entity_id"])
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown Edookit entity")
        return

    coordinator = entry.runtime_data.messages
    msg_id = msg["id"]

    @callback
    def push() -> None:
        payload = summary_payload(coordinator.data, _portal_today())
        connection.send_message(websocket_api.event_message(msg_id, payload))

    _hold_subscription(hass, connection, msg_id, entry, push, coordinator.async_add_listener(push))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "edookit/grades/subscribe",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@callback
def _subscribe_grades(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    entry = _loaded_entry(hass, msg["entity_id"])
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown Edookit entity")
        return

    coordinator = entry.runtime_data.grades
    msg_id = msg["id"]

    @callback
    def push() -> None:
        payload = grades_payload(coordinator.data, _portal_today(), coordinator.seen)
        connection.send_message(websocket_api.event_message(msg_id, payload))

    _hold_subscription(hass, connection, msg_id, entry, push, coordinator.async_add_listener(push))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "edookit/grades/seen",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("grade_id"): int,
    }
)
@websocket_api.async_response
async def _mark_grade_seen(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    entry = _loaded_entry(hass, msg["entity_id"])
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown Edookit entity")
        return
    if not await entry.runtime_data.grades.async_mark_seen(msg["grade_id"]):
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown grade")
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "edookit/messages/get",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("message_id"): int,
    }
)
@websocket_api.async_response
async def _get_message(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    entry = _loaded_entry(hass, msg["entity_id"])
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown Edookit entity")
        return
    if entry.options.get(CONF_MESSAGES_ADMIN_ONLY, False) and not connection.user.is_admin:
        connection.send_error(
            msg["id"], websocket_api.ERR_UNAUTHORIZED, "Only administrators can open messages"
        )
        return
    coordinator = entry.runtime_data.messages
    message_id: int = msg["message_id"]
    # Only ids the inbox listed: the card can't make HA fetch arbitrary pages.
    if not any(summary.id == message_id for summary in coordinator.data or []):
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown message")
        return
    try:
        message = await coordinator.session.async_call(
            lambda client: client.get_message(message_id)
        )
    except (UpdateFailed, ConfigEntryAuthFailed) as err:
        connection.send_error(msg["id"], "portal_error", str(err))
        return
    coordinator.async_mark_read(message_id)
    connection.send_result(msg["id"], message_payload(message))


@callback
def _hold_subscription(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg_id: int,
    entry: EdookitConfigEntry,
    push: CALLBACK_TYPE,
    unsubscribe_source: CALLBACK_TYPE,
) -> None:
    """Push now, on every source update and at each Prague midnight (the
    payloads carry the portal's today), until the socket ends the
    subscription or the entry unloads."""
    stopped = False
    cancel_midnight: CALLBACK_TYPE | None = None

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
    def cleanup() -> None:
        unsubscribe_source()
        if cancel_midnight is not None:
            cancel_midnight()

    @callback
    def stop(*, from_state_change: bool = False) -> None:
        nonlocal stopped
        if stopped:
            return
        stopped = True
        cleanup()
        if from_state_change:
            # HA is iterating the state-change callbacks right now; removing
            # one mid-loop would make it skip the next subscription's.
            hass.loop.call_soon(forget_entry_state)
        else:
            forget_entry_state()

    @callback
    def entry_state_changed() -> None:
        if stopped or entry.state is ConfigEntryState.LOADED:
            return
        connection.subscriptions.pop(msg_id, None)
        connection.send_message(websocket_api.event_message(msg_id, {"unloaded": True}))
        stop(from_state_change=True)

    forget_entry_state = entry.async_on_state_change(entry_state_changed)
    schedule()
    connection.subscriptions[msg_id] = stop
    connection.send_result(msg_id)
    push()
