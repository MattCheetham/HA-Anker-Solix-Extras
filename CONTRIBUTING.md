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
Pro, including its additional sensor appearing on the existing official device.
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
