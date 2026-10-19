"""Token-based setup, reauthentication, and reconfiguration."""
from __future__ import annotations

import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmartThermAuthError, SmartThermClient, SmartThermError
from .const import CONF_CLIENT_ID, CONF_TOKEN, CONF_USER_ID, DOMAIN, SUPPORTED_MODELS


def _schema(*, include_user: bool = False) -> vol.Schema:
    fields = {}
    if include_user:
        fields[vol.Required(CONF_USER_ID)] = selector.TextSelector()
    fields[vol.Required(CONF_TOKEN)] = selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )
    return vol.Schema(fields)


class SmartThermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, data: dict) -> str | None:
        user_id = data.get(CONF_USER_ID, "")
        token = data.get(CONF_TOKEN, "")
        if (not isinstance(user_id, str) or not user_id.isascii()
                or not user_id.isdigit() or not 1 <= len(user_id) <= 7
                or not isinstance(token, str) or not token.strip()):
            return "invalid_auth"
        client = SmartThermClient(async_get_clientsession(self.hass), user_id,
                                 token, data[CONF_CLIENT_ID])
        try:
            devices = await client.async_get_devices()
        except SmartThermAuthError:
            return "invalid_auth"
        except SmartThermError:
            return "cannot_connect"
        if not any(device.model in SUPPORTED_MODELS for device in devices.values()):
            return "no_devices"
        return None

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            data = {**user_input, CONF_CLIENT_ID: uuid.uuid4().hex[:13]}
            data[CONF_USER_ID] = str(data.get(CONF_USER_ID, "")).strip()
            data[CONF_TOKEN] = str(data.get(CONF_TOKEN, "")).strip()
            error = await self._validate(data)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(data[CONF_USER_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="SmartTherm", data=data)
        return self.async_show_form(step_id="user", data_schema=_schema(include_user=True), errors=errors)

    async def async_step_reauth(self, entry_data: dict) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> FlowResult:
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, CONF_TOKEN: user_input[CONF_TOKEN].strip()}
            error = await self._validate(data)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(step_id="reauth_confirm", data_schema=_schema(), errors=errors)

    async def async_step_reconfigure(self, user_input: dict | None = None) -> FlowResult:
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, CONF_TOKEN: user_input[CONF_TOKEN].strip()}
            error = await self._validate(data)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(step_id="reconfigure", data_schema=_schema(), errors=errors)
