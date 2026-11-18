"""Fixtures using Home Assistant's real device and entity registries."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.anker_solix_extras.const import DOMAIN, OFFICIAL_DOMAIN
from custom_components.anker_solix_extras.models import BackupReserve, BatteryPower

from .ha import (
    CORE_TEST_PLUGIN,
    MockConfigEntry,
    MockModule,
    mock_integration,
    mock_platform,
)


@pytest.fixture(autouse=True)
def custom_integrations(request: pytest.FixtureRequest) -> None:
    """Allow the test harness to load Extras from this repository."""
    if not CORE_TEST_PLUGIN:
        request.getfixturevalue("enable_custom_integrations")


@pytest.fixture
async def official_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Represent the official integration without importing Anker's code."""

    class OfficialConfigFlow(ConfigFlow, domain=OFFICIAL_DOMAIN):
        """Provide the version information required by Core during setup."""

        VERSION = 1

    mock_integration(
        hass,
        MockModule(
            OFFICIAL_DOMAIN,
            async_setup_entry=AsyncMock(return_value=True),
            async_unload_entry=AsyncMock(return_value=True),
            partial_manifest={"version": "1.5.1"},
        ),
        built_in=False,
    )
    mock_platform(hass, f"{OFFICIAL_DOMAIN}.config_flow", MagicMock(), built_in=False)
    entry = MockConfigEntry(
        domain=OFFICIAL_DOMAIN,
        title="Test Solarbank",
        data={"ip_address": "192.0.2.10", "port": 502},
        unique_id="test-battery",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(OFFICIAL_DOMAIN, entry.entry_id)},
        manufacturer="Anker",
        model="Anker SOLIX Solarbank 4 E5000 Pro",
        name="Test Solarbank",
    )
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Replace only the independent Modbus transport boundary."""
    with patch(
        "custom_components.anker_solix_extras.coordinator.AnkerSolixExtrasClient",
        autospec=True,
    ) as factory:
        client = factory.return_value
        client.async_read_temperature = AsyncMock(return_value=25.0)
        client.async_read_power = AsyncMock(return_value=BatteryPower(-2450, -2210))
        client.async_read_state_of_health = AsyncMock(return_value=100)
        client.async_read_backup_reserve = AsyncMock(
            return_value=BackupReserve(
                enabled=False, switch_supported=True, percentage=7
            )
        )
        yield factory


@pytest.fixture
def extras_entry(
    hass: HomeAssistant, official_entry: MockConfigEntry
) -> MockConfigEntry:
    """Create a configured Extras entry for the test battery."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Solarbank",
        data={"official_entry_id": official_entry.entry_id},
        unique_id=official_entry.entry_id,
    )
    entry.add_to_hass(hass)
    return entry
