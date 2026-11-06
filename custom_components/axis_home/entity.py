"""What every Axis Home entity shares: its room's device, its value, and sending changes."""

from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import SIGNAL_UPDATE, AxisHomeConfigEntry, AxisHomeData
from .client import AxisError
from .const import DOMAIN

CATEGORIES = {"config": EntityCategory.CONFIG, "diagnostic": EntityCategory.DIAGNOSTIC}


def declared(entry: AxisHomeConfigEntry, platform: str) -> list[tuple[dict, dict]]:
    """Every (room, entity) Axis declared for one platform."""
    return [
        (room, ent)
        for room in entry.runtime_data.rooms.values()
        for ent in room.get("entities", [])
        if ent.get("platform") == platform
    ]


class AxisHomeEntity(Entity):
    """One entity of a room, as Axis declared it."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: AxisHomeConfigEntry, room: dict, decl: dict) -> None:
        self._entry = entry
        self._data: AxisHomeData = entry.runtime_data
        self._room_id: str = room["id"]
        self._key: str = decl["key"]
        self._decl = decl
        self._attr_unique_id = f"{entry.entry_id}_{self._room_id}_{self._key}"
        self._attr_name = decl.get("name")
        if decl.get("icon"):
            self._attr_icon = decl["icon"]
        if decl.get("category") in CATEGORIES:
            self._attr_entity_category = CATEGORIES[decl["category"]]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self._room_id}")},
            name=room.get("name"),
            manufacturer="Axis",
            model="Room",
            suggested_area=room.get("area"),
            sw_version=self._data.client.server_version,
        )

    @property
    def available(self) -> bool:
        return self._data.client.connected and self._data.available.get(self._room_id, False)

    @property
    def value(self) -> Any:
        return self._data.values.get(self._room_id, {}).get(self._key)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SIGNAL_UPDATE}_{self._entry.entry_id}", self._updated
            )
        )

    @callback
    def _updated(self) -> None:
        self.async_write_ha_state()

    async def _send(self, value: Any) -> None:
        """Sends a change to Axis, which checks it and answers the room's values as saved."""
        try:
            values = await self._data.client.call(
                "rooms.haSet", {"room": self._room_id, "key": self._key, "value": value}
            )
        except AxisError as err:
            raise HomeAssistantError(str(err)) from err
        self._take(values)

    async def _press(self) -> None:
        try:
            values = await self._data.client.call(
                "rooms.haPress", {"room": self._room_id, "key": self._key}
            )
        except AxisError as err:
            raise HomeAssistantError(str(err)) from err
        self._take(values)

    def _take(self, values: Any) -> None:
        if isinstance(values, dict) and isinstance(values.get("values"), dict):
            self._data.values[self._room_id] = values["values"]
        self.async_write_ha_state()
