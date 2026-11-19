# Contributing to Anker SOLIX Extras

## Changes and review

Create a feature branch and make focused conventional commits, such as `feat:`,
`fix:`, `test:`, or `docs:`. Open a pull request against `main` for every
change, including documentation and maintenance changes. Wait for passing CI
and explicit maintainer approval before merging.

Use a concise PR title without a conventional commit prefix. Describe the
change and how you verified it. Update the title and description if the scope
changes.

Bump the version, tag a commit, or publish a GitHub release only at a
maintainer's explicit request. That request allows release-only version bumps
and release notes directly on `main`. Tag the tested commit and mark beta
releases as prereleases so the latest stable release stays in place.

## Development environment

Use Python **3.14** on Linux (including WSL). From the repository root, run the
same test and lint commands as CI.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements_dev.txt
ruff check .
ruff format --check .
pytest --cov=custom_components.anker_solix_extras --cov-report=term-missing
git diff --check
```

CI also runs the same tests with `requirements_legacy_test.txt`, plus Hassfest
and HACS validation. To run the legacy suite locally, install its requirements
in a separate virtual environment so each suite uses its pinned Home Assistant
dependencies.

## Development checks

- Use real Home Assistant test helpers and registries. Mock the Modbus transport
  and the official integration so tests can run without a battery.
- For setup, reload, and removal changes, verify that Extras attaches to the
  existing official device and that the official integration keeps its own
  device, entities, and configuration.
- For changes to Modbus controls, cover capability checks, fresh reads before
  writing, and readback. Only explicit control actions may write to the device.
- When changing setup text or entity names, keep `strings.json` and the English,
  German, French, and Dutch translations in sync. Preserve existing entity IDs.
- Update the README when installation, usage, compatibility, or troubleshooting
  changes.

## Hardware validation

Coordinate live tests with the maintainer. To build an archive for an approved
test, run `python scripts/build_zip.py` from the repository root. The command
creates `dist/anker_solix_extras.zip` for extraction into Home Assistant's
`custom_components` directory.

For a new reading or model, compare against a known working source. Report the
battery model, firmware, Home Assistant Core version, conditions, and what you
observed. Distinguish results observed on hardware from inferred compatibility.
Redact live addresses, serial numbers, credentials, tokens, and registry IDs
from fixtures, logs, and reports.

For changes to setup or entities, verify that reload and restart preserve
existing entity IDs. If you need to roll back a test build, restore the previous
Extras files and leave the official integration and device in place.
