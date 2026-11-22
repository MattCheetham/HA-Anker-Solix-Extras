"""Read the measurements used by setup validation and regular polling."""

import logging

from homeassistant.helpers.update_coordinator import UpdateFailed

from .client import (
    AnkerSolixExtrasClient,
    BackupReserveError,
    OffGridOutputPowerReadError,
    PowerReadError,
    RegisterReadError,
    StateOfHealthReadError,
    TemperatureReadError,
)
from .const import (
    ENERGY_ADDRESSES,
    EXPORT_LIMIT_ADDRESS,
    EXPORT_LIMIT_ENABLE_ADDRESS,
    MAX_EXPORT_LIMIT,
    SYSTEM_TIME_ADDRESS,
)
from .models import BatteryMeasurements

_LOGGER = logging.getLogger(__name__)

PUBLISHED_SETTINGS = {
    SYSTEM_TIME_ADDRESS: (2, 946684800, 0xFFFFFFFF),
    EXPORT_LIMIT_ENABLE_ADDRESS: (1, 0, 1),
    EXPORT_LIMIT_ADDRESS: (2, 0, MAX_EXPORT_LIMIT),
}


def published_input_registers(pcs_count_addresses: dict[str, int]) -> dict[int, int]:
    """Return published input register addresses and their word counts."""
    return {address: 2 for address in ENERGY_ADDRESSES.values()} | {
        address: 1 for address in pcs_count_addresses.values()
    }


async def async_read_measurements(
    client: AnkerSolixExtrasClient,
    *,
    off_grid_output_power_enabled: bool,
    published_inputs: dict[int, int] | None,
    published_addresses: set[int] | None = None,
) -> BatteryMeasurements:
    """Read independently available groups of battery values."""
    temperature = None
    power = None
    plant_status = None
    state_of_health = None
    off_grid_output_power = None
    backup_reserve = None
    try:
        temperature = await client.async_read_temperature()
    except TemperatureReadError as err:
        _LOGGER.debug("Temperature read failed: %s", err)
    try:
        plant_status, power = await client.async_read_status_and_power()
    except PowerReadError as err:
        _LOGGER.debug("Plant status and power read failed: %s", err)
    try:
        state_of_health = await client.async_read_state_of_health()
    except StateOfHealthReadError as err:
        _LOGGER.debug("State of health read failed: %s", err)
    if off_grid_output_power_enabled:
        try:
            off_grid_output_power = await client.async_read_off_grid_output_power()
        except OffGridOutputPowerReadError as err:
            _LOGGER.debug("Off-grid output power read failed: %s", err)
    try:
        backup_reserve = await client.async_read_backup_reserve()
    except BackupReserveError as err:
        _LOGGER.debug("Backup reserve read failed: %s", err)
    published_values = (
        await _async_read_published_values(
            client, published_inputs, published_addresses
        )
        if published_inputs is not None
        else {}
    )
    if not published_values and all(
        reading is None
        for reading in (
            temperature,
            power,
            state_of_health,
            off_grid_output_power,
            backup_reserve,
        )
    ):
        raise UpdateFailed("Unable to read any battery measurements")
    return BatteryMeasurements(
        temperature=temperature,
        power=power,
        plant_status=plant_status,
        state_of_health=state_of_health,
        backup_reserve=backup_reserve,
        off_grid_output_power=off_grid_output_power,
        published_values=published_values,
    )


async def _async_read_published_values(
    client: AnkerSolixExtrasClient,
    inputs: dict[int, int],
    addresses: set[int] | None,
) -> dict[int, int]:
    """Poll requested values independently of unsupported neighbors."""
    values = {}
    for address, count in inputs.items():
        if addresses is not None and address not in addresses:
            continue
        try:
            values[address] = await client.async_read_unsigned(address, count)
        except RegisterReadError as err:
            _LOGGER.debug("Published input read failed: %s", err)
    for address in PUBLISHED_SETTINGS:
        if addresses is not None and address not in addresses:
            continue
        try:
            values[address] = await async_read_published_setting(client, address)
        except RegisterReadError as err:
            _LOGGER.debug("Published setting read failed: %s", err)
    return values


async def async_read_published_setting(
    client: AnkerSolixExtrasClient, address: int
) -> int:
    """Check that the device exposes the setting and returns a valid value."""
    count, minimum, maximum = PUBLISHED_SETTINGS[address]
    value = await client.async_read_unsigned(address, count, holding=True)
    if not minimum <= value <= maximum:
        raise RegisterReadError(f"Invalid setting at register {address}")
    return value
