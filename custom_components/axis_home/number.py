"""A room's numbers: hand hold, weather dimming and each curve light's levels."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisHomeConfigEntry
from .entity import AxisHomeEntity, declared


async def async_setup_entry(
    hass: HomeAssistant, entry: AxisHomeConfigEntry, add: AddEntitiesCallback
) -> None:
    add(AxisHomeNumber(entry, room, decl) for room, decl in declared(entry, "number"))


class AxisHomeNumber(AxisHomeEntity, NumberEntity):
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry, room, decl) -> None:
        super().__init__(entry, room, decl)
        self._attr_native_min_value = decl.get("min", 0)
        self._attr_native_max_value = decl.get("max", 100)
        self._attr_native_step = decl.get("step", 1)
        self._attr_native_unit_of_measurement = decl.get("unit")

    @property
    def native_value(self) -> float | None:
        v = self.value
        return None if v is None else float(v)

    async def async_set_native_value(self, value: float) -> None:
        await self._send(value)
