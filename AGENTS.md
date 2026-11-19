# Working on Anker SOLIX Extras

## Purpose and boundaries

- This is a community companion to `anker_solix_official`, not a replacement.
- Keep the domain `anker_solix_extras` and only provide additional entities.
- Read-only battery temperature uses input register 10156, unit ID 1,
  signed INT16 divided by 10, Celsius, suggested display precision 0.
- Register 10156 is undocumented by Anker. Distinguish hardware observations
  from inferred model compatibility; never describe it as officially supported.
- Use the official integration's public config-entry data and device registry
  to select a battery. Do not import its implementation, patch its coordinator,
  change operating mode, or modify its files/configuration.
- Keep Modbus writes generic at the client layer and issue them only through
  explicit controls. Each control checks capability and fresh state before
  writing, then confirms the result by reading it back. Polling and setup are
  read-only.
- Only the backup reserve controls may write registers 60002 and 60003.
- Additional entities belong to Extras but attach to the official device using
  `entity.device_entry` with `device_info` unset. Matching identifiers alone
  does not share a device across config entries in recent Home Assistant.
- Removing/reloading Extras must never remove or update the official device.
  Handle the official entry being unavailable, disabled, removed, or reconfigured.
- Poll read-only Plant Status (UINT16 at input register 10000) with heating
  power in one FC04 read of 10000–10009. On an illegal-address response, fall
  back to 10006–10009 for heating. Unknown status codes leave Plant Status
  unavailable.
- Heating is an experimental estimate: decode signed INT32 AC/battery power from
  input registers 10006–10009 together, high word first. When AC is negative,
  use max(battery - AC, 0); otherwise zero. Activity is strictly estimate > 0.
- Do not read or use load power for this estimate. Do not introduce a deadband,
  absolute difference, or undocumented correction without explicit agreement.
- Polling defaults to 60 seconds per battery, configured through scan_interval
  in entry.options. Keep setup and options translations aligned. Use
  OptionsFlowWithReload without an Extras entry update listener.
- Keep temperature and power availability independent; never retain stale power
  attributes or interpret read failures as zero/off. Preserve temperature IDs.
- Heating compatibility is inferred for the supported models, not hardware-tested.
  Keep the README clear that losses and other consumption may affect the estimate.
- Heating activity uses a generic binary sensor with a radiator icon so its
  states display as On/Off. The Heat device class means Hot/Normal, not whether
  the battery heater is active.

## Development

- Use Python 3.14. `requirements_dev.txt` uses official `pytest-homeassistant`
  matched to Core 2026.11.2. In a separate environment, use
  `requirements_legacy_test.txt` for Core 2026.10.4. Match each Core version's
  built-in Modbus dependency pins.
- Never force an incompatible Core version into either test plugin's environment.
  The old community plugin is broken on Core 2026.11. Tests import helpers through
  `tests/ha.py`; only the legacy harness requires `enable_custom_integrations`.
- Keep `-p no:respx` in pytest options: autoloading that plugin can import the old
  HTTP client before Core initializes its new HTTP client compatibility aliases.
- Follow Home Assistant's async config-flow, coordinator, entity-description,
  typed `ConfigEntry.runtime_data`, and unload-cleanup patterns.
- Acquire a shared unit from Core's Modbus integration. Use a temporary unit in
  the config flow and let Core release the entry's unit on unload. Reload only
  Extras when the official entry's address changes.
- Use Ruff for lint and formatting; run pytest against real Home Assistant
  helpers. Mock the Modbus transport, not Home Assistant's entity registry.
- Test config-flow selection and duplicates; signed register decoding; failed
  reads/reconnection; setup/reload/unload; shared device identity; and safe removal.
- Never put live IP addresses, serial numbers, credentials, tokens, or real
  config-entry/device IDs into source, fixtures, documentation, or commit text.
- Keep test environments, downloaded tooling, and logs out of Git.

## Git and releases

- Make features, fixes, documentation, and maintenance changes on a feature
  branch and open a pull request against `main`. The release-only exception
  below applies when a maintainer explicitly requests publication.
- Wait for explicit maintainer approval before merging into `main`. Passing CI
  is necessary but is not permission to merge. Do not push changes directly to
  `main` outside the release-only exception, merge your own PR automatically,
  or bypass the review workflow.
- Make focused conventional commits as work progresses (`chore:`, `feat:`,
  `test:`, `fix:`, `docs:`). Do not squash or rewrite the owner's commits.
- Write PR titles as concise, human-readable summaries of the overall change.
  Do not copy a conventional commit subject or include prefixes such as `docs:`
  or `feat:`. For example: "Simplify the README and clarify contribution rules".
  Keep the title and description aligned with the final scope of the PR.
- Never create/push release tags, publish GitHub releases, or change the version
  unless a maintainer explicitly requests it. Merging a PR does not authorize
  a release. CI checks do not publish releases.
- An explicit request to publish a version authorizes release-only version bumps
  and release notes directly on `main`, followed by tagging that tested commit
  and publishing the release. A release PR or release branch is not required.
  This exception does not authorize unrelated feature or fix changes. Mark beta
  releases as GitHub prereleases and leave the latest stable release unchanged.
- Update this file when a lasting constraint changes how agents should work.

## Documentation

- Match the official integration's languages: English, German, French, and Dutch
  (`en`, `de`, `fr`, `nl`). Update all four translation files when changing setup
  text or adding entities; keep their keys aligned with `strings.json`.
- Match the official integration's English entity names with Title Case (for
  example, Battery Heating Power). Keep native capitalization conventions in
  other languages and preserve translation keys and entity IDs when renaming.
- Keep the README focused on end users: purpose, sensors, compatibility,
  installation, everyday use, troubleshooting, and removal.
- Keep the setup wizard description generic; describe individual sensors and
  their limitations in the README rather than in setup text.
- Keep general setup and removal instructions applicable to all Extras entities.
  Put sensor-specific details in the sensor table where possible.
- Keep `CONTRIBUTING.md` focused on development setup, validation, and review.
  Keep implementation behaviour in source and tests. Keep hardware observations,
  investigation notes, and local tooling details in the workspace outside the
  repository.
- Do not include development/release-status commentary or instructions addressed
  to a named individual in the README or contributor guidance.
- Retain a clear statement that Extras uses features outside Anker's published
  and supported Modbus interface and is used at the user's own risk, with no
  responsibility accepted by contributors/maintainers for resulting device
  damage or other loss. Do not imply Anker endorsement or guaranteed compatibility.
- Use the README's compatibility table for the current hardware-test status.

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
