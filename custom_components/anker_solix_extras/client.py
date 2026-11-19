"""Modbus register access for Anker SOLIX Extras."""

from modbus_connection import IllegalDataAddressError, ModbusError, ModbusUnit

from .const import (
    AC_POWER_ADDRESS,
    BATTERY_SOH_ADDRESS,
    BATTERY_TEMPERATURE_ADDRESS,
    OFF_GRID_OUTPUT_POWER_ADDRESS,
    PLANT_STATUS_ADDRESS,
    PLANT_STATUS_STATES,
    RESERVE_CAPABILITY_ADDRESS,
    RESERVE_ENABLE_ADDRESS,
    RESERVE_ENABLE_CAPABILITY,
)
from .models import BatteryPower


class TemperatureReadError(Exception):
    """A temperature reading could not be obtained."""


class PowerReadError(Exception):
    """A pair of power readings could not be obtained."""


class StateOfHealthReadError(Exception):
    """A battery state of health reading could not be obtained."""


class OffGridOutputPowerReadError(Exception):
    """An off-grid output power reading could not be obtained."""


class BackupReserveError(Exception):
    """The backup reserve switch state could not be read."""


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

    async def async_read_status_and_power(self) -> tuple[str | None, BatteryPower]:
        """Read plant status and the paired power values in one FC04 request."""
        power_offset = AC_POWER_ADDRESS - PLANT_STATUS_ADDRESS
        count = power_offset + 4
        plant_status = None
        try:
            try:
                registers = await self._unit.read_input_registers(
                    PLANT_STATUS_ADDRESS, count
                )
            except IllegalDataAddressError:
                # Preserve heating on firmware that rejects the wider range.
                registers = await self._unit.read_input_registers(AC_POWER_ADDRESS, 4)
            else:
                if not _valid_words(registers, count):
                    raise PowerReadError("Invalid plant status and power response")
                plant_status = PLANT_STATUS_STATES.get(registers[0])
                registers = registers[power_offset:]
        except (ModbusError, OSError) as err:
            raise PowerReadError("Unable to read battery power") from err
        if not _valid_words(registers, 4):
            raise PowerReadError("Invalid power response")
        values = []
        for offset in (0, 2):
            raw = (registers[offset] << 16) | registers[offset + 1]
            values.append(raw - 0x100000000 if raw & 0x80000000 else raw)
        return plant_status, BatteryPower(ac_power=values[0], battery_power=values[1])

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

    async def async_read_off_grid_output_power(self) -> int:
        """Read the raw value from the experimental off-grid output register."""
        try:
            registers = await self._unit.read_input_registers(
                OFF_GRID_OUTPUT_POWER_ADDRESS, 1
            )
        except (ModbusError, OSError) as err:
            raise OffGridOutputPowerReadError(
                "Unable to read off-grid output power"
            ) from err
        if not _valid_words(registers, 1):
            raise OffGridOutputPowerReadError("Invalid off-grid output power response")
        return registers[0]

    async def async_read_backup_reserve(self) -> bool | None:
        """Read the reserve switch state if the battery advertises it."""
        try:
            registers = await self._unit.read_input_registers(
                RESERVE_CAPABILITY_ADDRESS, 1
            )
            if not _valid_words(registers, 1):
                raise BackupReserveError("Invalid reserve capability response")
            if not registers[0] & RESERVE_ENABLE_CAPABILITY:
                return None

            registers = await self._unit.read_holding_registers(
                RESERVE_ENABLE_ADDRESS, 1
            )
        except (ModbusError, OSError) as err:
            raise BackupReserveError("Unable to read backup reserve") from err
        if not _valid_words(registers, 1) or registers[0] not in (0, 1):
            raise BackupReserveError("Invalid reserve enable flag")
        return bool(registers[0])

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
