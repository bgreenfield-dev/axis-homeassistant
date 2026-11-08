"""Axis Home's entities in Home Assistant: one device per room, live values, changes sent to Axis."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.axis_home.const import DOMAIN

from .conftest import ROOM_VALUES


async def setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="Axis", data={"url": "http://axis.example.com:8080", "token": "t"}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def live(hass: HomeAssistant, client, values=ROOM_VALUES, rev="r1", available=True) -> None:
    client.on_live("rooms-ha:bedroom", {"rev": rev, "values": values, "available": available})
    await hass.async_block_till_done()


async def test_a_room_is_a_device_with_its_entities(hass: HomeAssistant, fake_axis) -> None:
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    client = fake_axis.instances[0]
    assert client.watched == ["rooms-ha:bedroom"]
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_bedroom")})
    assert device is not None and device.name == "Bedroom" and device.manufacturer == "Axis"
    # Unavailable until Axis sends the room's values.
    assert hass.states.get("select.bedroom_scene").state == "unavailable"
    await live(hass, client)
    assert hass.states.get("select.bedroom_scene").state == "Day"
    assert hass.states.get("switch.bedroom_lights").state == "on"
    assert float(hass.states.get("number.bedroom_hand_hold").state) == 30
    assert hass.states.get("sensor.bedroom_lights_held").state == "1"
    assert hass.states.get("button.bedroom_resume") is not None


async def test_a_change_goes_to_axis_and_its_answer_is_kept(hass: HomeAssistant, fake_axis) -> None:
    await setup(hass)
    client = fake_axis.instances[0]
    await live(hass, client)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.bedroom_scene", "option": "Night"}, blocking=True
    )
    assert ("rooms.haSet", {"room": "bedroom", "key": "scene", "value": "Night"}) in client.calls
    assert hass.states.get("select.bedroom_scene").state == "Night"
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.bedroom_lights"}, blocking=True
    )
    assert ("rooms.haSet", {"room": "bedroom", "key": "lights", "value": False}) in client.calls
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.bedroom_resume"}, blocking=True
    )
    assert ("rooms.haPress", {"room": "bedroom", "key": "resume"}) in client.calls


async def test_disconnecting_makes_the_room_unavailable(hass: HomeAssistant, fake_axis) -> None:
    await setup(hass)
    client = fake_axis.instances[0]
    await live(hass, client)
    await client.on_connected(False)
    await hass.async_block_till_done()
    assert hass.states.get("select.bedroom_scene").state == "unavailable"


async def test_new_entities_from_axis_reload_the_entry(hass: HomeAssistant, fake_axis) -> None:
    entry = await setup(hass)
    client = fake_axis.instances[0]
    await live(hass, client, rev="r1")
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await live(hass, client, rev="r2")
    reload.assert_called_once_with(entry.entry_id)


async def test_an_older_axis_raises_a_repair(hass: HomeAssistant, fake_axis) -> None:
    fake_axis.hello = {"protocol": 99, "app": "0.30.0", "rooms": []}
    await setup(hass)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "protocol") is not None


async def test_the_notify_entity_sends_a_notice(hass: HomeAssistant, fake_axis) -> None:
    await setup(hass)
    client = fake_axis.instances[0]
    await hass.services.async_call(
        "notify",
        "send_message",
        {"entity_id": "notify.axis", "title": "Washer done", "message": "Cycle finished"},
        blocking=True,
    )
    assert any(m == "rooms.haNotify" for m, _ in client.calls)
