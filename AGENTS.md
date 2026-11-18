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

- Use Python 3.14. The test plugin in `requirements_dev.txt` pins Core 2026.10.4;
  test that minimum with pymodbus 3.10.0, then upgrade Core to 2026.11.2 and
  pymodbus to 3.16.2 for the current-version run. The plugin's older Core pin
  produces a dependency warning during that intentional second-stage upgrade.
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

- Make focused conventional commits as work progresses (`chore:`, `feat:`,
  `test:`, `fix:`, `docs:`). Do not squash or rewrite the owner's commits.
- The initial intended version is `0.1`.
- Never create/push release tags or publish a GitHub release unless Matthew
  explicitly requests publication. CI checks do not publish releases.
- Update this file when implementation or testing reveals useful constraints.

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
- Keep README installation, compatibility, test, and rollback instructions current.
- Do not install/restart/change the live Home Assistant instance merely to run
  development tests. Coordinate the hardware test separately with Matthew.
