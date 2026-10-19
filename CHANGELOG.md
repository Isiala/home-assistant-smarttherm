# Changelog

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
