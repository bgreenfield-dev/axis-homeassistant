"""Axis Home: Axis's rooms as Home Assistant devices.

Axis is the brain and the source of truth. Each room it declares is one device here, with
the entities Axis lists for it; their values come live from Axis, and a change made here is
sent to Axis, which checks it, saves it and sends the final value back.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .client import AxisAuthError, AxisClient, AxisError
from .const import CONF_TOKEN, CONF_URL, DOMAIN, HA_PROTOCOL, PLATFORMS, VERSION

_LOGGER = logging.getLogger(__name__)

SIGNAL_UPDATE = f"{DOMAIN}_update"


@dataclass
class AxisHomeData:
    """What one Axis server gave: its rooms, their values, and the connection."""

    client: AxisClient
    rooms: dict[str, dict[str, Any]] = field(default_factory=dict)
    values: dict[str, dict[str, Any]] = field(default_factory=dict)
    available: dict[str, bool] = field(default_factory=dict)
    revs: dict[str, str] = field(default_factory=dict)


type AxisHomeConfigEntry = ConfigEntry[AxisHomeData]


async def async_setup_entry(hass: HomeAssistant, entry: AxisHomeConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    holder: dict[str, AxisHomeData] = {}

    @callback
    def on_live(key: str, data: Any) -> None:
        state = holder.get("data")
        if state is None or not key.startswith("rooms-ha:") or not isinstance(data, dict):
            return
        room = key.split(":", 1)[1]
        rev = data.get("rev") or ""
        # The first value sets the revision these entities match. A new one means Axis's
        # entities for the room changed (a new scene, a light on the curve): rebuild.
        if not state.revs.get(room):
            state.revs[room] = rev
        elif rev and rev != state.revs[room]:
            hass.config_entries.async_schedule_reload(entry.entry_id)
            return
        state.values[room] = data.get("values") or {}
        state.available[room] = bool(data.get("available"))
        async_dispatcher_send(hass, f"{SIGNAL_UPDATE}_{entry.entry_id}")

    async def on_connected(on: bool) -> None:
        state = holder.get("data")
        if state is None:
            return
        if not on:
            for room in state.available:
                state.available[room] = False
        async_dispatcher_send(hass, f"{SIGNAL_UPDATE}_{entry.entry_id}")

    client = AxisClient(session, entry.data[CONF_URL], entry.data[CONF_TOKEN], on_live, on_connected)
    try:
        await client.start()
        hello = await client.call(
            "rooms.haHello", {"version": VERSION, "protocol": HA_PROTOCOL}
        )
    except AxisAuthError as err:
        await client.close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except AxisError as err:
        await client.close()
        raise ConfigEntryNotReady(str(err)) from err

    protocol = hello.get("protocol")
    if protocol != HA_PROTOCOL:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "protocol",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="protocol",
            translation_placeholders={
                "axis": str(hello.get("app", "?")),
                "ours": VERSION,
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, "protocol")

    data = AxisHomeData(client=client)
    for room in hello.get("rooms", []):
        data.rooms[room["id"]] = room
        data.available[room["id"]] = False
    holder["data"] = data
    entry.runtime_data = data

    await client.watch([f"rooms-ha:{rid}" for rid in data.rooms])
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AxisHomeConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.close()
    return unloaded
