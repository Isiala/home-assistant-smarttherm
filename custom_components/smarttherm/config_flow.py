"""Email/password or token setup, with password-free stored sessions."""
from __future__ import annotations

import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmartThermAuthError, SmartThermClient, SmartThermError
from .const import CONF_CLIENT_ID, CONF_TOKEN, CONF_USER_ID, DOMAIN, SUPPORTED_MODELS


def _secret() -> selector.TextSelector:
    return selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))


def _token_schema(*, include_user: bool) -> vol.Schema:
    fields = {}
    if include_user:
        fields[vol.Required(CONF_USER_ID)] = selector.TextSelector()
    fields[vol.Required(CONF_TOKEN)] = _secret()
    return vol.Schema(fields)


LOGIN_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL): selector.TextSelector(),
    vol.Required(CONF_PASSWORD): _secret(),
})


class SmartThermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def _existing_entry(self):
        source = self.context.get("source")
        if source == config_entries.SOURCE_REAUTH:
            return self._get_reauth_entry()
        if source == config_entries.SOURCE_RECONFIGURE:
            return self._get_reconfigure_entry()
        return None

    def _session_data(self, user_id: str, token: str) -> dict[str, str]:
        entry = self._existing_entry()
        return {
            CONF_USER_ID: user_id,
            CONF_TOKEN: token,
            CONF_CLIENT_ID: entry.data[CONF_CLIENT_ID] if entry else uuid.uuid4().hex[:13],
        }

    async def _validate(self, data: dict) -> str | None:
        user_id = data.get(CONF_USER_ID, "")
        token = data.get(CONF_TOKEN, "")
        if (not isinstance(user_id, str) or not user_id.isascii()
                or not user_id.isdigit() or not 1 <= len(user_id) <= 7
                or not isinstance(token, str) or not token.strip()):
            return "invalid_auth"
        entry = self._existing_entry()
        if entry and user_id != entry.data[CONF_USER_ID]:
            return "wrong_account"
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

    async def _finish(self, data: dict) -> FlowResult:
        entry = self._existing_entry()
        if entry:
            # Replace with the allowlisted session, not the login input/raw response.
            return self.async_update_reload_and_abort(entry, data=data)
        await self.async_set_unique_id(data[CONF_USER_ID])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="SmartTherm", data=data)

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        return self.async_show_menu(step_id="user", menu_options=["login", "token"])

    async def async_step_login(self, user_input: dict | None = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                session = await SmartThermClient.async_login(
                    async_get_clientsession(self.hass),
                    user_input.get(CONF_EMAIL, ""), user_input.get(CONF_PASSWORD, ""),
                )
            except SmartThermAuthError:
                errors["base"] = "invalid_auth"
            except SmartThermError:
                errors["base"] = "cannot_connect"
            else:
                data = self._session_data(session[CONF_USER_ID], session[CONF_TOKEN])
                error = await self._validate(data)
                if error:
                    errors["base"] = error
                else:
                    return await self._finish(data)
        return self.async_show_form(step_id="login", data_schema=LOGIN_SCHEMA, errors=errors)

    async def async_step_token(self, user_input: dict | None = None) -> FlowResult:
        errors = {}
        entry = self._existing_entry()
        if user_input is not None:
            raw_id = entry.data[CONF_USER_ID] if entry else str(user_input.get(CONF_USER_ID, "")).strip()
            user_id = str(int(raw_id)) if raw_id.isascii() and raw_id.isdigit() and 1 <= len(raw_id) <= 7 else raw_id
            data = self._session_data(user_id, str(user_input.get(CONF_TOKEN, "")).strip())
            error = await self._validate(data)
            if error:
                errors["base"] = error
            else:
                return await self._finish(data)
        return self.async_show_form(step_id="token", data_schema=_token_schema(include_user=entry is None), errors=errors)

    async def async_step_reauth(self, entry_data: dict) -> FlowResult:
        return await self.async_step_user()

    async def async_step_reconfigure(self, user_input: dict | None = None) -> FlowResult:
        return await self.async_step_user()
