"""Read-only Modbus access for additional SOLIX measurements."""

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import BATTERY_TEMPERATURE_ADDRESS, MODBUS_DEVICE_ID, MODBUS_TIMEOUT


class TemperatureReadError(Exception):
    """A temperature reading could not be obtained."""


class AnkerSolixExtrasClient:
    """Own a separate Modbus connection; expose no write operations."""

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
