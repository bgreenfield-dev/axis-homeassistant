"""Adding Axis Home by hand: the address and a pairing code."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.axis_home.client import AxisAuthError, AxisError
from custom_components.axis_home.const import DOMAIN

PAIR = "custom_components.axis_home.config_flow.pair"


async def start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_pairs_with_a_code(hass: HomeAssistant, fake_axis) -> None:
    flow = await start(hass)
    assert flow["type"] is FlowResultType.FORM
    with patch(PAIR, return_value="token-1"):
        done = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"url": "http://axis.example.com:8080/ ", "code": "ABCD2345"}
        )
    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert done["data"] == {"url": "http://axis.example.com:8080", "token": "token-1"}


async def test_says_which_field_is_wrong(hass: HomeAssistant, fake_axis) -> None:
    flow = await start(hass)
    with patch(PAIR, side_effect=AxisAuthError("bad")):
        bad = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"url": "http://axis.example.com:8080", "code": "WRONG"}
        )
    assert bad["errors"] == {"code": "bad_code"}
    with patch(PAIR, side_effect=AxisError("down")):
        down = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"url": "http://axis.example.com:8080", "code": "ABCD2345"}
        )
    assert down["errors"] == {"url": "cannot_connect"}
