"""Modbus access for additional SOLIX measurements and reserve controls."""

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    AC_POWER_ADDRESS,
    BATTERY_SOH_ADDRESS,
    BATTERY_TEMPERATURE_ADDRESS,
    MODBUS_DEVICE_ID,
    MODBUS_TIMEOUT,
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
    """A backup reserve read or write could not be confirmed."""


class AnkerSolixExtrasClient:
    """Own a separate Modbus connection with dedicated reserve write methods."""

    def __init__(self, host: str, port: int) -> None:
        """Create the transport on Home Assistant's event loop."""
        self._client = AsyncModbusTcpClient(
            host, port=port, timeout=MODBUS_TIMEOUT, retries=0
        )

    async def async_read_temperature(self) -> float:
        """Read a signed 16-bit temperature in tenths of a degree Celsius."""
        try:
            if not self._client.connected and not await self._client.connect():
                raise TemperatureReadError("Unable to connect to the battery")
            response = await self._client.read_input_registers(
                address=BATTERY_TEMPERATURE_ADDRESS,
                count=1,
                device_id=MODBUS_DEVICE_ID,
            )
            if response.isError():
                raise TemperatureReadError("The battery rejected the temperature read")
            registers = response.registers
            if len(registers) != 1 or type(registers[0]) is not int:
                raise TemperatureReadError("Incomplete temperature response")
            raw = registers[0]
            if not 0 <= raw <= 0xFFFF:
                raise TemperatureReadError("Invalid temperature register value")
            return (raw - 0x10000 if raw & 0x8000 else raw) / 10
        except (
            ModbusException,
            OSError,
            TimeoutError,
            AttributeError,
            TypeError,
        ) as err:
            self.close()
            raise TemperatureReadError("Unable to read battery temperature") from err
        except TemperatureReadError:
            self.close()
            raise

    def close(self) -> None:
        """Release only this integration's connection."""
        self._client.close()

    async def async_read_power(self) -> BatteryPower:
        """Read AC and battery power together as high-word-first signed INT32."""
        try:
            if not self._client.connected and not await self._client.connect():
                raise PowerReadError("Unable to connect to the battery")
            response = await self._client.read_input_registers(
                address=AC_POWER_ADDRESS,
                count=4,
                device_id=MODBUS_DEVICE_ID,
            )
            if response.isError():
                raise PowerReadError("The battery rejected the power read")
            registers = response.registers
            if len(registers) != 4 or any(
                type(word) is not int or not 0 <= word <= 0xFFFF for word in registers
            ):
                raise PowerReadError("Invalid power response")
            values = []
            for offset in (0, 2):
                raw = (registers[offset] << 16) | registers[offset + 1]
                values.append(raw - 0x100000000 if raw & 0x80000000 else raw)
            return BatteryPower(ac_power=values[0], battery_power=values[1])
        except (
            ModbusException,
            OSError,
            TimeoutError,
            AttributeError,
            TypeError,
        ) as err:
            self.close()
            raise PowerReadError("Unable to read battery power") from err
        except PowerReadError:
            self.close()
            raise

    async def async_read_state_of_health(self) -> int:
        """Read the battery system's state of health as a whole percentage."""
        try:
            if not self._client.connected and not await self._client.connect():
                raise StateOfHealthReadError("Unable to connect to the battery")
            response = await self._client.read_input_registers(
                address=BATTERY_SOH_ADDRESS,
                count=1,
                device_id=MODBUS_DEVICE_ID,
            )
            if response.isError():
                raise StateOfHealthReadError("The battery rejected the SOH read")
            registers = response.registers
            if (
                len(registers) != 1
                or type(registers[0]) is not int
                or not 0 <= registers[0] <= 100
            ):
                raise StateOfHealthReadError("Invalid SOH response")
            return registers[0]
        except (
            ModbusException,
            OSError,
            TimeoutError,
            AttributeError,
            TypeError,
        ) as err:
            self.close()
            raise StateOfHealthReadError(
                "Unable to read battery state of health"
            ) from err
        except StateOfHealthReadError:
            self.close()
            raise

    async def async_read_backup_reserve(self) -> BackupReserve | None:
        """Read the advertised reserve controls and their current values."""
        try:
            if not self._client.connected and not await self._client.connect():
                raise BackupReserveError("Unable to connect to the battery")
            response = await self._client.read_input_registers(
                address=RESERVE_CAPABILITY_ADDRESS, count=1, device_id=MODBUS_DEVICE_ID
            )
            if response.isError() or len(response.registers) != 1:
                raise BackupReserveError("Invalid reserve capability response")
            mask = response.registers[0]
            if type(mask) is not int or not 0 <= mask <= 0xFFFF:
                raise BackupReserveError("Invalid reserve capability mask")
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
            response = await self._client.read_holding_registers(
                address=address, count=count, device_id=MODBUS_DEVICE_ID
            )
            if response.isError() or len(response.registers) != count:
                raise BackupReserveError("Invalid reserve settings response")
            enabled = response.registers[-1]
            percentage = response.registers[0] if percentage_supported else None
            if type(enabled) is not int or enabled not in (0, 1):
                raise BackupReserveError("Invalid reserve enable flag")
            if percentage_supported and (
                type(percentage) is not int or not 0 <= percentage <= 100
            ):
                raise BackupReserveError("Invalid reserve percentage")
            return BackupReserve(bool(enabled), switch_supported, percentage)
        except (
            ModbusException,
            OSError,
            TimeoutError,
            AttributeError,
            TypeError,
        ) as err:
            self.close()
            raise BackupReserveError("Unable to read backup reserve") from err
        except BackupReserveError:
            self.close()
            raise

    async def async_write_reserve_enabled(self, enabled: bool) -> None:
        """Write the backup reserve enable flag."""
        await self._async_write_reserve_register(RESERVE_ENABLE_ADDRESS, int(enabled))

    async def async_write_reserve_percentage(self, percentage: int) -> None:
        """Write a whole reserve percentage."""
        if type(percentage) is not int or not 0 <= percentage <= 100:
            raise ValueError("Reserve percentage must be a whole number from 0 to 100")
        await self._async_write_reserve_register(RESERVE_PERCENTAGE_ADDRESS, percentage)

    async def _async_write_reserve_register(self, address: int, value: int) -> None:
        """Send FC06 on the connection used to check the current reserve settings."""
        try:
            if not self._client.connected:
                raise BackupReserveError(
                    "Battery disconnected before the reserve write"
                )
            response = await self._client.write_register(
                address=address, value=value, device_id=MODBUS_DEVICE_ID
            )
            if response.isError():
                raise BackupReserveError("The battery rejected the reserve write")
        except (ModbusException, OSError, TimeoutError, AttributeError) as err:
            self.close()
            raise BackupReserveError("Unable to write backup reserve") from err
        except BackupReserveError:
            self.close()
            raise
