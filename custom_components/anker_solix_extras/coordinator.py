"""Coordinate additional measurements without modifying the official integration."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AnkerSolixExtrasClient, PowerReadError, TemperatureReadError
from .const import CONF_OFFICIAL_ENTRY_ID, DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import BatteryMeasurements
from .source import OfficialBattery, async_get_battery

_LOGGER = logging.getLogger(__name__)


class AnkerSolixExtrasCoordinator(DataUpdateCoordinator[BatteryMeasurements]):
    """Poll additional registers at a modest interval."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, battery: OfficialBattery
    ) -> None:
        """Initialize the coordinator and its independently owned connection."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            always_update=False,
        )
        self.official_entry_id: str = entry.data[CONF_OFFICIAL_ENTRY_ID]
        self.device = battery.device
        self._address = (battery.host, battery.port)
        self._client = AnkerSolixExtrasClient(*self._address)

    async def _async_update_data(self) -> BatteryMeasurements:
        """Resolve the current address and fetch a fresh reading."""
        battery = async_get_battery(self.hass, self.official_entry_id)
        if battery is None or battery.device.id != self.device.id:
            self._client.close()
            raise UpdateFailed("The linked official battery is unavailable")

        address = (battery.host, battery.port)
        if address != self._address:
            self._client.close()
            self._address = address
            self._client = AnkerSolixExtrasClient(*address)

        temperature = None
        power = None
        try:
            temperature = await self._client.async_read_temperature()
        except TemperatureReadError as err:
            _LOGGER.debug("Temperature read failed: %s", err)
        try:
            power = await self._client.async_read_power()
        except PowerReadError as err:
            _LOGGER.debug("Power read failed: %s", err)
        if temperature is None and power is None:
            raise UpdateFailed("Unable to read battery temperature or power")
        return BatteryMeasurements(temperature=temperature, power=power)

    async def async_shutdown(self) -> None:
        """Stop polling and close the Extras connection."""
        await super().async_shutdown()
        self._client.close()
