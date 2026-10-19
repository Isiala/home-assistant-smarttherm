from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.components.climate import HVACMode
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smarttherm.api import SmartThermAuthError, SmartThermError, parse_thermostat
from custom_components.smarttherm.climate import SmartThermClimate
from custom_components.smarttherm.const import DOMAIN

TOKEN = 'unit-test-token-not-a-real-secret'
DATA = {'user_id':'1','token':TOKEN,'client_id':'test-client'}
DEVICE = parse_thermostat({'device_id':'000000000000','device_name':'Test thermostat',
    'device_type':'08','online':True,'inside_temparature':'162',
    'current_temprature':'135','autoTemp':'120','work_mode':'0','th_work':'0'})
DEVICES = {DEVICE.device_id:DEVICE}
CLIENT = 'custom_components.smarttherm.api.SmartThermClient'

async def setup_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id='1', data=DATA)
    entry.add_to_hass(hass)
    with patch(CLIENT+'.async_get_devices',return_value=DEVICES):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry

async def test_flow_masks_token_and_validates(hass):
    result=await hass.config_entries.flow.async_init(DOMAIN,context={'source':'user'})
    assert result['type']=='form'
    fields={str(key):value for key,value in result['data_schema'].schema.items()}
    assert fields['token'].config['type']=='password'
    with patch(CLIENT+'.async_get_devices',return_value=DEVICES), patch('custom_components.smarttherm.async_setup_entry',return_value=True):
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'user_id':'1','token':TOKEN})
    assert result['type']=='create_entry'
    assert result['data']['token']==TOKEN
    assert len(result['data']['client_id'])==13

@pytest.mark.parametrize('error,expected',[(SmartThermAuthError('rejected'),'invalid_auth'),(SmartThermError('offline'),'cannot_connect')])
async def test_flow_errors_do_not_expose_credentials(hass,error,expected):
    with patch(CLIENT+'.async_get_devices',side_effect=error):
        result=await hass.config_entries.flow.async_init(DOMAIN,context={'source':'user'},data={'user_id':'1','token':TOKEN})
    assert result['errors']=={'base':expected}
    assert TOKEN not in str(result)

async def test_setup_creates_climate_and_unloads(hass):
    entry=await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED
    entities=hass.states.async_all('climate')
    assert len(entities)==1
    state=entities[0]
    assert state.state=='auto'
    assert state.attributes['current_temperature']==16.2
    assert state.attributes['temperature']==12
    assert 'off' not in state.attributes['hvac_modes']
    assert TOKEN not in str(state)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

async def test_temperature_control_verifies_mode_and_target(hass):
    entry=await setup_entry(hass)
    coordinator=entry.runtime_data
    climate=SmartThermClimate(coordinator,DEVICE.device_id)
    after=replace(DEVICE,mode='1',configured_target=13.5)
    with patch.object(coordinator.client,'async_get_devices',side_effect=[DEVICES,{after.device_id:after}]), patch.object(coordinator.client,'async_set_target') as write:
        await climate.async_set_temperature(**{ATTR_TEMPERATURE:13.5})
    write.assert_awaited_once_with(DEVICE,'1',13.5)
    assert climate.target_temperature==13.5
    assert climate.preset_mode=='override'

async def test_manual_and_schedule_services(hass):
    entry=await setup_entry(hass)
    climate=SmartThermClimate(entry.runtime_data,DEVICE.device_id)
    with patch.object(entry.runtime_data,'async_control') as control:
        await climate.async_set_hvac_mode(HVACMode.HEAT)
        control.assert_awaited_with(DEVICE.device_id,'5',12)
        await climate.async_set_preset_mode('schedule')
        control.assert_awaited_with(DEVICE.device_id,'0',None)
        with pytest.raises(HomeAssistantError):await climate.async_set_hvac_mode(HVACMode.OFF)

async def test_offline_does_not_write(hass):
    entry=await setup_entry(hass)
    coordinator=entry.runtime_data
    with patch.object(coordinator.client,'async_get_devices',return_value={}), patch.object(coordinator.client,'async_set_target') as write:
        with pytest.raises(HomeAssistantError):await coordinator.async_control(DEVICE.device_id,'5',13.5)
    write.assert_not_awaited()

async def test_reauth_replaces_token(hass):
    entry=await setup_entry(hass)
    result=await hass.config_entries.flow.async_init(DOMAIN, context={'source':'reauth','entry_id':entry.entry_id},data=DATA)
    assert result['step_id']=='reauth_confirm'
    with patch(CLIENT+'.async_get_devices',return_value=DEVICES), patch.object(hass.config_entries,'async_reload',return_value=True):
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'token':'replacement-test-token'})
        await hass.async_block_till_done()
    assert result['type']=='abort'
    assert result['reason']=='reauth_successful'
    assert entry.data['token']=='replacement-test-token'
