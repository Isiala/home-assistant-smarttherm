"""Climate entities for OCSTAT SmartTherm device families 08, 09 and 53."""
from __future__ import annotations

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Thermostat
from .const import DOMAIN, MODE_MANUAL, MODE_OVERRIDE, MODE_SCHEDULE, PRESETS, SUPPORTED_MODELS
from .coordinator import SmartThermCoordinator

PARALLEL_UPDATES = 0

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SmartThermCoordinator = entry.runtime_data
    discovered: set[str] = set()

    @callback
    def discover() -> None:
        devices = coordinator.data or {}
        new = [device_id for device_id, device in devices.items()
               if device.model in SUPPORTED_MODELS and device_id not in discovered]
        discovered.update(new)
        async_add_entities([SmartThermClimate(coordinator, device_id) for device_id in new])

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class SmartThermClimate(CoordinatorEntity[SmartThermCoordinator], ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT]
    _attr_preset_modes = list(PRESETS)
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE

    def __init__(self, coordinator: SmartThermCoordinator, device_id: str):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{device_id}"
        device = coordinator.data[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)}, name=device.name,
            manufacturer="OCSTAT", model=f"SmartTherm {device.model}",
        )

    @property
    def _device(self) -> Thermostat | None:
        return (self.coordinator.data or {}).get(self._device_id)

    @property
    def available(self) -> bool:
        device = self._device
        return super().available and device is not None and device.online

    @property
    def current_temperature(self) -> float | None:
        return self._device.temperature if self._device else None

    @property
    def target_temperature(self) -> float | None:
        return self._device.target if self._device else None

    @property
    def hvac_mode(self) -> HVACMode | None:
        if self._device is None:
            return None
        if self._device.mode in (MODE_SCHEDULE, MODE_OVERRIDE):
            return HVACMode.AUTO
        return HVACMode.HEAT if self._device.mode == MODE_MANUAL else None

    @property
    def hvac_action(self) -> HVACAction | None:
        if self._device is None or not self.available or self._device.heating is None:
            return None
        return HVACAction.HEATING if self._device.heating else HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        return next((name for name, mode in PRESETS.items()
                     if self._device is not None and self._device.mode == mode), None)

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None or self._device is None:
            raise HomeAssistantError("A target temperature and an available device are required")
        hvac_mode = kwargs.get("hvac_mode", self.hvac_mode)
        if hvac_mode not in self.hvac_modes:
            raise HomeAssistantError("Unsupported HVAC mode")
        # Match the app: changing a scheduled target selects an override;
        # changing a manual target preserves manual mode.
        mode = MODE_MANUAL if hvac_mode == HVACMode.HEAT else MODE_OVERRIDE
        await self.coordinator.async_control(self._device_id, mode, temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self.hvac_modes or self._device is None:
            raise HomeAssistantError("Unsupported HVAC mode or unavailable device")
        mode = MODE_SCHEDULE if hvac_mode == HVACMode.AUTO else MODE_MANUAL
        temperature = None if mode == MODE_SCHEDULE else self._device.target
        await self.coordinator.async_control(self._device_id, mode, temperature)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in PRESETS or self._device is None:
            raise HomeAssistantError("Unsupported preset or unavailable device")
        mode = PRESETS[preset_mode]
        temperature = None if mode == MODE_SCHEDULE else self._device.target
        await self.coordinator.async_control(self._device_id, mode, temperature)
