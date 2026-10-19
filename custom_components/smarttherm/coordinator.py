"""Account-wide polling and serialized temperature controls."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SmartThermAuthError, SmartThermClient, SmartThermError, Thermostat
from .const import DOMAIN, MODE_SCHEDULE, SUPPORTED_MODELS

_LOGGER = logging.getLogger(__name__)

class SmartThermCoordinator(DataUpdateCoordinator[dict[str, Thermostat]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SmartThermClient):
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN,
                         update_interval=timedelta(seconds=60), always_update=False)
        self.client = client
        self._control_lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, Thermostat]:
        try:
            return await self.client.async_get_devices()
        except SmartThermAuthError as exc:
            raise ConfigEntryAuthFailed("Supply a valid SmartTherm token") from exc
        except SmartThermError as exc:
            raise UpdateFailed("Unable to refresh SmartTherm devices") from exc

    async def async_control(self, device_id: str, mode: str, temperature: float | None) -> None:
        async with self._control_lock:
            await self.async_refresh()
            device = self.data.get(device_id) if self.last_update_success and self.data else None
            if device is None or not device.online:
                raise HomeAssistantError("Thermostat is unavailable; command was not sent")
            if device.model not in SUPPORTED_MODELS:
                raise HomeAssistantError("This thermostat model is not supported for control")
            try:
                await self.client.async_set_target(device, mode, temperature)
            except SmartThermAuthError as exc:
                self.config_entry.async_start_reauth(self.hass)
                raise HomeAssistantError("SmartTherm token expired; update it in integration settings") from exc
            except SmartThermError as exc:
                await self.async_request_refresh()
                raise HomeAssistantError(str(exc)) from None
            for delay in (0, 1, 2, 4):
                if delay:
                    await asyncio.sleep(delay)
                await self.async_refresh()
                current = self.data.get(device_id) if self.last_update_success and self.data else None
                if (current is not None and current.online and current.mode == mode
                        and (mode == MODE_SCHEDULE or current.target == temperature)):
                    return
            raise HomeAssistantError(
                "Command sent but the cloud has not confirmed the requested state; refresh before retrying"
            )
