"""Import the matching official or pre-2026.11 Home Assistant test helpers."""

from importlib.util import find_spec

CORE_TEST_PLUGIN = find_spec("pytest_homeassistant") is not None

if CORE_TEST_PLUGIN:
    from pytest_homeassistant.common import (
        MockConfigEntry as MockConfigEntry,
        MockModule as MockModule,
        mock_integration as mock_integration,
        mock_platform as mock_platform,
    )
else:
    from pytest_homeassistant_custom_component.common import (
        MockConfigEntry as MockConfigEntry,
        MockModule as MockModule,
        mock_integration as mock_integration,
        mock_platform as mock_platform,
    )
