# Changelog

## Unreleased

- Support thermostat family 53 (e.g. Delta ST2602WIFIRF-5G), whose device
  identifiers are not 12-digit numbers (for example `&ABCD123E456`).

## 0.2.0

- Add email/password setup that discovers the account ID and token automatically.
- Use email/password or an existing token for reauthentication and reconfiguration.
- Save only account ID, token, and client ID; never persist the password/email.
- Reject reauthentication with a different account to preserve existing entities.
- Keep all existing token-based installations compatible without migration.
- Expand the test suite to cover login payloads, failed authentication, password
  handling, token replacement, and account identity checks.

## 0.1.0

- Token-based setup with account discovery for OCSTAT thermostat models 08 and 09.
- Climate entities with room/target temperature and reported heating state.
- Schedule, manual, and override modes with half-degree temperature control.
- Shared asynchronous polling, token replacement, and offline availability.
- Serialized writes and cloud read-back checks without automatic write retries.
- HACS custom-repository metadata and Home Assistant validation workflows.

Reads have been verified against real thermostats. Actual temperature writes have
not yet been tested on hardware; control request and read-back behavior have
mocked tests.
