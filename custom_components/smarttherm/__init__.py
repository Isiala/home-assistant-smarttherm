"""OCSTAT SmartTherm integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmartThermClient
from .const import CONF_CLIENT_ID, CONF_TOKEN, CONF_USER_ID
from .coordinator import SmartThermCoordinator

PLATFORMS = [Platform.CLIMATE]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = SmartThermClient(async_get_clientsession(hass), entry.data[CONF_USER_ID],
                             entry.data[CONF_TOKEN], entry.data[CONF_CLIENT_ID])
    coordinator = SmartThermCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
