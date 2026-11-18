"""Tests for read-only Modbus access and signed measurement decoding."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pymodbus.exceptions import ModbusException

from custom_components.anker_solix_extras.client import (
    AnkerSolixExtrasClient,
    PowerReadError,
    TemperatureReadError,
)


@pytest.fixture
def transport():
    """Provide a connected pymodbus transport without network I/O."""
    with patch(
        "custom_components.anker_solix_extras.client.AsyncModbusTcpClient",
        autospec=True,
    ) as factory:
        client = factory.return_value
        client.connected = True
        client.connect = AsyncMock(return_value=True)
        client.read_input_registers = AsyncMock()
        yield client


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(250, 25.0), (0, 0.0), (0xFFCE, -5.0), (253, 25.3), (0xFFCB, -5.3)],
)
async def test_read_temperature(transport, raw, expected) -> None:
    transport.read_input_registers.return_value = SimpleNamespace(
        registers=[raw], isError=lambda: False
    )
    client = AnkerSolixExtrasClient("192.0.2.10", 502)
    assert await client.async_read_temperature() == pytest.approx(expected)
    transport.read_input_registers.assert_awaited_once_with(
        address=10156, count=1, device_id=1
    )
    transport.write_register.assert_not_called()
    transport.write_registers.assert_not_called()
    transport.close.assert_not_called()


@pytest.mark.parametrize("registers", [[], [1, 2], [None], [True], [-1], [65536]])
async def test_bad_response_is_not_a_zero_temperature(transport, registers) -> None:
    transport.read_input_registers.return_value = SimpleNamespace(
        registers=registers, isError=lambda: False
    )
    client = AnkerSolixExtrasClient("192.0.2.10", 502)
    with pytest.raises(TemperatureReadError):
        await client.async_read_temperature()
    transport.close.assert_called_once()


async def test_rejected_register_closes_connection(transport) -> None:
    transport.read_input_registers.return_value = SimpleNamespace(isError=lambda: True)
    client = AnkerSolixExtrasClient("192.0.2.10", 502)
    with pytest.raises(TemperatureReadError, match="rejected"):
        await client.async_read_temperature()
    transport.close.assert_called_once()


async def test_connection_failure(transport) -> None:
    transport.connected = False
    transport.connect.return_value = False
    client = AnkerSolixExtrasClient("192.0.2.10", 502)
    with pytest.raises(TemperatureReadError, match="connect"):
        await client.async_read_temperature()
    transport.read_input_registers.assert_not_called()


@pytest.mark.parametrize("error", [OSError("offline"), ModbusException("timeout")])
async def test_transport_failure(transport, error) -> None:
    transport.read_input_registers.side_effect = error
    client = AnkerSolixExtrasClient("192.0.2.10", 502)
    with pytest.raises(TemperatureReadError):
        await client.async_read_temperature()
    transport.close.assert_called_once()


async def test_reconnects_when_disconnected(transport) -> None:
    transport.connected = False
    transport.read_input_registers.return_value = SimpleNamespace(
        registers=[250], isError=lambda: False
    )
    client = AnkerSolixExtrasClient("192.0.2.10", 502)
    assert await client.async_read_temperature() == 25
    transport.connect.assert_awaited_once()


def test_close_releases_own_transport(transport) -> None:
    AnkerSolixExtrasClient("192.0.2.10", 502).close()
    transport.close.assert_called_once()


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
async def test_read_power_in_one_request(transport, registers, ac, battery) -> None:
    """Decode both signed powers from one four-register snapshot, high word first."""
    transport.read_input_registers.return_value = SimpleNamespace(
        registers=registers, isError=lambda: False
    )
    power = await AnkerSolixExtrasClient("192.0.2.10", 502).async_read_power()
    assert power.ac_power == ac
    assert power.battery_power == battery
    transport.read_input_registers.assert_awaited_once_with(
        address=10006, count=4, device_id=1
    )
    transport.write_register.assert_not_called()
    transport.write_registers.assert_not_called()
    transport.close.assert_not_called()


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
async def test_invalid_power_response_is_not_zero(transport, registers) -> None:
    """Reject incomplete words, bools, nonintegers, and out-of-range values."""
    transport.read_input_registers.return_value = SimpleNamespace(
        registers=registers, isError=lambda: False
    )
    with pytest.raises(PowerReadError):
        await AnkerSolixExtrasClient("192.0.2.10", 502).async_read_power()
    transport.close.assert_called_once()


async def test_rejected_power_read(transport) -> None:
    """A rejected request cannot be interpreted as inactive heating."""
    transport.read_input_registers.return_value = SimpleNamespace(isError=lambda: True)
    with pytest.raises(PowerReadError, match="rejected"):
        await AnkerSolixExtrasClient("192.0.2.10", 502).async_read_power()
    transport.close.assert_called_once()


@pytest.mark.parametrize(
    "error", [OSError("offline"), ModbusException("failure"), TimeoutError()]
)
async def test_power_transport_failure(transport, error) -> None:
    """Wrap transport failures and release the owned connection."""
    transport.read_input_registers.side_effect = error
    with pytest.raises(PowerReadError):
        await AnkerSolixExtrasClient("192.0.2.10", 502).async_read_power()
    transport.close.assert_called_once()


async def test_power_connection_failure(transport) -> None:
    """Do not read from a connection that could not be established."""
    transport.connected = False
    transport.connect.return_value = False
    with pytest.raises(PowerReadError, match="connect"):
        await AnkerSolixExtrasClient("192.0.2.10", 502).async_read_power()
    transport.read_input_registers.assert_not_awaited()
    transport.close.assert_called_once()


async def test_power_reconnects_after_temperature_failure(transport) -> None:
    """A rejected temperature register does not prevent a fresh power read."""
    transport.read_input_registers.side_effect = [
        SimpleNamespace(isError=lambda: True),
        SimpleNamespace(registers=[0, 0, 0, 0], isError=lambda: False),
    ]
    client = AnkerSolixExtrasClient("192.0.2.10", 502)
    with pytest.raises(TemperatureReadError):
        await client.async_read_temperature()
    transport.connected = False
    assert (await client.async_read_power()).heating_power == 0
    transport.connect.assert_awaited_once()
