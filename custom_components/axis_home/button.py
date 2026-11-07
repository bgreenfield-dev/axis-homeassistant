"""A room's buttons, like Resume (end every hold)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisHomeConfigEntry
from .entity import AxisHomeEntity, declared


async def async_setup_entry(
    hass: HomeAssistant, entry: AxisHomeConfigEntry, add: AddEntitiesCallback
) -> None:
    add(AxisHomeButton(entry, room, decl) for room, decl in declared(entry, "button"))


class AxisHomeButton(AxisHomeEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self._press()
