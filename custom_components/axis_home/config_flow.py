"""Adding Axis Home: Axis's address and a one-time pairing code.

"home config ha link" in Axis starts this flow itself through HA's API and answers it, so
usually nobody types anything here. Adding it by hand works the same: the address HA reaches
Axis at, and a code from "server pair" in Axis.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import AxisAuthError, AxisError, pair, ws_url
from .const import CONF_CODE, CONF_TOKEN, CONF_URL, DOMAIN

SCHEMA = vol.Schema({vol.Required(CONF_URL): str, vol.Required(CONF_CODE): str})


def clean_url(url: str) -> str:
    return url.strip().rstrip("/")


class AxisHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = clean_url(user_input[CONF_URL])
            try:
                ws_url(url)
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                token = await pair(async_get_clientsession(self.hass), url, user_input[CONF_CODE])
            except AxisAuthError:
                errors[CONF_CODE] = "bad_code"
            except AxisError:
                errors[CONF_URL] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Axis", data={CONF_URL: url, CONF_TOKEN: token}
                )
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                token = await pair(
                    async_get_clientsession(self.hass), entry.data[CONF_URL], user_input[CONF_CODE]
                )
            except AxisAuthError:
                errors[CONF_CODE] = "bad_code"
            except AxisError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_CODE): str}),
            errors=errors,
        )
