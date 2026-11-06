"""A room's scene, as a select."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisHomeConfigEntry
from .entity import AxisHomeEntity, declared


async def async_setup_entry(
    hass: HomeAssistant, entry: AxisHomeConfigEntry, add: AddEntitiesCallback
) -> None:
    add(AxisHomeSelect(entry, room, decl) for room, decl in declared(entry, "select"))


class AxisHomeSelect(AxisHomeEntity, SelectEntity):
    def __init__(self, entry, room, decl) -> None:
        super().__init__(entry, room, decl)
        self._attr_options = list(decl.get("options", []))

    @property
    def current_option(self) -> str | None:
        v = self.value
        return v if v in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        await self._send(option)
