"""Tests for Modbus register access and measurement decoding."""

from unittest.mock import call, create_autospec

import pytest
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
    ModbusUnit,
)

from custom_components.anker_solix_extras.client import (
    AnkerSolixExtrasClient,
    BackupReserveError,
    PowerReadError,
    StateOfHealthReadError,
    TemperatureReadError,
)
from custom_components.anker_solix_extras.models import BackupReserve


@pytest.fixture
def unit():
    """Provide a shared Modbus unit without network I/O."""
    unit = create_autospec(ModbusUnit, instance=True, spec_set=True)
    unit.connected = True
    return unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(250, 25.0), (0, 0.0), (0xFFCE, -5.0), (253, 25.3), (0xFFCB, -5.3)],
)
async def test_read_temperature(unit, raw, expected) -> None:
    unit.read_input_registers.return_value = [raw]
    assert await AnkerSolixExtrasClient(unit).async_read_temperature() == pytest.approx(
        expected
    )
    unit.read_input_registers.assert_awaited_once_with(10156, 1)
    unit.write_register.assert_not_called()
    unit.write_registers.assert_not_called()


@pytest.mark.parametrize("registers", [[], [1, 2], [None], [True], [-1], [65536]])
async def test_bad_response_is_not_a_zero_temperature(unit, registers) -> None:
    unit.read_input_registers.return_value = registers
    with pytest.raises(TemperatureReadError):
        await AnkerSolixExtrasClient(unit).async_read_temperature()


@pytest.mark.parametrize(
    "error",
    [
        OSError("offline"),
        ModbusConnectionError("offline"),
        ModbusTimeoutError("timeout"),
    ],
)
async def test_transport_failure_then_recovery(unit, error) -> None:
    unit.read_input_registers.side_effect = [error, [250]]
    client = AnkerSolixExtrasClient(unit)
    with pytest.raises(TemperatureReadError):
        await client.async_read_temperature()
    assert await client.async_read_temperature() == 25


@pytest.mark.parametrize("value", [0, 87, 100])
async def test_read_state_of_health(unit, value) -> None:
    """Use the read-only register and return the whole percentage as reported."""
    unit.read_input_registers.return_value = [value]
    assert await AnkerSolixExtrasClient(unit).async_read_state_of_health() == value
    unit.read_input_registers.assert_awaited_once_with(10015, 1)


@pytest.mark.parametrize("registers", [[], [87, 87], [True], [-1], [101], [0xFFFF]])
async def test_invalid_state_of_health(unit, registers) -> None:
    unit.read_input_registers.return_value = registers
    with pytest.raises(StateOfHealthReadError, match="Invalid"):
        await AnkerSolixExtrasClient(unit).async_read_state_of_health()


@pytest.mark.parametrize(
    ("registers", "ac", "battery"),
    [
        ([0xFFFF, 0xF66E, 0xFFFF, 0xF75E], -2450, -2210),
        ([0, 0, 0, 0], 0, 0),
        ([0, 65535, 1, 0], 65535, 65536),
        ([0x7FFF, 0xFFFF, 0x8000, 0], 2147483647, -2147483648),
        ([0xFFFF, 0xFFFF, 0, 1], -1, 1),
    ],
)
async def test_read_power_in_one_request(unit, registers, ac, battery) -> None:
    """Decode both signed powers from one four-register snapshot, high word first."""
    unit.read_input_registers.return_value = registers
    power = await AnkerSolixExtrasClient(unit).async_read_power()
    assert power.ac_power == ac
    assert power.battery_power == battery
    unit.read_input_registers.assert_awaited_once_with(10006, 4)
    unit.write_register.assert_not_called()
    unit.write_registers.assert_not_called()


