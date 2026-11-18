# Working on Anker SOLIX Extras

## Purpose and boundaries

- This is a community companion to `anker_solix_official`, not a replacement.
- Keep the domain `anker_solix_extras` and only provide additional entities.
- Start with read-only battery temperature: input register 10156, unit ID 1,
  signed INT16 divided by 10, Celsius, suggested display precision 0.
- Register 10156 is undocumented by Anker. Distinguish hardware observations
  from inferred model compatibility; never describe it as officially supported.
- Use the official integration's public config-entry data and device registry
  to select a battery. Do not import its implementation, patch its coordinator,
  write registers, change operating mode, or modify its files/configuration.
- Additional entities belong to Extras but attach to the official device using
  `entity.device_entry` with `device_info` unset. Matching identifiers alone
  does not share a device across config entries in recent Home Assistant.
- Removing/reloading Extras must never remove or update the official device.
  Handle the official entry being unavailable, disabled, removed, or reconfigured.

## Development

- Use Python 3.14. `requirements_dev.txt` uses official `pytest-homeassistant`
  matched to Core 2026.11.2. In a separate environment, use
  `requirements_legacy_test.txt` for Core 2026.10.4 / pymodbus 3.10.0.
- Never force an incompatible Core version into either test plugin's environment.
  The old community plugin is broken on Core 2026.11. Tests import helpers through
  `tests/ha.py`; only the legacy harness requires `enable_custom_integrations`.
- Keep `-p no:respx` in pytest options: autoloading that plugin can import the old
  HTTP client before Core initializes its new HTTP client compatibility aliases.
- Follow Home Assistant's async config-flow, coordinator, entity-description,
  typed `ConfigEntry.runtime_data`, and unload-cleanup patterns.
- Use Ruff for lint and formatting; run pytest against real Home Assistant
  helpers. Mock the Modbus transport, not Home Assistant's entity registry.
- Test config-flow selection and duplicates; signed register decoding; failed
  reads/reconnection; setup/reload/unload; shared device identity; and safe removal.
- Never put live IP addresses, serial numbers, credentials, tokens, or real
  config-entry/device IDs into source, fixtures, documentation, or commit text.
- Keep test environments, downloaded tooling, and logs outside the repository.

## Git and releases

- Make every change on a feature branch and open a pull request against `main`.
  This includes features, fixes, documentation, and maintenance changes.
- Wait for explicit maintainer approval before merging into `main`. Passing CI
  is necessary but is not permission to merge. Do not push changes directly to
  `main`, merge your own PR automatically, or bypass the review workflow.
- Make focused conventional commits as work progresses (`chore:`, `feat:`,
  `test:`, `fix:`, `docs:`). Do not squash or rewrite the owner's commits.
- Write PR titles as concise, human-readable summaries of the overall change.
  Do not copy a conventional commit subject or include prefixes such as `docs:`
  or `feat:`. For example: "Simplify the README and clarify contribution rules".
  Keep the title and description aligned with the final scope of the PR.
- Never create/push release tags, publish GitHub releases, or change the version
  unless a maintainer explicitly requests it. Merging a PR does not authorize
  a release. CI checks do not publish releases.
- Update this file when implementation or testing reveals useful constraints.

## Documentation

- Keep the README focused on end users: purpose, sensors, compatibility,
  installation, everyday use, troubleshooting, and removal.
- Keep general setup and removal instructions applicable to all Extras sensors.
  Put sensor-specific details in the sensor table where possible.
- Put architecture, register behaviour, test harness details, and hardware-test
  procedures in `CONTRIBUTING.md` or this file instead of the main README.
- Do not include development/release-status commentary or instructions addressed
  to a named individual in the README or contributor guidance.
- Retain a clear statement that Extras uses features outside Anker's published
  and supported Modbus interface and is used at the user's own risk, with no
  responsibility accepted by contributors/maintainers for resulting device
  damage or other loss. Do not imply Anker endorsement or guaranteed compatibility.
- Extras has now been reported working on a Solarbank 4 E5000 Pro, including
  attachment to the official device. Do not keep describing that test as pending
  or imply the other supported models have all been hardware-tested.

## Verification and handoff

- Run `ruff check .`, `ruff format --check .`, `pytest`, and `git diff --check`.
- CI also runs HACS validation and Hassfest.
- Device registry `devices` iterates device entries, not IDs. Tests compare
  `{device.id for device in registry.devices}`; do not assume a dict API.
- Suggested precision is stored by the sensor platform under
  `entity.options["sensor"]["suggested_display_precision"]`; do not confuse it
  with a user override under `display_precision`.
- The official integration test fixture needs a mock config-flow platform and
  a versioned flow handler even though tests never run Anker's own setup flow.
- On Windows, the HA pytest plugin imports Linux-only `fcntl`. Run the complete
  suite in Linux (CI or an isolated rootless Podman container in WSL) rather than
  stubbing OS modules or claiming plugin-disabled unit tests cover the lifecycle.
- Keep README installation, compatibility, and removal instructions current;
  keep development and hardware-test guidance in `CONTRIBUTING.md` current.
- Do not install/restart/change the live Home Assistant instance merely to run
  development tests. Coordinate hardware tests separately with the user.
