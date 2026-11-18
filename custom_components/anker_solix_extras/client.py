"""Modbus register access for Anker SOLIX Extras."""

from modbus_connection import ModbusError, ModbusUnit

from .const import (
    AC_POWER_ADDRESS,
    BATTERY_SOH_ADDRESS,
    BATTERY_TEMPERATURE_ADDRESS,
    RESERVE_CAPABILITY_ADDRESS,
    RESERVE_ENABLE_ADDRESS,
    RESERVE_ENABLE_CAPABILITY,
    RESERVE_PERCENTAGE_ADDRESS,
    RESERVE_PERCENTAGE_CAPABILITY,
)
from .models import BackupReserve, BatteryPower


class TemperatureReadError(Exception):
    """A temperature reading could not be obtained."""


class PowerReadError(Exception):
    """A pair of power readings could not be obtained."""


class StateOfHealthReadError(Exception):
    """A battery state of health reading could not be obtained."""


class BackupReserveError(Exception):
    """The backup reserve settings could not be read."""


class RegisterWriteError(Exception):
    """A Modbus register write could not be completed."""


class AnkerSolixExtrasClient:
    """Read and write Modbus registers through a shared unit."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Use the Modbus unit managed by Home Assistant."""
        self._unit = unit

    async def async_read_temperature(self) -> float:
        """Read a signed 16-bit temperature in tenths of a degree Celsius."""
        try:
            registers = await self._unit.read_input_registers(
                BATTERY_TEMPERATURE_ADDRESS, 1
            )
        except (ModbusError, OSError) as err:
            raise TemperatureReadError("Unable to read battery temperature") from err
        if not _valid_words(registers, 1):
            raise TemperatureReadError("Invalid temperature response")
        raw = registers[0]
        return (raw - 0x10000 if raw & 0x8000 else raw) / 10

    async def async_read_power(self) -> BatteryPower:
        """Read AC and battery power together as high-word-first signed INT32."""
        try:
            registers = await self._unit.read_input_registers(AC_POWER_ADDRESS, 4)
        except (ModbusError, OSError) as err:
            raise PowerReadError("Unable to read battery power") from err
        if not _valid_words(registers, 4):
            raise PowerReadError("Invalid power response")
        values = []
        for offset in (0, 2):
            raw = (registers[offset] << 16) | registers[offset + 1]
            values.append(raw - 0x100000000 if raw & 0x80000000 else raw)
        return BatteryPower(ac_power=values[0], battery_power=values[1])

    async def async_read_state_of_health(self) -> int:
        """Read the battery system's state of health as a whole percentage."""
        try:
            registers = await self._unit.read_input_registers(BATTERY_SOH_ADDRESS, 1)
        except (ModbusError, OSError) as err:
            raise StateOfHealthReadError(
                "Unable to read battery state of health"
            ) from err
        if not _valid_words(registers, 1) or registers[0] > 100:
            raise StateOfHealthReadError("Invalid SOH response")
        return registers[0]

    async def async_read_backup_reserve(self) -> BackupReserve | None:
        """Read the advertised reserve controls and their current values."""
        try:
            registers = await self._unit.read_input_registers(
                RESERVE_CAPABILITY_ADDRESS, 1
            )
            if not _valid_words(registers, 1):
                raise BackupReserveError("Invalid reserve capability response")
            mask = registers[0]
            switch_supported = bool(mask & RESERVE_ENABLE_CAPABILITY)
            percentage_supported = bool(mask & RESERVE_PERCENTAGE_CAPABILITY)
            if not (switch_supported or percentage_supported):
                return None

            # The percentage's write condition needs the enable flag even when
            # the device does not advertise that the flag itself is writable.
            address, count = (
                (RESERVE_PERCENTAGE_ADDRESS, 2)
                if percentage_supported
                else (RESERVE_ENABLE_ADDRESS, 1)
            )
            registers = await self._unit.read_holding_registers(address, count)
        except (ModbusError, OSError) as err:
            raise BackupReserveError("Unable to read backup reserve") from err
        if not _valid_words(registers, count):
            raise BackupReserveError("Invalid reserve settings response")
        enabled = registers[-1]
        percentage = registers[0] if percentage_supported else None
        if enabled not in (0, 1):
            raise BackupReserveError("Invalid reserve enable flag")
        if percentage is not None and percentage > 100:
            raise BackupReserveError("Invalid reserve percentage")
        return BackupReserve(bool(enabled), switch_supported, percentage)

    async def async_write_register(self, address: int, value: int) -> None:
        """Write one holding register (FC06) on the active connection."""
        if not self._unit.connected:
            raise RegisterWriteError("Modbus connection closed before the write")
        try:
            await self._unit.write_register(address, value)
        except (ModbusError, OSError) as err:
            raise RegisterWriteError(
                f"Unable to write holding register {address}"
            ) from err


def _valid_words(registers: list[int], count: int) -> bool:
    """Check that a response contains exactly the requested 16-bit words."""
    return (
        isinstance(registers, list)
        and len(registers) == count
        and all(type(word) is int and 0 <= word <= 0xFFFF for word in registers)
    )
