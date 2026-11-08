"""Axis as a notify entity: notify.send_message sends a notice to Axis."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SIGNAL_UPDATE, AxisHomeConfigEntry, send_notice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: AxisHomeConfigEntry, add: AddEntitiesCallback
) -> None:
    add([AxisNotify(entry)])


class AxisNotify(NotifyEntity):
    """Sends a notice to Axis, from its Home Assistant source."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = None
    _attr_translation_key = "axis"

    def __init__(self, entry: AxisHomeConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_notify"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Axis",
            manufacturer="Axis",
            model="Server",
            sw_version=entry.runtime_data.client.server_version,
        )

    @property
    def available(self) -> bool:
        return self._entry.runtime_data.client.connected

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SIGNAL_UPDATE}_{self._entry.entry_id}", self._updated
            )
        )

    @callback
    def _updated(self) -> None:
        self.async_write_ha_state()

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await send_notice(self._entry, {"message": message, "title": title})
