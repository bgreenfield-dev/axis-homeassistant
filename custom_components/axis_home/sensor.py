"""A room's readings: who runs it, how often it agrees, lights held."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisHomeConfigEntry
from .entity import AxisHomeEntity, declared


async def async_setup_entry(
    hass: HomeAssistant, entry: AxisHomeConfigEntry, add: AddEntitiesCallback
) -> None:
    add(AxisHomeSensor(entry, room, decl) for room, decl in declared(entry, "sensor"))


class AxisHomeSensor(AxisHomeEntity, SensorEntity):
    def __init__(self, entry, room, decl) -> None:
        super().__init__(entry, room, decl)
        self._attr_native_unit_of_measurement = decl.get("unit")
        if decl.get("unit"):
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self.value
