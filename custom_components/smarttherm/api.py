"""Async SmartTherm API. No credentials, payloads, or server messages are logged."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import json
import math
import secrets

import aiohttp

from .const import BASE_URL, MODE_MANUAL, MODE_OVERRIDE, MODE_SCHEDULE

class SmartThermError(Exception):
    """Request failed or the cloud response could not be validated."""

class SmartThermAuthError(SmartThermError):
    """Session expired or was rejected."""

class SmartThermWriteUnknown(SmartThermError):
    """A write was attempted but its outcome is unknown. Do not retry it."""

@dataclass(frozen=True)
class Thermostat:
    device_id: str = field(repr=False)
    name: str
    model: str
    online: bool
    temperature: float | None
    configured_target: float | None
    automatic_target: float | None
    mode: str
    heating: bool | None

    @property
    def target(self) -> float | None:
        if self.mode == MODE_SCHEDULE:
            return self.automatic_target
        if self.mode in (MODE_MANUAL, MODE_OVERRIDE):
            return self.configured_target
        return None


def encode_temperature(value: float) -> str:
    try:
        number = Decimal(str(value))
        if (not number.is_finite() or not Decimal(5) <= number <= Decimal(35)
                or number * 2 != (number * 2).to_integral_value()):
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise SmartThermError("Choose a temperature from 5–35°C in 0.5°C steps") from None
    return str(int(number * 10))


def _temperature(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        number = float(value) / 10
        if not math.isfinite(number):
            raise ValueError
        return number
    except (ValueError, TypeError):
        raise SmartThermError("Invalid temperature in cloud response") from None


def parse_thermostat(value: dict) -> Thermostat:
    identifier = str(value.get("device_id", ""))
    # Families 08/09 use 12 digits; family 53 (e.g. Delta ST2602WIFIRF-5G) uses
    # identifiers such as "&ABCD123E456", so accept any printable ASCII token.
    if (not 1 <= len(identifier) <= 32 or not identifier.isascii() or not identifier.isprintable()
            or any(c.isspace() for c in identifier)):
        raise SmartThermError("Invalid device identifier in cloud response")
    state = str(value.get("th_work", ""))
    return Thermostat(
        device_id=identifier, name=str(value.get("device_name") or "SmartTherm thermostat"),
        model=str(value.get("device_type", "")), online=value.get("online") is True,
        temperature=_temperature(value.get("inside_temparature")),
        configured_target=_temperature(value.get("current_temprature")),
        automatic_target=_temperature(value.get("autoTemp")),
        mode=str(value.get("work_mode", "")),
        heating=state == "1" if state in ("0", "1") else None,
    )


class SmartThermClient:
    def __init__(self, session: aiohttp.ClientSession, user_id: str, token: str, client_id: str):
        self._session = session
        self._user_id = user_id
        self._token = token
        self._client_id = client_id

    async def _post(self, operation: str, extra: dict[str, str], *, write: bool = False) -> dict:
        if operation not in ("login", "getDeviceListNew", "setThermostatWorkModeNew"):
            raise SmartThermError("Unsupported operation")
        if write != (operation == "setThermostatWorkModeNew"):
            raise SmartThermError("Invalid operation type")
        params = extra if operation == "login" else {
            "token": self._token, "user_id": self._user_id,
            "userid_phoneid": self._user_id.zfill(7) + self._client_id, **extra,
        }
        try:
            async with self._session.post(
                BASE_URL + operation, data=params, allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                if response.status in (401, 403):
                    raise SmartThermAuthError("SmartTherm authentication failed")
                if response.status != 200:
                    raise SmartThermError("SmartTherm returned an unsuccessful HTTP response")
                raw = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    raw.extend(chunk)
                    if len(raw) > 2_000_000:
                        raise SmartThermError("Cloud response exceeded the size limit")
                data = json.loads(raw)
        except SmartThermAuthError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError, SmartThermError):
            if write:
                raise SmartThermWriteUnknown("Write outcome unknown; refresh the device before retrying") from None
            raise SmartThermError("Unable to read SmartTherm cloud data") from None
        if not isinstance(data, dict):
            if write:
                raise SmartThermWriteUnknown("Write outcome unknown; refresh the device before retrying")
            raise SmartThermError("Unexpected cloud response")
        if str(data.get("error_code")) == "4":
            raise SmartThermAuthError("SmartTherm token was rejected; supply a valid token")
        if data.get("statu") is False or data.get("status") is False:
            if operation == "login":
                raise SmartThermAuthError("SmartTherm rejected the login")
            raise SmartThermError("SmartTherm rejected the request")
        return data

    @staticmethod
    async def async_login(session: aiohttp.ClientSession, email: str, password: str) -> dict[str, str]:
        """Exchange login credentials for an ID/token without retaining the password."""
        if not isinstance(email, str) or not email.strip() or not isinstance(password, str) or not password:
            raise SmartThermAuthError("An email/login and password are required")
        client = SmartThermClient(session, "", "", "")
        data = await client._post("login", {"email": email.strip(), "password": password})
        user = data.get("user")
        if not isinstance(user, dict):
            raise SmartThermAuthError("Login did not return a valid session")
        user_id = str(user.get("id", ""))
        token = user.get("token")
        if (not user_id.isascii() or not user_id.isdigit() or not 1 <= len(user_id) <= 7
                or not isinstance(token, str) or not token.strip()):
            raise SmartThermAuthError("Login did not return a valid session")
        # Never return the raw account object: it can contain a password/email.
        return {"user_id": str(int(user_id)), "token": token.strip()}

    async def async_get_devices(self) -> dict[str, Thermostat]:
        result: dict[str, Thermostat] = {}
        for page in range(1, 101):
            data = await self._post("getDeviceListNew", {
                "pageNum": str(page), "pageSize": "12", "online": "1", "device_type": "1",
            })
            rows = data.get("devices")
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise SmartThermError("Cloud response has no valid devices array")
            previous = len(result)
            for row in rows:
                device = parse_thermostat(row)
                result[device.device_id] = device
            if len(rows) < 12:
                return result
            if len(result) == previous:
                raise SmartThermError("Cloud pagination did not advance")
        raise SmartThermError("Cloud pagination limit reached")

    async def async_set_target(self, device: Thermostat, mode: str, temperature: float | None) -> None:
        if not device.online:
            raise SmartThermError("Thermostat is offline")
        if mode not in (MODE_MANUAL, MODE_OVERRIDE, MODE_SCHEDULE):
            raise SmartThermError("Unsupported thermostat mode")
        encoded = encode_temperature(device.configured_target if mode == MODE_SCHEDULE else temperature)
        await self._post("setThermostatWorkModeNew", {
            "device_id": device.device_id, "work_mode": mode,
            "current_temprature": encoded,
            "messageId": format(4100 + secrets.randbelow(28667), "x"),
        }, write=True)