@pytest.mark.parametrize(
    "registers",
    [
        [],
        [0, 0],
        [0, 0, 0],
        [0, 0, 0, 0, 0],
        [None, 0, 0, 0],
        [0, True, 0, 0],
        [0, 0, -1, 0],
        [0, 0, 0, 65536],
        [0, 0, "0", 0],
        [0.0, 0, 0, 0],
        None,
    ],
)
async def test_invalid_power_response_is_not_zero(unit, registers) -> None:
    unit.read_input_registers.return_value = registers
    with pytest.raises(PowerReadError):
        await AnkerSolixExtrasClient(unit).async_read_power()


async def test_power_read_after_temperature_rejection(unit) -> None:
    """A rejected temperature register does not prevent a fresh power read."""
    unit.read_input_registers.side_effect = [
        IllegalDataAddressError("not supported"),
        [0, 0, 0, 0],
    ]
    client = AnkerSolixExtrasClient(unit)
    with pytest.raises(TemperatureReadError):
        await client.async_read_temperature()
    assert (await client.async_read_power()).heating_power == 0


@pytest.mark.parametrize(
    ("method", "error"),
    [
        ("async_read_power", PowerReadError),
        ("async_read_state_of_health", StateOfHealthReadError),
        ("async_read_backup_reserve", BackupReserveError),
    ],
)
async def test_transport_error_is_reported_for_each_measurement(unit, method, error):
    unit.read_input_registers.side_effect = IllegalDataAddressError("not supported")
    with pytest.raises(error):
        await getattr(AnkerSolixExtrasClient(unit), method)()


@pytest.mark.parametrize(
    ("mask", "registers", "address", "expected"),
    [
        (15, [7, 1], 60002, BackupReserve(True, True, 7)),
        (8, [0], 60003, BackupReserve(False, True, None)),
        (4, [0, 1], 60002, BackupReserve(True, False, 0)),
        (3, [], None, None),
    ],
)
async def test_read_backup_reserve(unit, mask, registers, address, expected) -> None:
    unit.read_input_registers.return_value = [mask]
    unit.read_holding_registers.return_value = registers
    assert await AnkerSolixExtrasClient(unit).async_read_backup_reserve() == expected
    unit.read_input_registers.assert_awaited_once_with(32775, 1)
    if address is None:
        unit.read_holding_registers.assert_not_awaited()
    else:
        unit.read_holding_registers.assert_awaited_once_with(address, len(registers))
    unit.write_register.assert_not_awaited()


@pytest.mark.parametrize("registers", [[], [50], [101, 1], [50, 2], [0, True]])
async def test_invalid_backup_reserve_response(unit, registers) -> None:
    unit.read_input_registers.return_value = [15]
    unit.read_holding_registers.return_value = registers
    with pytest.raises(BackupReserveError, match="Invalid reserve"):
        await AnkerSolixExtrasClient(unit).async_read_backup_reserve()


async def test_write_backup_reserve_uses_only_single_register_writes(unit) -> None:
    client = AnkerSolixExtrasClient(unit)
    await client.async_write_reserve_enabled(True)
    await client.async_write_reserve_percentage(0)
    await client.async_write_reserve_percentage(100)
    await client.async_write_reserve_enabled(False)
    assert unit.write_register.await_args_list == [
        call(60003, 1),
        call(60002, 0),
        call(60002, 100),
        call(60003, 0),
    ]
    unit.write_registers.assert_not_awaited()


async def test_rejected_backup_reserve_write(unit) -> None:
    unit.write_register.side_effect = IllegalDataAddressError("not supported")
    with pytest.raises(BackupReserveError):
        await AnkerSolixExtrasClient(unit).async_write_reserve_enabled(True)
    unit.write_register.assert_awaited_once_with(60003, 1)


async def test_disconnected_backup_reserve_write_is_skipped(unit) -> None:
    unit.connected = False
    with pytest.raises(BackupReserveError, match="disconnected"):
        await AnkerSolixExtrasClient(unit).async_write_reserve_enabled(True)
    unit.write_register.assert_not_awaited()
