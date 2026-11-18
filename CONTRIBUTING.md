# Contributing to Anker SOLIX Extras

## Changes and review

Create a feature branch and make focused conventional commits, such as `feat:`,
`fix:`, `test:`, or `docs:`. Open a pull request against `main` for every change,
including documentation and maintenance changes. Wait for explicit maintainer
approval before merging. Passing CI alone is not approval to merge.

Use a concise, human-readable PR title that summarizes the overall change,
such as "Simplify the README and clarify contribution rules". Conventional
commit prefixes such as `docs:` and `feat:` belong in commit messages, not PR
titles. Update the title and description if the PR's scope changes.

Do not create or push release tags, publish GitHub releases, or bump the version
unless explicitly requested by a maintainer. Releases are a separate step from
merging a pull request. CI validates changes and does not publish releases.

When a maintainer explicitly requests publication, release-only version bumps
and release notes can be committed directly to `main`. Tag the tested main
commit and publish the requested release; no release PR or release branch is
needed. Features and fixes still require review. Mark betas as GitHub prereleases
and keep the latest stable release unchanged.

Keep the README focused on installation and use. Put implementation details,
testing procedures, and contributor advice here or in [AGENTS.md](AGENTS.md).
Avoid release-status commentary or instructions aimed at a particular person in
the main README.

## Development environment

Use Python **3.14** on Linux. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements_dev.txt
ruff check .
ruff format --check .
pytest --cov=custom_components.anker_solix_extras --cov-report=term-missing
git diff --check
```

The development requirements use the official `pytest-homeassistant` plugin
matched to Core 2026.11.2. CI separately installs `requirements_legacy_test.txt`
to test Core 2026.10.4 with the last compatible community test plugin. Use a
separate environment for each harness; do not combine them or override their
Core pins. The `respx` pytest plugin is disabled to preserve Core's HTTP client
initialization order.

Tests use real Home Assistant registries and mock the official integration and
Modbus transport. No battery is required. CI also runs Hassfest and HACS validation.

## Integration boundaries

Extras provides additional entities alongside the official integration. It
selects an official configuration entry and attaches its own entities directly
to that entry's existing device. It must not change the device's owner or
identifiers, or modify the official integration's files or configuration.

Use the public Home Assistant configuration-entry and device-registry APIs.
Do not import the official integration's Python modules or access its private
coordinator data. Extras uses its own read-only Modbus connection and picks up
the official entry's current address when updating.

Verify setup, reload, unload, and removal with the real Home Assistant registries.
Removing Extras must leave the official device and entities intact. If the
official entry is unavailable or removed, Extras must not create a replacement
device or invent sensor values.

## Hardware validation

The separate Extras integration has been reported working on a Solarbank 4 E5000
Pro, including its temperature sensor appearing on the existing official device.
Keep hardware observations separate from inferred compatibility for other models.

For a new measurement or model, compare readings with a known working source and
record the model, firmware, and Core version when available. Check behaviour
through reloads and restarts. Keep existing automations unchanged during initial
testing, and remove only the Extras entry if rollback is needed.

Never commit live addresses, serial numbers, credentials, tokens, or configuration
entry/device IDs. Redact logs before sharing them.

## Local installation archive

Run `python scripts/build_zip.py` to create `dist/anker_solix_extras.zip`. The
archive contains the `anker_solix_extras` folder ready to extract into Home
Assistant's `custom_components` directory. Building it does not create a tag or
publish a release.

## Heating estimate

The heating entities are experimental estimates, not direct heater telemetry.
Extras reads input registers 10006–10009 together (unit ID 1): AC power at 10006
and battery power at 10008. Each is a high-word-first signed INT32 in watts,
matching the official integration's decoding. Negative values mean AC absorption
and battery charging respectively. No load power registers are read or used.

When AC power is negative, estimated heating is `max(battery_power - ac_power, 0)`.
Otherwise it is zero. For example, AC power of -2450 W and battery power of
-2210 W produce 240 W. Activity is strictly `heating_power > 0`, with no
threshold, rounding, or hysteresis. Both entities therefore share any false
positives in the estimate, including small conversion losses. Heating outside
AC absorption is not detected. Other consumption and PV flows may affect the
power difference; the estimate does not compensate for them.

The power entity exposes signed `ac_power` and `battery_power` source attributes.
Both must come from the same response. A failed power read makes both heating
entities unavailable and clears those attributes. Temperature is independent:
partial read failures must not hide a valid measurement or reuse stale values.
If neither measurement succeeds, the coordinator reports an update failure.
Existing setup validation still checks the temperature register; adding heating
must not require existing installations to recreate their configuration entry.

The register definitions come from the
[Anker Modbus guide](https://salesforce-knowledge-download.s3.us-west-2.amazonaws.com/000039871/en_US/000039871.pdf).
[Upstream PR #155](https://github.com/anker-charging/ha-anker-solix-official/pull/155)
provides the initial calculation idea, but its worked example reverses the two
signed source readings relative to its formula. Tests use the signs above rather
than taking an absolute difference. Model compatibility remains inferred, not a
claim of successful hardware testing.

### Manual heating comparison

Coordinate hardware testing with the maintainer; do not install this branch,
restart Home Assistant, or change battery settings automatically.

1. Install the reviewed build using the normal installation method, preserving
   the official integration and existing Extras entry. Confirm all three Extras
   entities appear on the existing battery device and temperature retains its ID.
2. During naturally occurring heating-off and heating-on periods with AC
   absorption, compare the Anker app's heater reading with Extras. Allow for the
   configured polling interval (60 seconds by default) and the app's own refresh delay.
3. Record the two signed source attributes, calculated heating, activity state,
   app heater reading, PV generation, and any connected appliance consumption.
   Also observe a period without AC absorption: the estimate must be zero and
   activity off, regardless of whether the device can heat in that condition.
4. Report the model, firmware, conditions, and any consistent mismatch. In
   particular, check whether conversion losses produce positive estimates while
   the app reports no heating. Do not use the estimate for critical automations
   before comparing it with the device's behavior.
5. Check reload and restart preserve all entity IDs. Roll back the integration
   files if needed without deleting the official device or configuration.

Redact addresses, identifiers, and account information before sharing observations.

## Polling configuration

Store the per-battery polling interval in entry.options under scan_interval, in
seconds; entries without the option retain the 60-second default. Both initial
setup and the options flow expose the setting. The options flow reloads Extras
through OptionsFlowWithReload; do not add an Extras entry update listener as well.
The official entry listener remains separate and refreshes only source settings.

The Linux test container may still mount a historical checkout after moving this
workspace. Check its bind mount before testing. Copy the current repository into
an isolated container directory or recreate the mount; do not test stale files.
