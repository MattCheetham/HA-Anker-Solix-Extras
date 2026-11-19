"""Fixtures using Home Assistant's real device and entity registries."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest
from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from modbus_connection import ModbusUnit

from custom_components.anker_solix_extras.const import DOMAIN, OFFICIAL_DOMAIN
from custom_components.anker_solix_extras.models import BatteryPower

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
def mock_connection() -> Generator[MagicMock]:
    """Mock the transport while keeping Home Assistant's connection registry."""
    with patch(
        "homeassistant.components.modbus.connection.ModbusConnection",
        autospec=True,
    ) as factory:
        unit = create_autospec(ModbusUnit, instance=True, spec_set=True)
        unit.connected = True
        factory.return_value.connected = True
        factory.return_value.for_unit.return_value = unit
        yield factory


@pytest.fixture
def mock_client(mock_connection) -> Generator[MagicMock]:
    """Stub battery measurements for entity and coordinator tests."""
    with patch(
        "custom_components.anker_solix_extras.AnkerSolixExtrasClient",
        autospec=True,
    ) as factory:
        client = factory.return_value
        client.async_read_temperature = AsyncMock(return_value=25.0)
        client.async_read_status_and_power = AsyncMock(
            return_value=("on_grid", BatteryPower(-2450, -2210))
        )
        client.async_read_state_of_health = AsyncMock(return_value=100)
        client.async_read_backup_reserve = AsyncMock(return_value=False)
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
