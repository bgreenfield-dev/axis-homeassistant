"""A room's lights and its on/off settings, as switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisHomeConfigEntry
from .entity import AxisHomeEntity, declared


async def async_setup_entry(
    hass: HomeAssistant, entry: AxisHomeConfigEntry, add: AddEntitiesCallback
) -> None:
    add(AxisHomeSwitch(entry, room, decl) for room, decl in declared(entry, "switch"))


class AxisHomeSwitch(AxisHomeEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        v = self.value
        return None if v is None else bool(v)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(False)
