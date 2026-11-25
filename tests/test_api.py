import asyncio
import json
from unittest.mock import patch

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.smarttherm.api import (
    SmartThermAuthError, SmartThermClient, SmartThermError, SmartThermWriteUnknown,
    encode_temperature, parse_thermostat,
)
from custom_components.smarttherm.const import BASE_URL

ROW={'device_id':'000000000000','device_name':'Test','device_type':'08','online':True,
     'inside_temparature':'162','current_temprature':'135','autoTemp':'120','work_mode':'5','th_work':'1'}

@pytest.mark.parametrize('value',[None,True,'nan','inf',4.5,35.5,13.2,'secret-untrusted-value'])
def test_invalid_target(value):
    with pytest.raises(SmartThermError) as exc:encode_temperature(value)
    assert 'secret-untrusted-value' not in str(exc.value)

async def test_read_and_parse(hass,aioclient_mock):
    aioclient_mock.post(BASE_URL+'getDeviceListNew',json={'devices':[ROW]})
    client=SmartThermClient(async_get_clientsession(hass),'1','fake-token','test-client')
    devices=await client.async_get_devices()
    device=devices['000000000000']
    assert device.temperature==16.2
    assert device.target==13.5
    assert device.heating is True
    assert '000000000000' not in repr(device)

async def test_model_53_identifier(hass,aioclient_mock):
    row={**ROW,'device_id':'&ABCD123E456','device_type':'53'}
    aioclient_mock.post(BASE_URL+'getDeviceListNew',json={'devices':[row]})
    client=SmartThermClient(async_get_clientsession(hass),'1','fake-token','test-client')
    devices=await client.async_get_devices()
    assert devices['&ABCD123E456'].model=='53'

@pytest.mark.parametrize('identifier',['','12345 678901','ab\tc','x'*33,'caf\u00e9'])
def test_invalid_identifier(identifier):
    with pytest.raises(SmartThermError):parse_thermostat({**ROW,'device_id':identifier})

async def test_expired_token(hass,aioclient_mock):
    aioclient_mock.post(BASE_URL+'getDeviceListNew',json={'statu':False,'error_code':4,'message':'sensitive-server-text'})
    client=SmartThermClient(async_get_clientsession(hass),'1','fake-token','test-client')
    with pytest.raises(SmartThermAuthError) as exc:await client.async_get_devices()
    assert 'sensitive-server-text' not in str(exc.value)

async def test_redirect_does_not_forward_credentials(hass,aioclient_mock):
    aioclient_mock.post(BASE_URL+'getDeviceListNew',status=302,headers={'Location':'https://example.org/'})
    client=SmartThermClient(async_get_clientsession(hass),'1','fake-token','test-client')
    with pytest.raises(SmartThermError):await client.async_get_devices()
    assert aioclient_mock.call_count==1

async def test_control_payload_and_only_one_write(hass,aioclient_mock):
    aioclient_mock.post(BASE_URL+'setThermostatWorkModeNew',json={'statu':True})
    client=SmartThermClient(async_get_clientsession(hass),'1','fake-token','test-client')
    await client.async_set_target(parse_thermostat(ROW),'5',13.5)
    request=aioclient_mock.mock_calls[0][2]
    assert request['current_temprature']=='135'
    assert request['work_mode']=='5'
    assert request['device_id']==ROW['device_id']
    assert 4100 <= int(request['messageId'],16) < 32767
    assert aioclient_mock.call_count==1

async def test_model_53_control_payload(hass,aioclient_mock):
    aioclient_mock.post(BASE_URL+'setThermostatWorkModeNew',json={'statu':True})
    client=SmartThermClient(async_get_clientsession(hass),'1','fake-token','test-client')
    await client.async_set_target(parse_thermostat({**ROW,'device_id':'&ABCD123E456','device_type':'53'}),'5',21.5)
    request=aioclient_mock.mock_calls[0][2]
    assert request['device_id']=='&ABCD123E456'
    assert request['current_temprature']=='215'

async def test_uncertain_write_not_retried(hass,aioclient_mock):
    aioclient_mock.post(BASE_URL+'setThermostatWorkModeNew',exc=asyncio.TimeoutError)
    client=SmartThermClient(async_get_clientsession(hass),'1','fake-token','test-client')
    with pytest.raises(SmartThermWriteUnknown):await client.async_set_target(parse_thermostat(ROW),'5',13.5)
    assert aioclient_mock.call_count==1


async def test_login_returns_only_id_and_token(hass,aioclient_mock):
    aioclient_mock.post(BASE_URL+'login',json={'statu':True,'user':{'id':1,'token':'login-test-token','password':'server-password-not-to-save','email':'unit-test@example.invalid'}})
    result=await SmartThermClient.async_login(async_get_clientsession(hass),' unit-test@example.invalid ',' password with spaces ')
    assert result=={'user_id':'1','token':'login-test-token'}
    request=aioclient_mock.mock_calls[0][2]
    assert request=={'email':'unit-test@example.invalid','password':' password with spaces '}
    assert aioclient_mock.call_count==1


@pytest.mark.parametrize('response', [
    {'statu':False,'error_code':2,'message':'untrusted-server-text'},
    {'statu':True,'user':{}},
    {'statu':True,'user':{'id':False,'token':'t'}},
    {'statu':True,'user':{'id':'1','token':''}},
])
async def test_login_rejection_and_incomplete_sessions(hass,aioclient_mock,response):
    aioclient_mock.post(BASE_URL+'login',json=response)
    with pytest.raises(SmartThermAuthError) as exc:
        await SmartThermClient.async_login(async_get_clientsession(hass),'unit-test@example.invalid','test-password-only')
    assert 'untrusted-server-text' not in str(exc.value)
    assert 'test-password-only' not in str(exc.value)


async def test_login_redirect_does_not_forward_password(hass,aioclient_mock):
    aioclient_mock.post(BASE_URL+'login',status=302,headers={'Location':'https://example.invalid/'})
    with pytest.raises(SmartThermError):
        await SmartThermClient.async_login(async_get_clientsession(hass),'unit-test@example.invalid','test-password-only')
    assert aioclient_mock.call_count==1
