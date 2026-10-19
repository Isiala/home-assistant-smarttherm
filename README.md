# SmartTherm (OCSTAT) for Home Assistant

Custom integration for the OCSTAT SmartTherm cloud used by the iPhone app
`com.zhongjin.Thermostat`. Supports the tested thermostat families **08 and 09**.
This is a community reverse-engineered integration, not an official OCSTAT product.

## Install with HACS

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/Isiala/home-assistant-smarttherm` with type **Integration**.
3. Download **SmartTherm (OCSTAT)** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → SmartTherm (OCSTAT)**.
5. Choose **Sign in with email and password** and enter the credentials used in the SmartTherm app. The account ID and token are discovered automatically.

This is a HACS custom repository; it has not been submitted to the default HACS
catalog. Branding validation is skipped while no separate Home Assistant Brands
submission exists.

[Open this repository in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=Isiala&repository=home-assistant-smarttherm&category=integration)

## Manual installation

1. Download the release ZIP and extract it into your Home Assistant configuration directory. The resulting
   path must be `/config/custom_components/smarttherm/manifest.json`.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → SmartTherm (OCSTAT)**.
4. Choose **Sign in with email and password** and enter the email/login name and
   password used in the SmartTherm app. The integration obtains the account ID
   and token automatically. No numeric ID or device identifiers need to be entered.

If you already have a token, choose **Use an existing account ID and token**
instead. That alternative accepts the numeric account ID and token as before.

The integration automatically discovers supported thermostats. It is independent
of macOS, Keychain, packet captures, proxies, and the phone once a valid token is
provided. No Python packages need to be installed manually inside Home Assistant.

The code targets Home Assistant Core 2025.10 or newer. Its automated integration
suite was run against Core 2025.10.4; installation on your own HA instance has
not yet been tested.

## Features

- Climate entity per supported thermostat, using its name from SmartTherm.
- Room temperature, target, and reported heating/idle state.
- Polling once per minute, shared by all entities in the account.
- Targets from 5 to 35°C in 0.5°C steps.
- **Auto / schedule:** run the existing thermostat schedule (app mode 0).
- **Heat / manual:** use a fixed target (app mode 5).
- **Override:** app mode 1. Changing the temperature while in Auto selects this
  override, matching the app. Its exact duration has not been verified.
- Email/password setup retrieves the account ID and token automatically.
- Existing account ID/token setup remains available.
- An expired session triggers Home Assistant's reauthentication prompt. Sign in
  again or supply a replacement token. **Reconfigure** also offers both methods.
- Existing installations retain their account and entity IDs after updating.
- New supported devices are added on subsequent updates; missing/offline devices
  become unavailable.

Off, boost, holiday, schedule editing, and other controls are not exposed. The
mode mapping for those operations has not been sufficiently verified.

## Examples

Replace `climate.your_thermostat` with your actual entity ID.

Set 13.5°C in manual mode:

```yaml
action: climate.set_temperature
target:
  entity_id: climate.your_thermostat
data:
  hvac_mode: heat
  temperature: 13.5
```

Restore the thermostat schedule:

```yaml
action: climate.set_hvac_mode
target:
  entity_id: climate.your_thermostat
data:
  hvac_mode: auto
```

## Credentials and privacy

**No real account token, user ID, device ID, password, packet capture, or Mac
Keychain export is included in this repository or its releases.** Enter your own credentials only in the
Home Assistant form. Password and token fields are masked. Login credentials
are sent to the manufacturer's fixed HTTPS endpoint with redirect following
disabled. The password and email are used only for that sign-in attempt: they
are not saved in the integration's config entry. Only the resulting account ID,
token, and generated client ID are saved. This integration does not log request
payloads, raw server messages, credentials, or full API responses, and has no
diagnostics export containing config entries.

Home Assistant stores integration credentials in its local `.storage` config
entry files, like other token-based integrations. Masking the UI is not encryption
of those files. Protect the HA configuration directory and its backups; do not
commit them. Token expiry is controlled by OCSTAT. Automatic token refresh is
not available because passwords are not retained. If the saved token is rejected,
use the Home Assistant reauthentication form to sign in again or supply a new token.

## Verification and limitations

The independent async API read path was verified against real thermostats using
credentials in memory. No live readings or account details are included in the repository. Setup,
climate entities, reauthentication, unload, API errors, redirect handling, and
control requests have automated tests using synthetic credentials/devices.
The email/password exchange is based on the manufacturer's app login operation;
its successful and rejected responses are covered by mocked API tests. A live
email/password login has not yet been verified with supplied account credentials.

Actual thermostat writes have not been tested live. The control endpoint, modes,
and temperature units were traced from the manufacturer's app. A control sends
one write and then polls for the requested mode and target. It never automatically
retries a write. Successful read-back confirms the **cloud-reported state**, not
an independent acknowledgement from the physical thermostat. If the requested
state is not confirmed, the service raises an error and the next normal poll
continues to report observed data. Refresh before deciding to resend a command.

The cloud supplies no verified sensor sampling timestamp. Cloud values may be
cached, even when a fresh HTTP request succeeds. Unknown thermostat modes are
shown without an inferred HVAC mode. Unsupported models are not exposed as
controllable climate entities.

## Development

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
```

Tests use the Home Assistant custom-component test framework. Do not put real
credentials in fixtures. Installation/distribution should copy only the
`custom_components/smarttherm` directory and this README.

## Contributing and support

Report reproducible problems through [GitHub issues](https://github.com/Isiala/home-assistant-smarttherm/issues).
Include your Home Assistant version, thermostat model, and sanitized error text.
Never attach tokens, complete configuration files, packet captures, or raw cloud
responses (they can contain credentials and device passwords).

GitHub Actions runs the tests against the minimum supported Home Assistant release
and a current release, plus hassfest and HACS validation. Tests use synthetic data
and do not require repository secrets or access to your thermostats.

Released under the [MIT License](LICENSE).
