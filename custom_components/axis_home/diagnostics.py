"""Diagnostics: the rooms Axis declared and their values, without the login."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import AxisHomeConfigEntry
from .const import CONF_TOKEN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AxisHomeConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), {CONF_TOKEN}),
        "connected": data.client.connected,
        "server_version": data.client.server_version,
        "rooms": data.rooms,
        "values": data.values,
        "revisions": data.revs,
    }
